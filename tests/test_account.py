import asyncio
import pytest

from analytics import account as acct


class FakeGateway:
    def __init__(self, paper=True):
        self.paper = paper

    async def account(self):
        return {"equity": 1000, "last_equity": 990}


@pytest.mark.asyncio
async def test_record_account(monkeypatch):
    rec_paper = []
    rec_live = []

    monkeypatch.setattr(
        acct.account_paper_coll, "insert_one", lambda d: rec_paper.append(d)
    )
    monkeypatch.setattr(
        acct.account_live_coll, "insert_one", lambda d: rec_live.append(d)
    )

    await acct.record_account(FakeGateway(paper=True))
    await acct.record_account(FakeGateway(paper=False))

    assert rec_paper and rec_live
