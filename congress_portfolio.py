from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Dict, Literal

TradeType = Literal["BUY", "SELL", "CLOSE"]

@dataclass
class Position:
    symbol: str
    market_value: Decimal
    pct_alloc: Decimal = field(init=False)

@dataclass
class TradeEvent:
    symbol: str
    trade_type: TradeType
    value: Decimal
    timestamp: datetime


def apply_trade(event: TradeEvent, portfolio: Dict[str, Position]) -> None:
    """Apply a trade to the portfolio and rebalance weights."""
    # Synthetic events (symbol starts with ``__``) are used solely to trigger a
    # rebalance. They should not modify positions.
    if not event.symbol.startswith("__"):
        pos = portfolio.get(event.symbol)

        if event.trade_type == "BUY":
            if pos:
                pos.market_value += event.value
            else:
                pos = Position(symbol=event.symbol, market_value=event.value)
                portfolio[event.symbol] = pos

        elif event.trade_type in ("SELL", "CLOSE"):
            if not pos:
                return  # selling what we don't own
            pos.market_value -= event.value
            if pos.market_value <= 0 or event.trade_type == "CLOSE":
                portfolio.pop(event.symbol, None)

    # ---------- rebalance ----------
    total = sum(p.market_value for p in portfolio.values())
    if total > 0:
        for p in portfolio.values():
            p.pct_alloc = (p.market_value / total * Decimal("100")).quantize(
                Decimal("0.01")
            )
    else:
        for p in portfolio.values():
            p.pct_alloc = Decimal("0")


def mark_to_market(portfolio: Dict[str, Position], prices: Dict[str, Dict[str, Decimal]]) -> None:
    """Update position market values using latest prices and trigger rebalance."""
    for sym, price in prices.items():
        if sym in portfolio:
            shares = portfolio[sym].market_value / price.get("old", Decimal("1"))
            portfolio[sym].market_value = shares * price.get("last", price["old"])
    apply_trade(TradeEvent("__synthetic__", "BUY", Decimal("0"), datetime.utcnow()), portfolio)

# Seed portfolio as of 4 Jul 2025 for Rep. Dan Muser
seed: Dict[str, Decimal] = {
    "NVDA":  Decimal("2630000"),
    "MSFT":  Decimal("454500"),
    "GOOGL": Decimal("350800"),
    "AAPL":  Decimal("322100"),
    "V":     Decimal("213300"),
    "HACK":  Decimal("141500"),
    "MCD":   Decimal("120200"),
    "ABT":   Decimal("118600"),
    "WM":    Decimal("112300"),
    "AMGN":  Decimal("105400"),
    "BRK.A": Decimal("99100"),
    "FNB":   Decimal("72900"),
    "JPM":   Decimal("69700"),
    "WFC":   Decimal("67700"),
    "FB":    Decimal("66100"),
    "PNC":   Decimal("60400"),
    "DIS":   Decimal("54700"),
    "NSC":   Decimal("45100"),
    "PFE":   Decimal("41000"),
    "MDT":   Decimal("34000"),
    "APTV":  Decimal("32400"),
    "NKE":   Decimal("29000"),
    "BP":    Decimal("27900"),
    "AAL":   Decimal("27800"),
    "EMR":   Decimal("23300"),
    "MDLZ":  Decimal("22400"),
    "GE":    Decimal("19600"),
    "QCOM":  Decimal("18500"),
    "KMB":   Decimal("17300"),
    "WPC":   Decimal("15400"),
    "GIS":   Decimal("12800"),
    "MRK":   Decimal("11500"),
    "ABBV":  Decimal("9500"),
    "HON":   Decimal("9200"),
    "XOM":   Decimal("8800"),
    "PG":    Decimal("8600"),
    "LMT":   Decimal("8100"),
    "INTC":  Decimal("7500"),
    "GPC":   Decimal("7400"),
    "EQNR":  Decimal("6600"),
    "NUE":   Decimal("6400"),
    "LEG":   Decimal("187"),
}

# Seed portfolio as of 4 Jul 2025 for Rep. Nancy Pelosi
pelosi_seed: Dict[str, Decimal] = {
    "AAPL":  Decimal("32840000"),
    "MSFT":  Decimal("17850000"),
    "NVDA":  Decimal("17270000"),
    "AMZN":  Decimal("15190000"),
    "GOOGL": Decimal("14210000"),
    "CRM":   Decimal("12330000"),
    "CRWD":  Decimal("4440000"),
    "NFLX":  Decimal("4380000"),
    "V":     Decimal("3420000"),
    "DIS":   Decimal("3360000"),
    "AXP":   Decimal("3310000"),
    "CMCSA": Decimal("721300"),
    "RBLX":  Decimal("660200"),
    "IBKR":  Decimal("475500"),
    "DBX":   Decimal("353900"),
    "MORN":  Decimal("350900"),
    "PYPL":  Decimal("332400"),
    "T":     Decimal("217200"),
    "QCOM":  Decimal("34300"),
    "WBD":   Decimal("34100"),
    "CLNE":  Decimal("6600"),
}

