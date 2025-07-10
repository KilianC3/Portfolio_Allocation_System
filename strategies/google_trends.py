from __future__ import annotations

import pandas as pd
from typing import TYPE_CHECKING, Optional

try:
    from transformers import pipeline
except Exception:  # pragma: no cover - optional dependency
    pipeline = None  # type: ignore

if TYPE_CHECKING:
    from transformers.pipelines import TextClassificationPipeline

from database import (
    google_trends_coll as trends_coll,
    news_coll,
    app_reviews_coll,
)

from core.equity import EquityPortfolio


_pipe: Optional["TextClassificationPipeline"]

if pipeline is not None:
    try:  # pragma: no cover - download may fail
        _pipe = pipeline(task="text-classification")
    except Exception:  # pragma: no cover - fallback
        _pipe = None
else:  # pragma: no cover - pipeline import failure
    _pipe = None


class GoogleTrendsNewsSentiment:
    """Long tickers with rising search interest and positive news."""

    def __init__(self, top_n: int = 30) -> None:
        self.top_n = top_n

    @staticmethod
    def _score(text: str) -> int:
        if _pipe:
            try:
                out = _pipe(text[:512])[0]
                return (
                    1
                    if out["label"].startswith("POS")
                    else -1 if out["label"].startswith("NEG") else 0
                )
            except Exception:
                pass
        t = text.lower()
        pos_words = {"up", "beat", "surge", "buy", "bull"}
        neg_words = {"down", "miss", "drop", "sell", "bear"}
        pos = sum(w in t for w in pos_words)
        neg = sum(w in t for w in neg_words)
        if pos > neg:
            return 1
        if neg > pos:
            return -1
        return 0

    def _news_sentiment(self) -> pd.Series:
        docs = list(news_coll.find())
        if not docs:
            return pd.Series(dtype=float)
        df = pd.DataFrame(docs)
        df["score"] = df["headline"].map(self._score)
        return df.groupby("ticker")["score"].mean()

    def _review_hype(self) -> pd.Series:
        docs = list(app_reviews_coll.find())
        if not docs:
            return pd.Series(dtype=float)
        df = pd.DataFrame(docs)
        df["hype"] = pd.to_numeric(df["hype"], errors="coerce")
        return df.groupby("ticker")["hype"].mean()

    def _rank(self) -> pd.Series:
        docs = list(trends_coll.find())
        if not docs:
            return pd.Series(dtype=float)
        df = pd.DataFrame(docs)
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["score", "date"])
        latest = df["date"].max()
        cutoff = latest - pd.Timedelta(days=30)
        df = df[df["date"] >= cutoff]
        score = df.groupby("ticker")["score"].mean()
        return score.sort_values(ascending=False)

    async def build(self, pf: EquityPortfolio) -> None:
        ranks = self._rank().head(self.top_n)
        if ranks.empty:
            return
        senti = self._news_sentiment()
        hype = self._review_hype()
        filtered = [
            s for s in ranks.index if senti.get(s, 0) > 0 and hype.get(s, 0) > 0
        ]
        if not filtered:
            return
        w = {sym: 1 / len(filtered) for sym in filtered}
        pf.set_weights(w)
        await pf.rebalance()
