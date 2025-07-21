#!/usr/bin/env python3
"""Comprehensive fundamental scoring for the universe.

This script aggregates Yahoo Finance statements and price data to
compute quality, value, growth, momentum and risk metrics for a
collection of tickers. Results are saved to three CSV files in the
current directory.
"""
import math
import datetime as dt
import warnings
from typing import List, Sequence, Dict, Iterable, Tuple

from scrapers.universe import load_sp500, load_sp400, load_russell2000

import numpy as np
import pandas as pd
import yfinance as yf

PRICE_LOOKBACK_DAYS = 400
POSITION_DOLLARS = 5_000_000
BATCH_SIZE_PRICES = 350
BATCH_SLEEP_SEC = 1.0
OUTPUT_WIDE_CSV = "scores_wide.csv"
OUTPUT_LONG_CSV = "scores_long.csv"
OUTPUT_COMPACT_CSV = "scores_compact.csv"

WEIGHTS = {
    "value_score": 0.18,
    "quality_score": 0.17,
    "financial_strength_score": 0.10,
    "growth_score_adj": 0.20,
    "momentum_score_adj": 0.18,
    "risk_score": 0.07,
    "liquidity_score": 0.05,
    "piotroski_score": 0.05,
}

ALIASES = {
    "net_income": ["Net Income", "Net Income Applicable To Common Shares"],
    "total_revenue": ["Total Revenue", "Revenue", "Sales"],
    "gross_profit": ["Gross Profit"],
    "oper_income": ["Operating Income", "Operating Income Before Depreciation"],
    "ebit": ["Ebit", "EBIT"],
    "ebitda": ["Ebitda", "EBITDA"],
    "pretax": ["Income Before Tax", "Earnings Before Tax"],
    "income_tax": ["Income Tax Expense", "Income Tax Provision"],
    "interest_exp": ["Interest Expense", "Interest Expense Non Operating"],
    "ocf": ["Total Cash From Operating Activities", "Operating Cash Flow"],
    "capex": ["Capital Expenditures", "Capital Expenditure"],
    "total_assets": ["Total Assets"],
    "total_liabilities": [
        "Total Liab",
        "Total Liabilities Net Minority Interest",
        "Total Liabilities",
    ],
    "current_assets": ["Total Current Assets", "Current Assets"],
    "current_liabilities": ["Total Current Liabilities", "Current Liabilities"],
    "retained_earnings": [
        "Retained Earnings",
        "Retained Earnings (Accumulated Deficit)",
    ],
    "long_debt": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
    "short_debt": ["Short Long Term Debt", "Short Term Debt"],
    "equity": ["Total Stockholder Equity", "Total Equity Gross Minority Interest"],
    "common_stock": ["Common Stock", "Common Stock Total Equity"],
    "receivables": ["Net Receivables", "Accounts Receivable"],
    "ppe": ["Property Plant Equipment", "Property Plant And Equipment"],
    "sga": [
        "Selling General Administrative",
        "Selling General & Administrative",
        "SG&A Expense",
    ],
    "depreciation": [
        "Depreciation",
        "Depreciation Amortization",
        "Depreciation & Amortization",
    ],
}


def safe_div(a, b):
    try:
        if a is None or b is None or b == 0:
            return np.nan
        return a / b
    except Exception:
        return np.nan


def last_two(df: pd.DataFrame):
    if df is None or df.empty:
        return df
    cols = sorted(df.columns, reverse=True)
    return df[cols].iloc[:, :2]


def gv(df, aliases: Sequence[str], idx: int, default=np.nan):
    if df is None or df.empty:
        return default
    for name in aliases:
        if name in df.index:
            try:
                return float(df.loc[name].iloc[idx])
            except Exception:
                pass
    return default


def pct_change_price(series: pd.Series, periods: int):
    if len(series) < periods + 1:
        return np.nan
    return series.iloc[-1] / series.iloc[-(periods + 1)] - 1.0


def max_drawdown(series: pd.Series):
    if series.empty:
        return np.nan
    cm = series.cummax()
    return (series / cm - 1.0).min()