# Seed portfolio as of 4 Jul 2025 for Sen. Shelley Moore Capito
capito_seed: Dict[str, Decimal] = {
    "MSFT":  Decimal("326400"),
    "UBSI":  Decimal("219200"),
    "AAPL":  Decimal("130000"),
    "C":     Decimal("128500"),
    "TRV":   Decimal("103500"),
    "TFC":   Decimal("100800"),
    "JNJ":   Decimal("71200"),
    "KO":    Decimal("57700"),
    "ADI":   Decimal("51400"),
    "MCD":   Decimal("48000"),
    "GD":    Decimal("46200"),
    "ADP":   Decimal("43100"),
    "AMGN":  Decimal("40700"),
    "PAYX":  Decimal("40600"),
    "AVGO":  Decimal("39300"),
    "MDLZ":  Decimal("37800"),
    "LIN":   Decimal("37700"),
    "XOM":   Decimal("36700"),
    "BLK":   Decimal("35300"),
    "JPM":   Decimal("34400"),
    "CSCO":  Decimal("33200"),
    "AFL":   Decimal("33000"),
    "CVX":   Decimal("32300"),
    "SBUX":  Decimal("32200"),
    "ITW":   Decimal("32100"),
    "CB":    Decimal("32000"),
    "ABT":   Decimal("31800"),
    "FDS":   Decimal("31500"),
    "LOW":   Decimal("28900"),
    "NSC":   Decimal("27600"),
    "WFC":   Decimal("27100"),
    "ZTS":   Decimal("26000"),
    "PSX":   Decimal("22400"),
    "CEG":   Decimal("19700"),
    "LHX":   Decimal("19500"),
    "NEE":   Decimal("19300"),
    "GOOGL": Decimal("18300"),
    "WMT":   Decimal("14800"),
    "AUB":   Decimal("14700"),
    "ACN":   Decimal("14600"),
    "IBM":   Decimal("14400"),
    "UNH":   Decimal("13700"),
    "WMB":   Decimal("13300"),
    "COST":  Decimal("12100"),
    "EMR":   Decimal("11700"),
    "GE":    Decimal("11600"),
    "BAC":   Decimal("11600"),
    "DIS":   Decimal("10900"),
    "HBAN":  Decimal("10900"),
    "GILD":  Decimal("10700"),
    "WEC":   Decimal("9700"),
    "NVS":   Decimal("9700"),
    "DUK":   Decimal("9600"),
    "CMS":   Decimal("9500"),
    "FERG":  Decimal("9500"),
    "META":  Decimal("9400"),
    "QCOM":  Decimal("9300"),
    "CL":    Decimal("9200"),
    "VZ":    Decimal("9000"),
    "SNA":   Decimal("8900"),
    "MDT":   Decimal("8700"),
    "PG":    Decimal("8600"),
    "RPM":   Decimal("8300"),
    "LMT":   Decimal("8100"),
    "AMT":   Decimal("8100"),
    "QSR":   Decimal("7100"),
    "CSL":   Decimal("7100"),
    "PFE":   Decimal("6800"),
    "CVS":   Decimal("6700"),
    "SJM":   Decimal("6500"),
    "PPG":   Decimal("6400"),
    "GIS":   Decimal("6400"),
    "MRK":   Decimal("5700"),
    "CMCSA": Decimal("5300"),
    "INTC":  Decimal("3800"),
}


def init_portfolio(seed_data: Dict[str, Decimal] = seed) -> Dict[str, Position]:
    """Return portfolio dictionary populated from seed market values."""
    portfolio: Dict[str, Position] = {}
    for sym, val in seed_data.items():
        portfolio[sym] = Position(symbol=sym, market_value=val)
    # initial rebalance to populate pct_alloc fields
    apply_trade(TradeEvent("__init__", "BUY", Decimal("0"), datetime.utcnow()), portfolio)
    return portfolio


def init_pelosi_portfolio(seed_data: Dict[str, Decimal] = pelosi_seed) -> Dict[str, Position]:
    """Return Nancy Pelosi's portfolio populated from seed data."""
    return init_portfolio(seed_data)


def init_capito_portfolio(seed_data: Dict[str, Decimal] = capito_seed) -> Dict[str, Position]:
    """Return Shelley Moore Capito's portfolio populated from seed data."""
    return init_portfolio(seed_data)
