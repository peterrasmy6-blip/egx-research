"""
Deterministic financial calculations.

Everything in this module is plain arithmetic over stored data. No estimates,
no language model, no guessing. If an input is missing, the output is None and
the caller must say "insufficient data" rather than print a number.

Price conventions (getting this wrong is the classic source of bad numbers):
  * `close`     - split-adjusted, NOT dividend-adjusted. This is the price a
                  buyer actually paid on that day. Use it for share counts and
                  for the price-only return.
  * `adj_close` - split- AND dividend-adjusted. Use it for total return, which
                  is what "how did my money do" actually means.
Dividend amounts from the source are split-adjusted too, so a share count
derived from `close` stays consistent with them over time.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from sqlalchemy import select

from ..models import Security, Price, Dividend

TRADING_DAYS = 252


# --------------------------------------------------------------------------
# Data access
# --------------------------------------------------------------------------
def get_security(db, ticker: str):
    return db.scalar(select(Security).where(Security.ticker == ticker.upper()))


def price_series(db, security_id: int, start: date | None = None,
                 end: date | None = None) -> list[Price]:
    q = select(Price).where(Price.security_id == security_id)
    if start:
        q = q.where(Price.d >= start)
    if end:
        q = q.where(Price.d <= end)
    return list(db.scalars(q.order_by(Price.d)))


def price_on_or_after(db, security_id: int, d: date) -> Price | None:
    """
    First trading day at or after `d`.

    Used for entries: if someone says "I invested on a Friday holiday", the
    realistic answer is that they bought on the next day the market opened.
    """
    return db.scalar(
        select(Price).where(Price.security_id == security_id, Price.d >= d)
        .order_by(Price.d).limit(1))


def price_on_or_before(db, security_id: int, d: date) -> Price | None:
    return db.scalar(
        select(Price).where(Price.security_id == security_id, Price.d <= d)
        .order_by(Price.d.desc()).limit(1))


def latest_price(db, security_id: int) -> Price | None:
    return db.scalar(select(Price).where(Price.security_id == security_id)
                     .order_by(Price.d.desc()).limit(1))


def dividends_between(db, security_id: int, start: date, end: date) -> list[Dividend]:
    return list(db.scalars(
        select(Dividend).where(Dividend.security_id == security_id,
                               Dividend.ex_date > start,
                               Dividend.ex_date <= end)
        .order_by(Dividend.ex_date)))


# --------------------------------------------------------------------------
# Risk / return statistics
# --------------------------------------------------------------------------
def daily_returns(values: list[float]) -> list[float]:
    out = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        if prev and prev > 0:
            out.append(values[i] / prev - 1.0)
    return out


def annualised_volatility(rets: list[float]) -> float | None:
    n = len(rets)
    if n < 20:
        return None                      # too short to mean anything
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS)


def cagr(start_value: float, end_value: float, years: float) -> float | None:
    """Compound annual growth rate. Undefined for sub-year or non-positive values."""
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return None
    if years < 1.0:
        return None                      # annualising a few months overstates wildly
    return (end_value / start_value) ** (1.0 / years) - 1.0


def max_drawdown(values: list[float]) -> dict | None:
    """Worst peak-to-trough fall, and when it happened."""
    if len(values) < 2:
        return None
    peak = values[0]
    worst = 0.0
    peak_i = trough_i = 0
    cur_peak_i = 0
    for i, v in enumerate(values):
        if v > peak:
            peak, cur_peak_i = v, i
        if peak > 0:
            dd = v / peak - 1.0
            if dd < worst:
                worst, peak_i, trough_i = dd, cur_peak_i, i
    return {"max_drawdown": worst, "peak_index": peak_i, "trough_index": trough_i}


def sharpe_ratio(rets: list[float], risk_free_annual: float) -> float | None:
    """
    Sharpe using an Egyptian risk-free rate.

    This matters locally: with EGP deposit rates in the high teens/twenties, a
    nominal 20% equity return can be a *poor* risk-adjusted outcome. A Sharpe
    computed against a 2% rate would flatter EGX results badly.
    """
    n = len(rets)
    if n < 20:
        return None
    mean_a = (sum(rets) / n) * TRADING_DAYS
    vol = annualised_volatility(rets)
    if not vol:
        return None
    return (mean_a - risk_free_annual) / vol


def sortino_ratio(rets: list[float], risk_free_annual: float) -> float | None:
    n = len(rets)
    if n < 20:
        return None
    mean_a = (sum(rets) / n) * TRADING_DAYS
    downside = [r for r in rets if r < 0]
    if len(downside) < 5:
        return None
    dd = math.sqrt(sum(r * r for r in downside) / len(downside)) * math.sqrt(TRADING_DAYS)
    if dd == 0:
        return None
    return (mean_a - risk_free_annual) / dd
