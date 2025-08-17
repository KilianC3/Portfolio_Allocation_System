from __future__ import annotations

import math
import time
import random
from typing import Iterable, Sequence, Dict, Optional, cast, Any

from service.logger import get_logger

import numpy as np
import pandas as pd
import yfinance as yf

from requests.exceptions import HTTPError as RequestsHTTPError

HTTP_ERRORS: tuple[type[BaseException], ...] = (RequestsHTTPError,)
try:  # yfinance may use curl_cffi under the hood
    from curl_cffi.requests.exceptions import HTTPError as CurlHTTPError  # type: ignore

    HTTP_ERRORS = (RequestsHTTPError, CurlHTTPError)
except Exception:  # pragma: no cover - curl_cffi optional
    pass

log = get_logger(__name__)


def yf_symbol(sym: str) -> str:
    """Return Yahoo Finance compatible ticker."""
    return sym.replace(".", "-")


def _val(df: pd.DataFrame, keys: Sequence[str], idx: int = 0) -> float:
    for k in keys:
        for row in df.index:
            if k.lower() in str(row).lower():
                try:
                    return float(df.loc[row].iloc[idx])
                except Exception:
                    continue
    return math.nan


def _safe_ratio(n: float, d: float) -> float:
    if d == 0 or math.isnan(n) or math.isnan(d):
        return math.nan
    return n / d


def _piotroski(t: yf.Ticker) -> float:
    bs = t.balance_sheet
    fin = t.financials
    cf = t.cashflow
    if bs.shape[1] < 2 or fin.shape[1] < 2 or cf.shape[1] < 2:
        return math.nan
    ni_cur = _val(fin, ["Net Income"], 0)
    ni_prev = _val(fin, ["Net Income"], 1)
    ta_cur = _val(bs, ["Total Assets"], 0)
    ta_prev = _val(bs, ["Total Assets"], 1)
    cfo_cur = _val(cf, ["Operating Cash Flow"], 0)
    cfo_prev = _val(cf, ["Operating Cash Flow"], 1)
    lt_cur = _val(bs, ["Long Term Debt"], 0)
    lt_prev = _val(bs, ["Long Term Debt"], 1)
    ca_cur = _val(bs, ["Current Assets"], 0)
    ca_prev = _val(bs, ["Current Assets"], 1)
    cl_cur = _val(bs, ["Current Liabilities"], 0)
    cl_prev = _val(bs, ["Current Liabilities"], 1)
    shares_cur = _val(bs, ["Ordinary Shares", "Share Issued", "Common Stock"], 0)
    shares_prev = _val(bs, ["Ordinary Shares", "Share Issued", "Common Stock"], 1)
    sales_cur = _val(fin, ["Total Revenue"], 0)
    sales_prev = _val(fin, ["Total Revenue"], 1)
    gp_cur = _val(fin, ["Gross Profit"], 0)
    gp_prev = _val(fin, ["Gross Profit"], 1)

    roa_cur = _safe_ratio(ni_cur, ta_cur)
    roa_prev = _safe_ratio(ni_prev, ta_prev)
    gm_cur = _safe_ratio(gp_cur, sales_cur)
    gm_prev = _safe_ratio(gp_prev, sales_prev)
    at_cur = _safe_ratio(sales_cur, ta_cur)
    at_prev = _safe_ratio(sales_prev, ta_prev)

    score = 0
    score += roa_cur > 0
    score += cfo_cur > 0
    score += (roa_cur - roa_prev) > 0
    score += cfo_cur > ni_cur
    score += _safe_ratio(lt_cur, ta_cur) < _safe_ratio(lt_prev, ta_prev)
    score += _safe_ratio(ca_cur, cl_cur) > _safe_ratio(ca_prev, cl_prev)
    if not math.isnan(shares_cur) and not math.isnan(shares_prev):
        score += shares_cur <= shares_prev
    score += gm_cur > gm_prev
    score += at_cur > at_prev
    return float(score)


def _altman(t: yf.Ticker, info: Dict[str, Any]) -> float:
    bs = t.balance_sheet
    fin = t.financials
    if bs.empty or fin.empty:
        return math.nan
    ca = _val(bs, ["Current Assets"], 0)
    cl = _val(bs, ["Current Liabilities"], 0)
    wc = ca - cl
    ta = _val(bs, ["Total Assets"], 0)
    re = _val(bs, ["Retained Earnings"], 0)
    ebit = _val(fin, ["EBIT"], 0)
    tl = _val(bs, ["Total Liabilities"], 0)
    if math.isnan(tl):
        tl = _val(bs, ["Total Liabilities Net Minority Interest"], 0)
    sales = _val(fin, ["Total Revenue"], 0)
    price = info.get("currentPrice") or info.get("lastPrice")
    shares = info.get("sharesOutstanding") or info.get("shares")
    if not price or not shares or tl == 0 or ta == 0:
        return math.nan
    mve = price * shares
    return (
        1.2 * _safe_ratio(wc, ta)
        + 1.4 * _safe_ratio(re, ta)
        + 3.3 * _safe_ratio(ebit, ta)
        + 0.6 * _safe_ratio(mve, tl)
        + 1.0 * _safe_ratio(sales, ta)
    )


def _roic(t: yf.Ticker) -> float:
    bs = t.balance_sheet
    fin = t.financials
    if bs.shape[1] < 2 or fin.empty:
        return math.nan
    ebit = _val(fin, ["EBIT"], 0)
    tax_rate = _val(fin, ["Tax Rate For Calcs"], 0) / 100
    if math.isnan(tax_rate) or tax_rate <= 0 or tax_rate >= 1:
        tax_rate = 0.21
    nopat = ebit * (1 - tax_rate)
    debt_beg = _val(bs, ["Total Debt"], 1)
    debt_end = _val(bs, ["Total Debt"], 0)
    eq_beg = _val(bs, ["Stockholders Equity", "Total Equity"], 1)
    eq_end = _val(bs, ["Stockholders Equity", "Total Equity"], 0)
    invested = 0.5 * ((debt_beg + eq_beg) + (debt_end + eq_end))
    if invested == 0:
        return math.nan
    return _safe_ratio(nopat, invested)