def download_prices_batch(
    tickers: List[str], lookback_days: int = PRICE_LOOKBACK_DAYS
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    end = dt.date.today()
    start = end - dt.timedelta(days=lookback_days)
    all_close = {}
    all_ohlcv = {}
    for i in range(0, len(tickers), BATCH_SIZE_PRICES):
        batch = tickers[i : i + BATCH_SIZE_PRICES]
        data = yf.download(
            batch,
            start=start,
            end=end,
            progress=False,
            group_by="ticker",
            threads=False,
            auto_adjust=False,
        )
        if isinstance(data.columns, pd.MultiIndex):
            for t in batch:
                sub = {}
                for f in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
                    if (t, f) in data.columns:
                        sub[f] = data[(t, f)]
                if sub:
                    df = pd.DataFrame(sub)
                    all_ohlcv[t] = df
                    all_close[t] = (
                        df["Adj Close"] if "Adj Close" in df.columns else df["Close"]
                    )
        else:
            t = batch[0]
            all_ohlcv[t] = data
            if "Adj Close" in data.columns:
                all_close[t] = data["Adj Close"]
            elif "Close" in data.columns:
                all_close[t] = data["Close"]
        if BATCH_SLEEP_SEC and i + BATCH_SIZE_PRICES < len(tickers):
            import time

            time.sleep(BATCH_SLEEP_SEC)
    close_df = pd.DataFrame(all_close).sort_index()
    return close_df, all_ohlcv


def previous_shares_outstanding(ticker: str):
    try:
        tk = yf.Ticker(ticker)
        hist = tk.get_shares_full(start=dt.date.today() - dt.timedelta(days=500))
        if hist is not None and not hist.empty:
            hist = hist.sort_index()
            return float(hist.iloc[0])
    except Exception:
        return None
    return None


def compute_piotroski(fin, bs, cf):
    if any(x is None or x.empty or x.shape[1] < 2 for x in [fin, bs, cf]):
        return np.nan
    ni0 = gv(fin, ALIASES["net_income"], 0)
    ni1 = gv(fin, ALIASES["net_income"], 1)
    ta0 = gv(bs, ALIASES["total_assets"], 0)
    ta1 = gv(bs, ALIASES["total_assets"], 1)
    roa0 = safe_div(ni0, ta0)
    roa1 = safe_div(ni1, ta1)
    cfo0 = gv(cf, ALIASES["ocf"], 0)
    debt0 = gv(bs, ALIASES["long_debt"], 0, 0.0) + gv(bs, ALIASES["short_debt"], 0, 0.0)
    debt1 = gv(bs, ALIASES["long_debt"], 1, 0.0) + gv(bs, ALIASES["short_debt"], 1, 0.0)
    ca0 = gv(bs, ALIASES["current_assets"], 0)
    ca1 = gv(bs, ALIASES["current_assets"], 1)
    cl0 = gv(bs, ALIASES["current_liabilities"], 0)
    cl1 = gv(bs, ALIASES["current_liabilities"], 1)
    cr0 = safe_div(ca0, cl0)
    cr1 = safe_div(ca1, cl1)
    rev0 = gv(fin, ALIASES["total_revenue"], 0)
    rev1 = gv(fin, ALIASES["total_revenue"], 1)
    gp0 = gv(fin, ALIASES["gross_profit"], 0)
    gp1 = gv(fin, ALIASES["gross_profit"], 1)
    gm0 = safe_div(gp0, rev0)
    gm1 = safe_div(gp1, rev1)
    at0 = safe_div(rev0, ta0)
    at1 = safe_div(rev1, ta1)
    common0 = gv(bs, ALIASES["common_stock"], 0, np.nan)
    common1 = gv(bs, ALIASES["common_stock"], 1, np.nan)
    share_flag = (
        1
        if (np.isnan(common0) or np.isnan(common1) or common0 <= common1 * 1.01)
        else 0
    )
    score = 0
    score += int(roa0 > 0)
    score += int(cfo0 > 0)
    score += int(roa0 > roa1)
    score += int(cfo0 > ni0)
    score += int(debt0 < debt1)
    score += int(cr0 > cr1)
    score += share_flag
    score += int(gm0 > gm1)
    score += int(at0 > at1)
    return score


def quality_metrics(fin, bs, cf):
    if any(x is None or x.empty for x in [fin, bs]):
        return {}
    ebit = gv(fin, ALIASES["ebit"], 0)
    pretax = gv(fin, ALIASES["pretax"], 0)
    tax_exp = gv(fin, ALIASES["income_tax"], 0)
    tax_rate = safe_div(tax_exp, pretax)
    if np.isnan(tax_rate) or tax_rate < 0 or tax_rate > 0.5:
        tax_rate = 0.21
    nopat = ebit * (1 - tax_rate) if not np.isnan(ebit) else np.nan
    d0 = gv(bs, ALIASES["long_debt"], 0, 0.0) + gv(bs, ALIASES["short_debt"], 0, 0.0)
    d1 = gv(bs, ALIASES["long_debt"], 1, 0.0) + gv(bs, ALIASES["short_debt"], 1, 0.0)
    eq0 = gv(bs, ALIASES["equity"], 0)
    eq1 = gv(bs, ALIASES["equity"], 1)
    invested_avg = np.nanmean([d0 + eq0, d1 + eq1])
    roic = safe_div(nopat, invested_avg)
    ni0 = gv(fin, ALIASES["net_income"], 0)
    avg_eq = np.nanmean([eq0, eq1])
    roe = safe_div(ni0, avg_eq)
    rev0 = gv(fin, ALIASES["total_revenue"], 0)
    gp0 = gv(fin, ALIASES["gross_profit"], 0)
    op0 = gv(fin, ALIASES["oper_income"], 0)
    gross_margin = safe_div(gp0, rev0)
    oper_margin = safe_div(op0, rev0)
    net_margin = safe_div(ni0, rev0)
    cfo0 = gv(cf, ALIASES["ocf"], 0)
    assets0 = gv(bs, ALIASES["total_assets"], 0)
    accruals = safe_div(ni0 - cfo0, assets0)
    return dict(
        roic=roic,
        roe=roe,
        gross_margin=gross_margin,
        oper_margin=oper_margin,
        net_margin=net_margin,
        accruals=accruals,
    )


def growth_metrics(fin):
    if fin is None or fin.empty or fin.shape[1] < 2:
        return {}
    r0 = gv(fin, ALIASES["total_revenue"], 0)
    r1 = gv(fin, ALIASES["total_revenue"], 1)
    g0 = gv(fin, ALIASES["gross_profit"], 0)
    g1 = gv(fin, ALIASES["gross_profit"], 1)
    e0 = gv(fin, ALIASES["ebitda"], 0)
    e1 = gv(fin, ALIASES["ebitda"], 1)
    rev_growth = safe_div(r0 - r1, r1)
    gm0 = safe_div(g0, r0)
    gm1 = safe_div(g1, r1)
    gm_trend = (gm0 - gm1) if not (np.isnan(gm0) or np.isnan(gm1)) else np.nan
    ebitda_growth = safe_div(e0 - e1, e1)
    accel = (ebitda_growth - rev_growth) + gm_trend
    return dict(
        revenue_growth=rev_growth,
        gross_margin_trend=gm_trend,
        ebitda_growth=ebitda_growth,
        growth_acceleration=accel,
    )


def value_metrics(fin, bs, cf, info, shares_prev):
    if info is None:
        info = {}
    ebit = gv(fin, ALIASES["ebit"], 0)
    ebitda = gv(fin, ALIASES["ebitda"], 0)
    ocf = gv(cf, ALIASES["ocf"], 0)
    capex = gv(cf, ALIASES["capex"], 0)
    fcf = (ocf + capex) if not (np.isnan(ocf) or np.isnan(capex)) else np.nan
    mcap = info.get("marketCap")
    total_debt = info.get("totalDebt")
    if total_debt is None or np.isnan(total_debt):
        total_debt = gv(bs, ALIASES["long_debt"], 0, 0.0) + gv(
            bs, ALIASES["short_debt"], 0, 0.0
        )
    cash = info.get("totalCash") or info.get("cash") or 0.0
    ev = info.get("enterpriseValue")
    if ev is None or np.isnan(ev):
        if mcap and total_debt is not None:
            ev = mcap + total_debt - (cash or 0.0)
    earnings_yield = safe_div(ebit, ev)
    fcf_yield = safe_div(fcf, ev)
    ev_ebitda = safe_div(ev, ebitda) if ebitda not in (0, np.nan) else np.nan
    ev_ebit = safe_div(ev, ebit) if ebit not in (0, np.nan) else np.nan
    equity = gv(bs, ALIASES["equity"], 0)
    revenue = gv(fin, ALIASES["total_revenue"], 0)
    pb = safe_div(mcap, equity)
    ps = safe_div(mcap, revenue)
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    dividend_rate = info.get("dividendRate")
    dividend_yield = (
        safe_div(dividend_rate, price) if (dividend_rate and price) else 0.0
    )
    shares_now = info.get("sharesOutstanding")
    buyback_yield = 0.0
    if shares_now and shares_prev and shares_prev > 0:
        delta = shares_prev - shares_now
        pct = delta / shares_prev
        buyback_yield = pct if pct > 0 else 0.0
    shareholder_yield = (dividend_yield or 0.0) + (buyback_yield or 0.0)
    return dict(
        earnings_yield=earnings_yield,
        fcf_yield=fcf_yield,
        ev_ebitda=ev_ebitda,
        ev_ebit=ev_ebit,
        pb=pb,
        ps=ps,
        dividend_yield=dividend_yield,
        buyback_yield=buyback_yield,
        shareholder_yield=shareholder_yield,
    )


def strength_metrics(fin, bs, cf, info):
    ebit = gv(fin, ALIASES["ebit"], 0)
    interest_exp = gv(fin, ALIASES["interest_exp"], 0)
    interest_cov = (
        safe_div(ebit, abs(interest_exp))
        if (interest_exp not in (0, np.nan))
        else np.nan
    )
    ebitda = gv(fin, ALIASES["ebitda"], 0)
    total_debt = gv(bs, ALIASES["long_debt"], 0, 0.0) + gv(
        bs, ALIASES["short_debt"], 0, 0.0
    )
    cash = info.get("totalCash") or info.get("cash") or 0.0 if info else 0.0
    net_debt = total_debt - (cash or 0.0)
    net_debt_ebitda = safe_div(net_debt, ebitda)
    equity = gv(bs, ALIASES["equity"], 0)
    debt_equity = safe_div(total_debt, equity)
    return dict(
        interest_coverage=interest_cov,
        net_debt_ebitda=net_debt_ebitda,
        debt_equity=debt_equity,
    )


def collect_fundamentals(ticker: str):
    tk = yf.Ticker(ticker)
    try:
        fin = last_two(tk.financials)
        bs = last_two(tk.balance_sheet)
        cf = last_two(tk.cashflow)
        info = tk.info
    except Exception:
        return {}
    shares_prev = previous_shares_outstanding(ticker)
    row = {}
    row["piotroski"] = compute_piotroski(fin, bs, cf)
    row["altman_z"] = compute_altman(fin, bs, info)
    row.update(quality_metrics(fin, bs, cf))
    row.update(growth_metrics(fin))
    row.update(value_metrics(fin, bs, cf, info, shares_prev))
    row.update(strength_metrics(fin, bs, cf, info))
    return row


def compute_altman(fin, bs, info):
    if any(x is None or x.empty for x in [fin, bs]):
        return np.nan
    WC = gv(bs, ALIASES["current_assets"], 0) - gv(
        bs, ALIASES["current_liabilities"], 0
    )
    TA = gv(bs, ALIASES["total_assets"], 0)
    RE = gv(bs, ALIASES["retained_earnings"], 0)
    EBIT = gv(fin, ALIASES["ebit"], 0)
    TL = gv(bs, ALIASES["total_liabilities"], 0)
    Sales = gv(fin, ALIASES["total_revenue"], 0)
    price = info.get("currentPrice") or info.get("regularMarketPrice") if info else None
    shares = info.get("sharesOutstanding") if info else None
    MVE = price * shares if (price and shares) else np.nan
    if (
        any(np.isnan(x) for x in [WC, TA, RE, EBIT, TL, Sales, MVE])
        or TA <= 0
        or TL <= 0
    ):
        return np.nan
    return (
        1.2 * (WC / TA)
        + 1.4 * (RE / TA)
        + 3.3 * (EBIT / TA)
        + 0.6 * (MVE / TL)
        + 1.0 * (Sales / TA)
    )


def build_price_metrics(
    px: pd.DataFrame, ohlcv: Dict[str, pd.DataFrame], tickers: List[str]
) -> pd.DataFrame:
    rets = px.pct_change().replace([np.inf, -np.inf], np.nan)
    rows = []
    for t in tickers:
        s = px[t].dropna() if t in px.columns else pd.Series(dtype=float)
        r = rets[t].dropna() if t in rets.columns else pd.Series(dtype=float)
        ret_1m = pct_change_price(s, 21)
        ret_3m = pct_change_price(s, 63)
        ret_6m = pct_change_price(s, 126)
        ret_9m = pct_change_price(s, 189)
        ret_12m = pct_change_price(s, 252)
        ret_12m_ex1m = (
            (ret_12m - ret_1m)
            if (not np.isnan(ret_12m) and not np.isnan(ret_1m))
            else np.nan
        )
        r6 = r.tail(126)
        sharpe_6m = sortino_6m = np.nan
        if r6.size >= 60:
            mu = r6.mean()
            sd = r6.std(ddof=0)
            if sd:
                sharpe_6m = (mu / sd) * math.sqrt(252)
            neg = r6[r6 < 0]
            if neg.size > 0:
                dsd = neg.std(ddof=0)
                if dsd:
                    sortino_6m = (mu / dsd) * math.sqrt(252)
        vol_63d = (
            r.tail(63).std(ddof=0) * math.sqrt(252) if r.tail(63).size >= 40 else np.nan
        )
        mdd = max_drawdown(s)
        addv_60d = turnover_60d = spread_proxy = days_to_liq = np.nan
        if t in ohlcv:
            df = ohlcv[t].tail(70)
            if {"Close", "High", "Low", "Volume"}.issubset(df.columns):
                recent = df.tail(60)
                if not recent.empty:
                    addv_60d = (recent["Close"] * recent["Volume"]).mean()
                    spread_proxy = (
                        (recent["High"] - recent["Low"]) / recent["Close"]
                    ).mean()
                    avg_vol = recent["Volume"].mean()
                    info = yf.Ticker(t).info
                    shares = info.get("sharesOutstanding")
                    insider = info.get("heldPercentInsiders") or 0.0
                    float_shares = shares * (1 - insider) if shares else np.nan
                    turnover_60d = safe_div(avg_vol, float_shares)
                    days_to_liq = (
                        safe_div(0.30 * POSITION_DOLLARS, addv_60d)
                        if addv_60d
                        else np.nan
                    )
        rows.append(
            dict(
                ticker=t,
                ret_1m=ret_1m,
                ret_3m=ret_3m,
                ret_6m=ret_6m,
                ret_9m=ret_9m,
                ret_12m_ex1m=ret_12m_ex1m,
                sharpe_6m=sharpe_6m,
                sortino_6m=sortino_6m,
                vol_63d=vol_63d,
                max_drawdown=mdd,
                addv_60d=addv_60d,
                turnover_60d=turnover_60d,
                spread_proxy=spread_proxy,
                days_to_liq=days_to_liq,
            )
        )
    return pd.DataFrame(rows).set_index("ticker")


def linear_scale(x, lo, hi):
    if np.isnan(x):
        return np.nan
    x = min(max(x, lo), hi)
    return 100 * (x - lo) / (hi - lo)


def log_inverted(x, lo, hi):
    if np.isnan(x) or x <= 0:
        return np.nan
    x = min(max(x, lo), hi)
    return 100 * (math.log(hi) - math.log(x)) / (math.log(hi) - math.log(lo))


def accrual_scale(a):
    if np.isnan(a):
        return np.nan
    a = min(max(a, -0.5), 0.5)
    return 100 * (0.5 - (a + 0.5))


def interest_cov_scale(ic):
    if np.isnan(ic) or ic < 0:
        return 0
    ic = min(ic, 40)
    return 100 * (math.log(ic + 1) / math.log(41))


def net_debt_ebitda_scale(x):
    if np.isnan(x):
        return np.nan
    x = min(max(x, -3), 8)
    return 100 * (8 - x) / 11


def debt_equity_scale(x):
    if np.isnan(x):
        return np.nan
    x = min(max(x, 0), 3)
    return 100 * (3 - x) / 3


def turnover_score(t):
    if np.isnan(t):
        return np.nan
    if t < 0.0005:
        return 0
    if t <= 0.01:
        return 100 * (t - 0.0005) / (0.01 - 0.0005)
    if t <= 0.08:
        return 100
    return max(20, 100 * math.exp(-12 * (t - 0.08)))


def spread_score(sp):
    if np.isnan(sp):
        return np.nan
    sp = min(max(sp, 0.002), 0.12)
    return 100 * (0.12 - sp) / 0.118


def days_to_liq_score(d):
    if np.isnan(d):
        return np.nan
    d = min(max(d, 0), 15)
    return 100 * (15 - d) / 15


def addv_score(v):
    if np.isnan(v) or v <= 0:
        return np.nan
    lo, hi = 5e4, 2e9
    v = min(max(v, lo), hi)
    return 100 * (math.log(v) - math.log(lo)) / (math.log(hi) - math.log(lo))


def volatility_score(v):
    if np.isnan(v):
        return np.nan
    v = min(max(v, 0.10), 0.90)
    return 100 * (0.90 - v) / 0.80


def drawdown_score(dd):
    if np.isnan(dd):
        return np.nan
    dd = min(max(dd, -0.85), 0)
    return 100 * (dd + 0.85) / 0.85


def sharpe_score(s):
    if np.isnan(s):
        return np.nan
    s = min(max(s, -2), 5)
    return 100 * (s + 2) / 7


def sortino_score(s):
    if np.isnan(s):
        return np.nan
    s = min(max(s, -2), 6)
    return 100 * (s + 2) / 8


def score_absolute(df: pd.DataFrame) -> pd.DataFrame:
    S = pd.DataFrame(index=df.index)

    S["earnings_yield_score"] = df["earnings_yield"].apply(
        lambda x: linear_scale(x, -0.50, 0.50)
    )
    S["fcf_yield_score"] = df["fcf_yield"].apply(lambda x: linear_scale(x, -0.30, 0.40))
    S["shareholder_yield_score"] = df["shareholder_yield"].apply(
        lambda x: linear_scale(x, -0.20, 0.20)
    )
    S["ev_ebitda_score"] = df["ev_ebitda"].apply(lambda x: log_inverted(x, 2, 45))
    S["ev_ebit_score"] = df["ev_ebit"].apply(lambda x: log_inverted(x, 3, 55))
    S["pb_score"] = df["pb"].apply(lambda x: log_inverted(x, 0.5, 15))
    S["ps_score"] = df["ps"].apply(lambda x: log_inverted(x, 0.7, 20))
    S["value_score"] = S[
        [
            "earnings_yield_score",
            "fcf_yield_score",
            "shareholder_yield_score",
            "ev_ebitda_score",
            "ev_ebit_score",
            "pb_score",
            "ps_score",
        ]
    ].mean(axis=1, skipna=True)

    S["roic_score"] = df["roic"].apply(lambda x: linear_scale(x, -0.10, 0.45))
    S["roe_score"] = df["roe"].apply(lambda x: linear_scale(x, -0.20, 0.65))
    S["gross_margin_score"] = df["gross_margin"].apply(
        lambda x: linear_scale(x, 0, 0.95)
    )
    S["oper_margin_score"] = df["oper_margin"].apply(
        lambda x: linear_scale(x, -0.25, 0.45)
    )
    S["net_margin_score"] = df["net_margin"].apply(
        lambda x: linear_scale(x, -0.35, 0.40)
    )
    S["accruals_score"] = df["accruals"].apply(accrual_scale)
    S["int_coverage_score"] = df["interest_coverage"].apply(interest_cov_scale)
    S["quality_score"] = S[
        [
            "roic_score",
            "gross_margin_score",
            "oper_margin_score",
            "net_margin_score",
            "accruals_score",
            "int_coverage_score",
        ]
    ].mean(axis=1, skipna=True)

    S["altman_score"] = df["altman_z"].apply(lambda x: linear_scale(x, -2, 9))
    S["net_debt_ebitda_score"] = df["net_debt_ebitda"].apply(net_debt_ebitda_scale)
    S["debt_equity_score"] = df["debt_equity"].apply(debt_equity_scale)
    S["financial_strength_score"] = S[
        ["altman_score", "net_debt_ebitda_score", "debt_equity_score"]
    ].mean(axis=1, skipna=True)

    S["rev_growth_score"] = df["revenue_growth"].apply(
        lambda x: linear_scale(x, -0.60, 1.20)
    )
    S["ebitda_growth_score"] = df["ebitda_growth"].apply(
        lambda x: linear_scale(x, -0.80, 1.50)
    )
    S["gm_trend_score"] = df["gross_margin_trend"].apply(
        lambda x: linear_scale(x, -0.12, 0.12)
    )
    S["growth_accel_score"] = df["growth_acceleration"].apply(
        lambda x: linear_scale(x, -0.50, 0.70)
    )
    S["growth_score"] = (
        0.30 * S["rev_growth_score"]
        + 0.30 * S["ebitda_growth_score"]
        + 0.20 * S["gm_trend_score"]
        + 0.20 * S["growth_accel_score"]
    )

    S["ret_1m_score"] = df["ret_1m"].apply(lambda x: linear_scale(x, -0.35, 0.35))
    S["ret_3m_score"] = df["ret_3m"].apply(lambda x: linear_scale(x, -0.50, 0.90))
    S["ret_6m_score"] = df["ret_6m"].apply(lambda x: linear_scale(x, -0.60, 1.40))
    S["ret_9m_score"] = df["ret_9m"].apply(lambda x: linear_scale(x, -0.70, 1.80))
    S["ret_12m_ex1m_score"] = df["ret_12m_ex1m"].apply(
        lambda x: linear_scale(x, -0.70, 1.80)
    )

    def mom_accel(r1m, r3m):
        if np.isnan(r1m) or np.isnan(r3m):
            return np.nan
        return r1m - (r3m / 3.0)

    accel = [
        (
            mom_accel(df.loc[i, "ret_1m"], df.loc[i, "ret_3m"])
            if "ret_3m" in df.columns
            else np.nan
        )
        for i in df.index
    ]
    S["mom_accel_score"] = pd.Series(accel, index=df.index).apply(
        lambda x: linear_scale(x, -0.20, 0.25)
    )

    base_mom = (
        0.35 * S["ret_1m_score"]
        + 0.35 * S["ret_3m_score"]
        + 0.15 * S["ret_6m_score"]
        + 0.10 * S["ret_9m_score"]
        + 0.05 * S["ret_12m_ex1m_score"]
    )
    penalty = (100 - S["ret_1m_score"]) * 0.15
    S["momentum_score"] = (
        base_mom
        - penalty.where(S["ret_1m_score"] < 50, 0)
        + 0.15 * S["mom_accel_score"]
    )

    S["sharpe_score"] = df["sharpe_6m"].apply(sharpe_score)
    S["sortino_score"] = df["sortino_6m"].apply(sortino_score)
    S["vol_score"] = df["vol_63d"].apply(volatility_score)
    S["mdd_score"] = df["max_drawdown"].apply(drawdown_score)
    S["risk_score"] = S[
        ["sharpe_score", "sortino_score", "vol_score", "mdd_score"]
    ].mean(axis=1, skipna=True)

    S["addv_score"] = df["addv_60d"].apply(addv_score)
    S["turnover_score"] = df["turnover_60d"].apply(turnover_score)
    S["spread_score"] = df["spread_proxy"].apply(spread_score)
    S["dtl_score"] = df["days_to_liq"].apply(days_to_liq_score)
    S["liquidity_score"] = (
        0.35 * S["addv_score"]
        + 0.25 * S["turnover_score"]
        + 0.20 * S["spread_score"]
        + 0.20 * S["dtl_score"]
    )

    S["piotroski_score"] = df["piotroski"].apply(
        lambda x: np.nan if np.isnan(x) else (x / 9) * 100
    )

    risk_multiplier = 0.85 + 0.30 * (S["risk_score"] / 100.0)
    S["growth_score_adj"] = S["growth_score"] * risk_multiplier
    S["momentum_score_adj"] = S["momentum_score"] * risk_multiplier

    overall = 0
    for k, w in WEIGHTS.items():
        overall += S[k] * w
    S["overall_score"] = overall
    S.insert(0, "piotroski_raw", df["piotroski"])
    return S.round(2)


def build_fundamentals(universe: Iterable[str]) -> pd.DataFrame:
    rows = []
    for t in universe:
        t = t.upper().strip()
        if not t:
            continue
        data = collect_fundamentals(t)
        data["ticker"] = t
        rows.append(data)
    return pd.DataFrame(rows).set_index("ticker")


def build_dataset(universe: Iterable[str]) -> pd.DataFrame:
    tickers = [t.upper().strip() for t in universe if t and t.strip()]
    tickers = list(dict.fromkeys(tickers))
    prices, ohlcv = download_prices_batch(tickers)
    fundamentals = build_fundamentals(tickers)
    price_metrics = build_price_metrics(prices, ohlcv, tickers)
    return fundamentals.join(price_metrics, how="left")


def load_default_universe() -> List[str]:
    """Return tickers from the combined index universe."""
    syms = set(load_sp500()) | set(load_sp400()) | set(load_russell2000())
    return sorted(syms)


def run_scoring(universe: Iterable[str]):
    merged = build_dataset(universe)
    scores = score_absolute(merged)
    long_df = scores.reset_index().melt(
        id_vars="ticker", var_name="metric", value_name="value"
    )
    compact_cols = [
        c
        for c in [
            "piotroski_raw",
            "value_score",
            "quality_score",
            "financial_strength_score",
            "growth_score_adj",
            "momentum_score_adj",
            "risk_score",
            "liquidity_score",
            "piotroski_score",
            "overall_score",
        ]
        if c in scores.columns
    ]
    compact = scores[compact_cols]
    return dict(wide=scores, long=long_df, compact=compact)


def main(universe: Iterable[str] | None = None):
    """Run scoring for ``universe`` or the default combined universe."""
    if universe is None:
        universe = load_default_universe()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = run_scoring(universe)
    wide_df = result["wide"]
    long_df = result["long"]
    compact_df = result["compact"]
    wide_df.to_csv(OUTPUT_WIDE_CSV)
    long_df.to_csv(OUTPUT_LONG_CSV, index=False)
    compact_df.to_csv(OUTPUT_COMPACT_CSV)
    print("=== Wide (preview) ===")
    print(wide_df.head())
    print("\n=== Compact ===")
    print(compact_df.head())
    print(f"\nSaved: {OUTPUT_WIDE_CSV}, {OUTPUT_LONG_CSV}, {OUTPUT_COMPACT_CSV}")


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
