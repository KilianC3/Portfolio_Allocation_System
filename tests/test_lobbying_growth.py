import os

os.environ["PG_URI"] = "postgresql://localhost/test"

import asyncio
import datetime as dt

from database import lobby_coll
from strategies.lobbying_growth import LobbyingGrowthStrategy


class DummyPF:
    def __init__(self):
        self.weights = {}

    def set_weights(self, w):
        self.weights = w

    async def rebalance(self):
        pass


def seed_data():
    lobby_coll.delete_many({})
    today = dt.date.today()
    for i in range(40):
        amt_a = "$20000" if i < 20 else "$10000"
        lobby_coll.insert_one(
            {
                "ticker": "AAA",
                "client": "X",
                "amount": amt_a,
                "date": (today - dt.timedelta(days=i)).strftime("%m/%d/%Y"),
            }
        )
        lobby_coll.insert_one(
            {
                "ticker": "BBB",
                "client": "Y",
                "amount": "$10000",
                "date": (today - dt.timedelta(days=i)).strftime("%m/%d/%Y"),
            }
        )


async def _run():
    seed_data()
    strat = LobbyingGrowthStrategy(top_n=1)
    pf = DummyPF()
    await strat.build(pf)
    return pf.weights


def test_growth_weights():
    weights = asyncio.run(_run())
    assert weights == {"AAA": 1.0}
