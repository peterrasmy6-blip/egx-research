"""
Multi-asset portfolio backtesting and risk analysis.

The backtest walks forward one trading day at a time using only prices dated on
or before that day. There is no vectorised shortcut that peeks at the future,
and rebalancing decisions are made from the state of the portfolio as it stood,
not from what later turned out to work.

Survivorship: securities that stopped trading are retained in the database
rather than removed, so a backtest that includes one sees its real ending, not
a silent gap.

Nothing here recommends a portfolio. It reports what a stated allocation would
have done.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from sqlalchemy import select

from ..models import Price, Dividend, Security
from .analytics import (
    price_series, dividends_between, daily_returns, annualised_volatility,
    max_drawdown, cagr, sharpe_ratio, sortino_ratio, TRADING_DAYS,
)

DEFAULT_COST_RATE = 0.00175

# Imported rather than repeated. Holding the Egyptian risk-free rate in two
# places let them drift apart once already: risk-adjusted measures here were
# still using 22% after the valuation engine was corrected to a sourced 20.5%,
# which shifted every Sharpe ratio by about 0.05.
from .valuation import DEFAULTS as _VAL_DEFAULTS

EGP_RISK_FREE = _VAL_DEFAULTS["risk_free_rate"]


class BacktestError(Exception):
    pass


def _price_map(db, security_id: int, start: date, end: date) -> dict:
    return {p.d: p for p in price_series(db, security_id, start, end)}


def _forward_fill(pmap: dict, days: list[date]) -> dict:
    """
    Carry the last known price across days a security did not trade.

    EGX names suspend or go untraded for stretches; without this a portfolio
    would appear to lose the holding entirely on those days.
    """
    out, last = {}, None
    for d in days:
        if d in pmap:
            last = pmap[d]
        if last is not None:
            out[d] = last
    return out


def backtest(db, holdings: list[dict], start: date, end: date | None = None,
             initial: float = 100_000.0, monthly: float = 0.0,
             rebalance: str = "none", reinvest_dividends: bool = True,
             cost_rate: float = DEFAULT_COST_RATE,
             risk_free: float = EGP_RISK_FREE) -> dict:
    """
    Simulate a weighted portfolio.

    holdings: [{"ticker": "COMI", "weight": 0.4}, ...] - weights are normalised.
    rebalance: none | monthly | quarterly | annual
    """
    if not holdings:
        raise BacktestError("Select at least one security.")
    if initial <= 0 and monthly <= 0:
        raise BacktestError("Enter a starting amount or a monthly amount.")

    end = end or date.today()
    if start >= end:
        raise BacktestError("The start date must be before the end date.")

    total_w = sum(h.get("weight", 0) for h in holdings)
    if total_w <= 0:
        raise BacktestError("Portfolio weights must add up to more than zero.")

    secs = []
    for h in holdings:
        sec = db.scalar(select(Security).where(Security.ticker == h["ticker"].upper()))
        if sec is None:
            raise BacktestError("We do not hold data for '%s'." % h["ticker"])
        secs.append({"sec": sec, "weight": h.get("weight", 0) / total_w})

    # Build the shared trading calendar from securities that actually traded.
    all_days: set[date] = set()
    for s in secs:
        pm = _price_map(db, s["sec"].id, start, end)
        s["pmap"] = pm
        all_days |= set(pm.keys())
    if not all_days:
        raise BacktestError(
            "No price history exists for those securities in that period.")

    days = sorted(all_days)
    # Refuse a window we cannot honestly cover.
    for s in secs:
        first = min(s["pmap"]) if s["pmap"] else None
        if first is None:
            raise BacktestError(
                "%s has no prices in that period." % s["sec"].ticker)
        if (first - days[0]).days > 30:
            raise BacktestError(
                "%s only has prices from %s, which is after your start date. "
                "Choose a later start date or remove it."
                % (s["sec"].ticker, first.isoformat()))
        s["ff"] = _forward_fill(s["pmap"], days)
        s["divs"] = {d.ex_date: d.amount_per_share
                     for d in dividends_between(db, s["sec"].id,
                                                days[0] - timedelta(days=1), days[-1])}
        s["shares"] = 0.0

    # --- initial purchase ---
    cash = 0.0
    contributed = 0.0
    costs_total = 0.0

    def buy(day: date, amount: float):
        nonlocal costs_total
        c = amount * cost_rate
        costs_total += c
        net = amount - c
        for s in secs:
            px = s["ff"].get(day)
            if px and px.close > 0:
                s["shares"] += (net * s["weight"]) / px.close

    if initial > 0:
        buy(days[0], initial)
        contributed += initial

    def portfolio_value(day: date) -> float:
        v = 0.0
        for s in secs:
            px = s["ff"].get(day)
            if px:
                v += s["shares"] * px.close
        return v

    reb_months = {"monthly": 1, "quarterly": 3, "annual": 12}.get(rebalance)
    series = []
    contrib_series = []
    last_month = (days[0].year, days[0].month)
    last_reb = days[0]
    dividends_total = 0.0

    for day in days:
        # dividends paid today
        for s in secs:
            amt = s["divs"].get(day)
            if amt and s["shares"] > 0:
                pay = s["shares"] * amt
                dividends_total += pay
                if reinvest_dividends:
                    px = s["ff"].get(day)
                    if px and px.close > 0:
                        s["shares"] += pay / px.close
                    else:
                        cash += pay
                else:
                    cash += pay

        # monthly contribution on the first trading day of each month
        ym = (day.year, day.month)
        if monthly > 0 and ym != last_month:
            buy(day, monthly)
            contributed += monthly
            last_month = ym

        # rebalance back to target weights
        if reb_months:
            months_since = ((day.year - last_reb.year) * 12
                            + day.month - last_reb.month)
            if months_since >= reb_months:
                v = portfolio_value(day)
                if v > 0:
                    turnover = 0.0
                    for s in secs:
                        px = s["ff"].get(day)
                        if not px or px.close <= 0:
                            continue
                        target_v = v * s["weight"]
                        cur_v = s["shares"] * px.close
                        turnover += abs(target_v - cur_v)
                    # cost applies to the value actually traded (half the sum of
                    # absolute differences is the amount that changes hands)
                    fee = (turnover / 2.0) * cost_rate
                    costs_total += fee
                    v_after = v - fee
                    for s in secs:
                        px = s["ff"].get(day)
                        if px and px.close > 0:
                            s["shares"] = (v_after * s["weight"]) / px.close
                last_reb = day

        series.append((day, portfolio_value(day) + cash))
        contrib_series.append(contributed)

    values = [v for _, v in series]
    final = values[-1]
    profit = final - contributed
    years = (days[-1] - days[0]).days / 365.25

    rets = daily_returns(values)
    vol = annualised_volatility(rets)
    dd = max_drawdown(values)
    cg = cagr(contributed, final, years) if monthly == 0 else None

    # Money-weighted return is the fair measure when money arrives over time.
    twr = _time_weighted_return(series, contrib_series)

    # calendar-year performance
    by_year = {}
    for (d, v) in series:
        by_year.setdefault(d.year, []).append(v)
    yearly = {}
    for y, vs in by_year.items():
        if len(vs) > 1 and vs[0] > 0:
            yearly[y] = round((vs[-1] / vs[0] - 1) * 100, 2)

    recovery = _recovery_days(series, dd) if dd else None

    return {
        "holdings": [{"ticker": s["sec"].ticker, "name": s["sec"].name_en,
                      "weight_pct": round(s["weight"] * 100, 2),
                      "sector": s["sec"].sector} for s in secs],
        "start_date": days[0].isoformat(),
        "end_date": days[-1].isoformat(),
        "years": round(years, 2),
        "trading_days": len(days),
        "initial": initial,
        "monthly": monthly,
        "rebalance": rebalance,
        "reinvest_dividends": reinvest_dividends,

        "total_contributed": round(contributed, 2),
        "final_value": round(final, 2),
        "profit": round(profit, 2),
        "total_return_pct": round(profit / contributed * 100, 2) if contributed else None,
        "cagr_pct": round(cg * 100, 2) if cg is not None else None,
        "time_weighted_return_pct": round(twr * 100, 2) if twr is not None else None,
        "dividends_received": round(dividends_total, 2),
        "transaction_costs": round(costs_total, 2),

        "volatility_pct": round(vol * 100, 2) if vol else None,
        "max_drawdown_pct": round(dd["max_drawdown"] * 100, 2) if dd else None,
        "recovery_days": recovery,
        "sharpe": round(sharpe_ratio(rets, risk_free), 2) if sharpe_ratio(rets, risk_free) else None,
        "sortino": round(sortino_ratio(rets, risk_free), 2) if sortino_ratio(rets, risk_free) else None,
        "risk_free_used_pct": round(risk_free * 100, 1),

        "best_year": max(yearly.items(), key=lambda x: x[1]) if yearly else None,
        "worst_year": min(yearly.items(), key=lambda x: x[1]) if yearly else None,
        "yearly_returns": yearly,

        "series": [{"d": d.isoformat(), "v": round(v, 2), "c": round(c, 2)}
                   for (d, v), c in zip(series, contrib_series)][::max(1, len(series) // 400)],

        "assumptions": [
            "Bought at closing prices; no intraday timing.",
            "Transaction cost of %.3f%% on every purchase and on rebalancing trades."
            % (cost_rate * 100),
            "Dividends %s." % ("reinvested" if reinvest_dividends else "held as cash"),
            "Rebalancing: %s." % (rebalance if rebalance != "none" else "never"),
            "Risk-adjusted measures use an EGP risk-free rate of %.1f%%. This "
            "matters: with Egyptian deposit rates this high, a nominal gain can "
            "still be a poor risk-adjusted result." % (risk_free * 100),
            "No tax applied. Prices on non-trading days carry forward.",
            "Past performance does not indicate future results.",
        ],
    }


def _time_weighted_return(series, contribs) -> float | None:
    """
    Return that strips out the timing of deposits.

    With monthly contributions a simple total return flatters or penalises the
    result depending purely on when money went in, which says nothing about the
    investments themselves.
    """
    if len(series) < 2:
        return None
    factor = 1.0
    prev_v = series[0][1]
    prev_c = contribs[0]
    for i in range(1, len(series)):
        v = series[i][1]
        flow = contribs[i] - prev_c
        base = prev_v + flow
        if base > 0:
            factor *= v / base
        prev_v, prev_c = v, contribs[i]
    years = (series[-1][0] - series[0][0]).days / 365.25
    if years <= 0 or factor <= 0:
        return None
    return factor ** (1 / years) - 1 if years >= 1 else factor - 1


def _recovery_days(series, dd) -> int | None:
    """Days from the worst trough back to the previous peak, or None if never."""
    try:
        peak_v = series[dd["peak_index"]][1]
        trough_i = dd["trough_index"]
        trough_d = series[trough_i][0]
        for i in range(trough_i, len(series)):
            if series[i][1] >= peak_v:
                return (series[i][0] - trough_d).days
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Portfolio composition analysis (descriptive only - never prescriptive)
# ---------------------------------------------------------------------------
def analyse_composition(db, holdings: list[dict]) -> dict:
    """
    Describe what a portfolio is exposed to.

    States facts ("62% sits in banks") and explains why concentration matters
    in general terms. It does not tell anyone what to buy or sell.
    """
    total = sum(h.get("value", 0) for h in holdings)
    if total <= 0:
        raise BacktestError("Portfolio values must be greater than zero.")

    rows, by_sector = [], {}
    for h in holdings:
        sec = db.scalar(select(Security).where(Security.ticker == h["ticker"].upper()))
        if sec is None:
            continue
        w = h["value"] / total
        sector = sec.sector or "Unclassified"
        by_sector[sector] = by_sector.get(sector, 0.0) + w
        rows.append({"ticker": sec.ticker, "name": sec.name_en,
                     "sector": sector, "value": round(h["value"], 2),
                     "weight_pct": round(w * 100, 2)})

    rows.sort(key=lambda r: -r["weight_pct"])
    sectors = sorted(({"sector": k, "weight_pct": round(v * 100, 2)}
                      for k, v in by_sector.items()),
                     key=lambda r: -r["weight_pct"])

    # Herfindahl index: 1/HHI is the "effective number of holdings".
    hhi = sum((r["weight_pct"] / 100) ** 2 for r in rows)
    effective_n = round(1 / hhi, 1) if hhi > 0 else None

    observations = []
    if rows and rows[0]["weight_pct"] >= 30:
        observations.append(
            "%s alone accounts for %.0f%% of this portfolio. When one holding is "
            "this large, the portfolio's result depends heavily on that single "
            "company."
            % (rows[0]["ticker"], rows[0]["weight_pct"]))
    if sectors and sectors[0]["weight_pct"] >= 50:
        observations.append(
            "%.0f%% sits in %s. Companies in the same sector tend to move "
            "together, so a sector-wide event affects most of the portfolio at "
            "once." % (sectors[0]["weight_pct"], sectors[0]["sector"]))
    if effective_n is not None and effective_n < 3:
        observations.append(
            "The portfolio behaves like roughly %.1f equally weighted holdings, "
            "which is a concentrated position." % effective_n)
    if len(rows) >= 8 and effective_n and effective_n > 6:
        observations.append(
            "Holdings are spread fairly evenly across %d securities." % len(rows))
    if not observations:
        observations.append(
            "No single holding or sector dominates this portfolio.")

    return {
        "total_value": round(total, 2),
        "holdings": rows,
        "sectors": sectors,
        "largest_holding_pct": rows[0]["weight_pct"] if rows else None,
        "largest_sector_pct": sectors[0]["weight_pct"] if sectors else None,
        "effective_holdings": effective_n,
        "observations": observations,
        "note": ("These are descriptive observations about what the portfolio "
                 "contains. They are not advice, and they do not take your "
                 "personal circumstances into account."),
    }
