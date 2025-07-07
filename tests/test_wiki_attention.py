import os

os.environ["MONGO_URI"] = "mongomock://localhost"

import pytest
from unittest.mock import patch

import pandas as pd

import scrapers.wiki_attention_strategy as wiki


def test_trending_candidates_error():
    with patch.object(wiki, "_fetch_topviews", side_effect=Exception("boom")):
        out = wiki.trending_candidates()
        assert out == {}


def test_trending_candidates_success():
    articles = [{"article": "Acme_Corp", "views": 5000}]
    with patch.object(wiki, "_fetch_topviews", return_value=articles), patch.object(
        wiki, "_looks_like_company", return_value=True
    ), patch.object(wiki, "_ticker_from_wikidata", return_value=("ACME", "Acme Corp")):
        out = wiki.trending_candidates()
        assert out == {"ACME": "Acme Corp"}


def test_build_wiki_portfolio_filters_on_spikes():
    universe = {"AAA": "Alpha Inc", "BBB": "Beta Inc", "CCC": "Cat Co"}

    def fake_cached_views(page: str):
        today = pd.Timestamp.today().normalize()
        idx = pd.date_range(end=today, periods=185)
        if page == "Alpha_Inc":
            vals = [50] * 178 + [100] * 7  # big spike last 7 days
        elif page == "Beta_Inc":
            vals = [50] * 178 + [60] * 7  # mild spike
        else:
            vals = [50] * 185  # no spike
        return pd.Series(vals, index=idx)

    with (
        patch.object(wiki, "sp1500_map", return_value=universe),
        patch.object(wiki, "trending_candidates", return_value={}),
        patch.object(
            wiki, "wiki_title", side_effect=lambda name: name.replace(" ", "_")
        ),
        patch.object(wiki, "cached_views", side_effect=fake_cached_views),
        patch.object(wiki, "adv_float", return_value=(10_000_000, 1_000_000_000)),
        patch.object(
            wiki,
            "sector_table",
            return_value=pd.Series({"AAA": "tech", "BBB": "tech", "CCC": "tech"}),
        ),
    ):
        df = wiki.build_wiki_portfolio(include_trending=False, top_k=2)

    assert list(df.symbol) == ["AAA", "BBB"]
    assert "CCC" not in df.symbol.values
    assert (
        df.loc[df.symbol == "AAA", "weight"].iat[0]
        > df.loc[df.symbol == "BBB", "weight"].iat[0]
    )