def _fcf_yield(t: yf.Ticker, info: Dict[str, Any]) -> float:
    cf = t.cashflow
    bs = t.balance_sheet
    if cf.empty or bs.empty:
        return math.nan
    ocf = _val(cf, ["Operating Cash Flow"], 0)
    capex = _val(cf, ["Capital Expenditure"], 0)
    price = info.get("currentPrice") or info.get("lastPrice")
    shares = info.get("sharesOutstanding") or info.get("shares")
    debt = _val(bs, ["Total Debt"], 0)
    cash = _val(
        bs,
        [
            "Cash And Cash Equivalents",
            "Cash Cash Equivalents And Short Term Investments",
        ],
        0,
    )
    if not price or not shares:
        return math.nan
    mkt = price * shares
    ev = mkt + debt - cash
    if ev == 0:
        return math.nan
    return (ocf - capex) / ev


def _beneish(t: yf.Ticker) -> float:
    bs = t.balance_sheet
    fin = t.financials
    cf = t.cashflow
    if bs.shape[1] < 2 or fin.shape[1] < 2 or cf.shape[1] < 2:
        return math.nan
    rec0 = _val(bs, ["Accounts Receivable", "Receivables"], 0)
    rec1 = _val(bs, ["Accounts Receivable", "Receivables"], 1)
    sales0 = _val(fin, ["Total Revenue"], 0)
    sales1 = _val(fin, ["Total Revenue"], 1)
    cogs0 = _val(fin, ["Cost Of Revenue"], 0)
    cogs1 = _val(fin, ["Cost Of Revenue"], 1)
    gp0 = sales0 - cogs0
    gp1 = sales1 - cogs1
    total_assets0 = _val(bs, ["Total Assets"], 0)
    total_assets1 = _val(bs, ["Total Assets"], 1)
    ca0 = _val(bs, ["Current Assets"], 0)
    ca1 = _val(bs, ["Current Assets"], 1)
    ppe0 = _val(bs, ["Net PPE"], 0)
    ppe1 = _val(bs, ["Net PPE"], 1)
    dep0 = _val(cf, ["Depreciation", "Depreciation And Amortization"], 0)
    dep1 = _val(cf, ["Depreciation", "Depreciation And Amortization"], 1)
    sga0 = _val(fin, ["Selling General And Administration"], 0)
    sga1 = _val(fin, ["Selling General And Administration"], 1)
    ni0 = _val(fin, ["Net Income Continuous Operations", "Net Income"], 0)
    ni1 = _val(fin, ["Net Income Continuous Operations", "Net Income"], 1)
    debt0 = _val(bs, ["Total Debt"], 0)
    debt1 = _val(bs, ["Total Debt"], 1)
    lvgi = _safe_ratio(debt0 / total_assets0, debt1 / total_assets1)
    dsri = _safe_ratio(rec0 / sales0, rec1 / sales1)
    gmi = _safe_ratio(gp1 / sales1, gp0 / sales0)
    aqi = _safe_ratio(
        (total_assets0 - ca0 - ppe0) / total_assets0,
        (total_assets1 - ca1 - ppe1) / total_assets1,
    )
    sgi = _safe_ratio(sales0, sales1)
    depi = _safe_ratio(dep1 / (dep1 + ppe1), dep0 / (dep0 + ppe0))
    sgai = _safe_ratio(sga0 / sales0, sga1 / sales1)
    tata = _safe_ratio((ni0 - _val(cf, ["Operating Cash Flow"], 0)), total_assets0)
    if math.isnan(dsri):
        return math.nan
    return (
        -4.84
        + 0.92 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * tata
        - 0.327 * lvgi
    )


def _fetch_info(t: yf.Ticker) -> Dict[str, Any]:
    """Return ticker info with retries and fallbacks."""
    for delay in (0.5, 1.0):
        try:
            return t.get_info()
        except HTTP_ERRORS as e:  # pragma: no cover - network conditions vary
            msg = str(e)
            if any(code in msg for code in ("401", "403", "429")):
                time.sleep(delay + random.random())
                continue
            break
        except Exception:
            break
    try:  # fall back to lightweight fast_info
        fi = t.fast_info
        return {k: getattr(fi, k) for k in dir(fi) if not k.startswith("_")}
    except Exception:
        return {}


def _safe_metric(func, *args):
    try:
        return func(*args)
    except Exception:  # pragma: no cover - network optional
        return math.nan


def compute_fundamental_metrics(symbol: str) -> Dict[str, Optional[float]]:
    """Return fundamental metrics for ``symbol`` computed from statements."""
    t = yf.Ticker(yf_symbol(symbol))
    info = _fetch_info(t)
    if not info:
        log.warning(f"fundamental metrics missing info for {symbol}")
    short_ratio = cast(Optional[float], info.get("shortRatio"))
    if short_ratio is None:
        short_ratio = math.nan
    insider = cast(Optional[float], info.get("heldPercentInsiders"))
    if insider is None:
        insider = math.nan
    metrics = {
        "piotroski": _safe_metric(_piotroski, t),
        "altman": _safe_metric(_altman, t, info),
        "roic": _safe_metric(_roic, t),
        "fcf_yield": _safe_metric(_fcf_yield, t, info),
        "beneish": _safe_metric(_beneish, t),
        "short_ratio": short_ratio,
        "insider_buying": insider,
    }
    return metrics
