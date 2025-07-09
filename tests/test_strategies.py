import asyncio
from unittest import mock
import pandas as pd

from core.equity import EquityPortfolio
from strategies import (
    CongressionalTradingAggregate,
    FollowTheLeaderSleeves,
    PelosiSleeve,
    MuserSleeve,
    CapitoSleeve,
    DCInsiderScoreTilt,
    GovContractsMomentum,
    CorporateInsiderBuyingPulse,
    AppReviewsHypeScore,
    GoogleTrendsNewsSentiment,
    RedditBuzzStrategy,
)


class FakeGW:
    async def order_to_pct(self, *a, **k):
        return None


class Coll(list):
    def find(self, *a, **k):
        return self


def portfolio_stub() -> EquityPortfolio:
    pf = EquityPortfolio("test", gateway=FakeGW())

    async def rebalance():
        return None

    pf.rebalance = rebalance
    return pf


async def run_all():
    with mock.patch("core.equity.pf_coll", new=mock.Mock()):
        pf = portfolio_stub()

        congress = CongressionalTradingAggregate()
        sleeves = FollowTheLeaderSleeves(["Rep"])
        pelosi = PelosiSleeve()
        muser = MuserSleeve()
        capito = CapitoSleeve()
        insider = DCInsiderScoreTilt()
        contracts = GovContractsMomentum()
        corp = CorporateInsiderBuyingPulse()
        hype = AppReviewsHypeScore()
        trends = GoogleTrendsNewsSentiment()
        reddit = RedditBuzzStrategy(days=1, top_n=2)

        trade = Coll(
            [
                {
                    "politician": "Rep",
                    "ticker": "AAPL",
                    "transaction": "buy",
                    "amount": "$1",
                    "date": "2024-01-01",
                },
                {
                    "politician": "Rep",
                    "ticker": "MSFT",
                    "transaction": "sell",
                    "amount": "$1",
                    "date": "2024-01-01",
                },
            ]
        )
        insider_data = Coll([{"ticker": "AAPL", "score": "10", "date": "2024-01-01"}])
        contract_data = Coll(
            [{"ticker": "AAPL", "value": "$60000000", "date": "2024-01-01"}]
        )
        buy_data = Coll(
            [{"ticker": "AAPL", "exec": "X", "shares": "100", "date": "2024-01-01"}]
        )
        app_data = Coll([{"ticker": "AAPL", "hype": "5", "date": "2024-01-01"}])
        trend_data = Coll([{"ticker": "AAPL", "score": "5", "date": "2024-01-15"}])

        with mock.patch(
            "strategies.congress_aggregate.politician_coll", trade
        ), mock.patch(
            "strategies.politician_sleeves.politician_coll", trade
        ), mock.patch(
            "strategies.dc_insider_tilt.insider_coll", insider_data
        ), mock.patch(
            "strategies.gov_contracts_momentum.contracts_coll", contract_data
        ), mock.patch(
            "strategies.insider_buying.insider_buy_coll", buy_data
        ), mock.patch(
            "strategies.app_reviews_hype.app_reviews_coll", app_data
        ), mock.patch(
            "strategies.google_trends.trends_coll", trend_data
        ), mock.patch(
            "strategies.google_trends.news_coll",
            Coll(
                [{"ticker": "AAPL", "headline": "AAPL beats estimates", "time": "1d"}]
            ),
        ), mock.patch(
            "strategies.google_trends.app_reviews_coll",
            Coll([{"ticker": "AAPL", "hype": "5", "date": "2024-01-01"}]),
        ), mock.patch(
            "strategies.google_trends._pipe",
            lambda x: [{"label": "POSITIVE"}],
        ), mock.patch(
            "strategies.wallstreetbets.run_analysis",
            lambda d, t: pd.DataFrame({"symbol": ["AAPL", "MSFT"]}),
        ):
            await congress.build(pf)
            await sleeves.build(pf)
            await pelosi.build(pf)
            await muser.build(pf)
            await capito.build(pf)
            await insider.build(pf)
            await contracts.build(pf)
            await corp.build(pf)
            await hype.build(pf)
            await trends.build(pf)
            await reddit.build(pf)

        assert pf.weights
        print(list(pf.weights.keys()))


def test_strategies():
    asyncio.run(run_all())
