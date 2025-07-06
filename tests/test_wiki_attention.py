import os
os.environ['MONGO_URI'] = 'mongomock://localhost'

import pytest
from unittest.mock import patch

import pandas as pd

import scrapers.wiki_attention_strategy as wiki


def test_trending_candidates_error():
    with patch.object(wiki, '_fetch_topviews', side_effect=Exception('boom')):
        out = wiki.trending_candidates()
        assert out == {}


def test_trending_candidates_success():
    articles = [{'article': 'Acme_Corp', 'views': 5000}]
    with patch.object(wiki, '_fetch_topviews', return_value=articles), \
         patch.object(wiki, '_looks_like_company', return_value=True), \
         patch.object(wiki, '_ticker_from_wikidata', return_value=('ACME', 'Acme Corp')):
        out = wiki.trending_candidates()
        assert out == {'ACME': 'Acme Corp'}
