from __future__ import annotations

import asyncio
import datetime as dt
from typing import List

import pandas as pd

from database import db, pf_coll, init_db
from infra.data_store import append_snapshot
from metrics import scrape_latency, scrape_errors
from service.logger import get_logger

log = get_logger(__name__)

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Iterable

import praw
import requests
from praw.models import Comment
from tqdm import tqdm
from typing import TYPE_CHECKING
import yfinance as yf

from service.config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
from scrapers.universe import load_sp500, load_sp400, load_russell2000

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
EQ_FILE = CACHE_DIR / "equity_universe.json"
CRYPTO_FILE = CACHE_DIR / "crypto_universe.json"

TOKEN_RE = re.compile(r"\b\$?([A-Z]{3,5})\b")
STOP_SHORT = {"A", "I", "AND", "THE", "FOR", "YOU", "ARE", "WITH", "TO", "IN"}

if TYPE_CHECKING:  # pragma: no cover - optional
    from transformers.pipelines import TextClassificationPipeline

try:  # pragma: no cover - heavy optional dep
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
    import torch
except Exception:  # pragma: no cover - transformers unavailable
    AutoModelForSequenceClassification = None  # type: ignore
    AutoTokenizer = None  # type: ignore
    pipeline = None  # type: ignore
    torch = None  # type: ignore

_pipe: Optional["TextClassificationPipeline"]
if AutoTokenizer is not None:
    try:
        DEVICE = 0 if torch and torch.cuda.is_available() else -1
        _tok = AutoTokenizer.from_pretrained(
            "cardiffnlp/twitter-roberta-base-sentiment-latest"
        )
        _mod = AutoModelForSequenceClassification.from_pretrained(
            "cardiffnlp/twitter-roberta-base-sentiment-latest"
        )
        _pipe = pipeline(
            task="text-classification", model=_mod, tokenizer=_tok, device=DEVICE
        )
    except Exception:  # pragma: no cover - model load failure
        _pipe = None
else:  # pragma: no cover - transformers not installed
    _pipe = None


def build_equity_universe() -> None:
    """Cache the most liquid equity symbols."""
    syms = set(load_sp500()) | set(load_sp400()) | set(load_russell2000())
    df = yf.download(
        list(syms),
        period="1d",
        interval="1d",
        group_by="ticker",
        threads=True,
        progress=False,
    )
    vols = []
    for sym in syms:
        try:
            vols.append((sym, df[sym]["Volume"].iloc[-1]))
        except Exception:
            continue
    vols.sort(key=lambda x: x[1], reverse=True)
    cutoff = len(vols) // 2
    top_syms = [s for s, _ in vols[:cutoff]]
    EQ_FILE.write_text(json.dumps(top_syms))


def build_crypto_universe() -> None:
    """Cache the most liquid crypto symbols."""
    reqs = []
    for page in (1, 2):
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "volume_desc",
                "per_page": "250",
                "page": str(page),
            },
            timeout=10,
        )
        r.raise_for_status()
        reqs += r.json()
    syms = [item["symbol"].upper() for item in reqs[:500]]
    CRYPTO_FILE.write_text(json.dumps(syms))


def load_universe() -> set[str]:
    eq = set(json.loads(EQ_FILE.read_text())) if EQ_FILE.exists() else set()
    cp = set(json.loads(CRYPTO_FILE.read_text())) if CRYPTO_FILE.exists() else set()
    return eq | cp


def reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT or "WSB-Strategy/1.0",
    )


def wsb_blobs(days: int) -> Iterable[str]:  # pragma: no cover - network heavy
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rd = reddit_client()
    for sub in rd.subreddit("wallstreetbets").new(limit=None):
        if dt.datetime.fromtimestamp(sub.created_utc, dt.timezone.utc) < cutoff:
            break
        yield sub.title
        if sub.selftext:
            yield sub.selftext
        sub.comments.replace_more(limit=0)
        for cm in sub.comments.list():
            if isinstance(cm, Comment):
                yield cm.body
        time.sleep(0.5)


def simple_sentiment(text: str) -> str:
    t = text.lower()
    pos = sum(w in t for w in {"buy", "bull", "long", "call", "moon"})
    neg = sum(w in t for w in {"sell", "bear", "short", "put", "down"})
    if pos > neg:
        return "pos"
    if neg > pos:
        return "neg"
    return "neu"


def label_sentiment(batch: List[str]) -> List[str]:
    if _pipe:
        out = _pipe(batch)
        return [o["label"].lower()[:3] for o in out]
    return [simple_sentiment(t) for t in batch]


def run_analysis(days: int, top_n: int) -> pd.DataFrame:
    """Return mention counts and sentiment for top tickers."""
    uni = load_universe()
    if not uni:
        raise RuntimeError("Universe is empty; run with --refresh-universe first")

    raw_counts: Counter[str] = Counter()
    senti_counts: Dict[str, Counter[str]] = defaultdict(
        lambda: Counter(pos=0, neu=0, neg=0)
    )

    batch: List[str] = []
    for text in tqdm(wsb_blobs(days), desc="Blobs", unit="blob"):
        batch.append(text)
        if len(batch) == 32:
            labs = label_sentiment(batch)
            for txt, lab in zip(batch, labs):
                for tok in TOKEN_RE.findall(txt.upper()):
                    if tok in STOP_SHORT or tok not in uni:
                        continue
                    raw_counts[tok] += 1
                    senti_counts[tok][lab] += 1
            batch.clear()
    if batch:
        labs = label_sentiment(batch)
        for txt, lab in zip(batch, labs):
            for tok in TOKEN_RE.findall(txt.upper()):
                if tok in STOP_SHORT or tok not in uni:
                    continue
                raw_counts[tok] += 1
                senti_counts[tok][lab] += 1

    rows = []
    for sym, cnt in raw_counts.most_common(top_n):
        sc = senti_counts[sym]
        rows.append(
            {
                "symbol": sym,
                "mentions": cnt,
                "pos": sc["pos"],
                "neu": sc["neu"],
                "neg": sc["neg"],
            }
        )
    return pd.DataFrame(rows)


reddit_coll = db["reddit_mentions"] if db else pf_coll


async def fetch_wsb_mentions(days: int = 7, top_n: int = 15) -> List[dict]:
    """Collect WallStreetBets mention counts."""
    log.info("fetch_wsb_mentions start")
    init_db()
    with scrape_latency.labels("reddit_mentions").time():
        try:
            df = await asyncio.to_thread(run_analysis, days, top_n)
        except Exception as exc:
            scrape_errors.labels("reddit_mentions").inc()
            log.warning(f"fetch_wsb_mentions failed: {exc}")
            raise
    if df.empty:
        return []
    now = dt.datetime.now(dt.timezone.utc)
    rows: List[dict] = []
    for _, row in df.iterrows():
        item = {
            "ticker": row["symbol"],
            "mentions": int(row["mentions"]),
            "pos": int(row.get("pos", 0)),
            "neu": int(row.get("neu", 0)),
            "neg": int(row.get("neg", 0)),
            "date": str(dt.date.today()),
            "_retrieved": now,
        }
        reddit_coll.update_one(
            {"ticker": item["ticker"], "date": item["date"]},
            {"$set": item},
            upsert=True,
        )
        rows.append(item)
    append_snapshot("reddit_mentions", rows)
    log.info(f"fetched {len(rows)} wsb rows")
    return rows


if __name__ == "__main__":
    import asyncio

    print(asyncio.run(fetch_wsb_mentions(1, 2)))
