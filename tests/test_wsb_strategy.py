import os
os.environ['MONGO_URI'] = 'mongomock://localhost'

import types
from unittest.mock import patch

import pandas as pd

import wsb_strategy as wsb

class DummyComment:
    def __init__(self, body):
        self.body = body

class DummyComments(list):
    def replace_more(self, limit=0):
        pass
    def list(self):
        return self

import time

class DummySubmission:
    def __init__(self, title, selftext, comments):
        self.title = title
        self.selftext = selftext
        self.comments = DummyComments([DummyComment(c) for c in comments])
        self.created_utc = time.time()

class DummyReddit:
    def subreddit(self, name):
        return self
    def new(self, limit=None):
        return [
            DummySubmission("Bullish on $AAPL", "", ["AAPL to 200", "I hate TSLA"]),
            DummySubmission("TSLA to the moon", "", ["TSLA is good"]),
            DummySubmission("GME is dead", "", []),
        ]


def fake_sentiment(batch):
    out = []
    for text in batch:
        if "hate" in text or "dead" in text:
            out.append("neg")
        else:
            out.append("pos")
    return out

@patch.object(wsb, 'reddit_client', return_value=DummyReddit())
@patch.object(wsb, 'load_universe', return_value={'AAPL','TSLA','GME'})
@patch.object(wsb, 'label_sentiment', side_effect=fake_sentiment)
def test_run_analysis(_, __, ___):
    df = wsb.run_analysis(1, 3)
    assert set(df.symbol) == {'AAPL', 'TSLA', 'GME'}
    assert df.loc[df.symbol=='TSLA', 'mentions'].iat[0] > 0
    assert df.loc[df.symbol=='AAPL', 'pos'].iat[0] > 0

