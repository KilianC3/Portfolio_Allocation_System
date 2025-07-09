#!/usr/bin/env python3
"""WallStreetBets sentiment screener.

Run with --refresh-universe to rebuild the universe caches,
otherwise it streams r/WallStreetBets and aggregates ticker mentions
with simple sentiment detection.
"""

import argparse
import datetime as dt
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, List, Dict

import pandas as pd
import praw
import requests
import yfinance as yf
from praw.models import Comment
from tqdm import tqdm

try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
    import torch
except Exception:  # transformers not installed
    AutoModelForSequenceClassification = None  # type: ignore
    AutoTokenizer = None  # type: ignore
    pipeline = None  # type: ignore
    torch = None  # type: ignore

from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
)

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
EQ_FILE = CACHE_DIR / "equity_universe.json"
CRYPTO_FILE = CACHE_DIR / "crypto_universe.json"

TOKEN_RE = re.compile(r"\b\$?([A-Z]{3,5})\b")
STOP_SHORT = {"A", "I", "AND", "THE", "FOR", "YOU", "ARE", "WITH", "TO", "IN"}

# -------------------- Universe builders --------------------


def build_equity_universe() -> None:
    """Top 50% of S&P 1500 by volume."""
    url = "https://en.wikipedia.org/wiki/S%26P_1500"
    html = requests.get(url, timeout=10).text
    dfs = pd.read_html(html)
    syms = set()
    for tbl in dfs[:3]:
        for col in tbl.columns:
            if str(col).lower().startswith(("ticker", "symbol")):
                syms.update(tbl[col].astype(str).str.upper())
                break
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
    """Top 500 cryptocurrencies by 24h volume."""
    reqs = []
    for page in (1, 2):
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "volume_desc",
                "per_page": 250,
                "page": page,
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


# -------------------- Reddit helpers --------------------


def reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT or "WSB-Strategy/1.0",
        check_for_async=False,
    )


def wsb_blobs(days: int) -> Iterable[str]:
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


# -------------------- Sentiment --------------------

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
            "sentiment-analysis",
            model=_mod,
            tokenizer=_tok,
            device=DEVICE,
            batch_size=16,
            truncation=True,
        )
    except Exception:
        _pipe = None
else:
    _pipe = None

POS_WORDS = {"buy", "bull", "long", "call", "moon"}
NEG_WORDS = {"sell", "bear", "short", "put", "down"}


def simple_sentiment(text: str) -> str:
    t = text.lower()
    pos = sum(w in t for w in POS_WORDS)
    neg = sum(w in t for w in NEG_WORDS)
    if pos > neg:
        return "pos"
    if neg > pos:
        return "neg"
    return "neu"


def label_sentiment(batch: List[str]) -> List[str]:
    if _pipe:
        out = _pipe(batch)
        return [o["label"].lower()[:3] for o in out]
    else:
        return [simple_sentiment(t) for t in batch]


# -------------------- Analysis --------------------


def run_analysis(days: int, top_n: int) -> pd.DataFrame:
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


# -------------------- CLI --------------------

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-universe", action="store_true")
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    if args.refresh_universe:
        build_equity_universe()
        build_crypto_universe()
        raise SystemExit

    df = run_analysis(args.days, args.top)
    if df.empty:
        print("No tickers found.")
    else:
        print(df.to_markdown(index=False))
