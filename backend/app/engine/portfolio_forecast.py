"""
Forward-looking model for a portfolio the user builds today.

The problem with the obvious approach
-------------------------------------
Applying one assumed return to every holding wastes everything the platform
knows. A bank on 5x earnings with a 4% yield and a loss-making micro-cap should
not carry the same expectation.

The model used instead
----------------------
A building-block decomposition, which is standard practice and, more
importantly, explainable line by line:

    expected return  =  income  +  growth  +  valuation change

  income     the dividend yield the company actually pays
  growth     how fast its earnings have been growing, damped
  valuation  the drift from today's multiple toward a normal one for its sector,
             spread over the holding period

Each block is only used where the company genuinely supports it. A company that
pays no dividend contributes no income block. A loss-making company gets no
earnings-growth block, because growth from a negative base is meaningless. A
bank is never given an EV/EBITDA-based block. The result records which blocks
were used, so the user can see the reasoning rather than a single number.

Shrinkage: why the raw figure is not used directly
--------------------------------------------------
Extrapolating a company's own recent numbers produces absurd expectations --
a company that grew 60% for two years is not going to compound at 60% for five.
So the raw estimate is pulled toward the market-implied return (Egyptian
government yield plus an equity risk premium), and pulled harder when the data
behind it is thin. A stock with five years of statements keeps more of its own
character than one with two.

Risk comes from actual price history: each holding's volatility, and the real
correlations between them, so a portfolio of five banks is correctly shown as
riskier than five companies from different sectors.

None of this is a prediction. It is arithmetic on stated assumptions, and every
output says so.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from .analytics import price_series, daily_returns, annualised_volatility, max_drawdown
from .valuation import DEFAULTS as RATE_DEFAULTS

# Ceilings on each block. Without them a single freak year dominates the answer.
MAX_GROWTH_BLOCK = 0.25          # 25%/yr of earnings growth is already heroic
MAX_VALUATION_BLOCK = 0.10       # re-rating can help, but not without limit
MAX_INCOME_BLOCK = 0.15
MIN_EXPECTED = -0.05
MAX_EXPECTED = 0.60

# How much of its own character a holding keeps, at best.
MAX_SELF_WEIGHT = 0.65

TRADING_DAYS = 252


def market_expected_return() -> float:
    """The return investors currently require: government yield + equity premium."""
    return RATE_DEFAULTS["risk_free_rate"] + RATE_DEFAULTS["equity_risk_premium"]


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# Per-holding expectation
# ---------------------------------------------------------------------------
def expected_return_for(m, sector_median_pe: float | None = None) -> dict:
    """
    Build one holding's expected return from the metrics it actually has.

    `m` is the security's metric snapshot. Returns the figure plus the blocks
    that produced it and the reasons any were skipped.
    """
    blocks: list[dict] = []
    skipped: list[str] = []
    market = market_expected_return()

    # ---- income ----
    dy = getattr(m, "dividend_yield_pct", None)
    if dy is not None and dy > 0:
        v = _clamp(dy / 100.0, 0, MAX_INCOME_BLOCK)
        blocks.append({"name": "Dividend income", "value": v,
                       "detail": "pays %.2f%% a year in cash" % dy})
    else:
        skipped.append("no dividend, so no income contribution")

    # ---- growth ----
    # Prefer the steadier three-year figure over one volatile year.
    g3 = getattr(m, "revenue_cagr_3y_pct", None)
    g1 = getattr(m, "earnings_growth_pct", None)
    roe = getattr(m, "roe_pct", None)
    net_income = getattr(m, "net_income", None)

    if net_income is not None and net_income <= 0:
        skipped.append("loss-making, so earnings growth is not meaningful")
    else:
        cand = [x for x in (g3, g1) if x is not None]
        if cand:
            # The lower of the two, damped: recent growth rarely persists.
            g = min(cand) / 100.0
            damped = _clamp(g * 0.5, -0.05, MAX_GROWTH_BLOCK)
            blocks.append({"name": "Earnings growth", "value": damped,
                           "detail": "grew %.1f%% a year recently, halved here "
                                     "because growth rarely persists at full rate"
                                     % (min(cand))})
        elif roe is not None and roe > 0:
            # Fallback: sustainable growth = ROE x retained share.
            payout = _clamp((dy or 0) / max(roe, 1e-9), 0, 1)
            sg = _clamp((roe / 100.0) * (1 - payout) * 0.5, -0.05, MAX_GROWTH_BLOCK)
            blocks.append({"name": "Reinvested earnings", "value": sg,
                           "detail": "estimated from a %.1f%% return on equity" % roe})
        else:
            skipped.append("no usable growth or profitability history")

    # ---- valuation ----
    pe = getattr(m, "pb", None) and getattr(m, "pe", None)
    pe = getattr(m, "pe", None)
    if pe and sector_median_pe and pe > 0 and sector_median_pe > 0:
        # Closing part of the gap to a normal multiple, spread over five years.
        gap = (sector_median_pe / pe) - 1.0
        annual = _clamp(gap / 5.0, -MAX_VALUATION_BLOCK, MAX_VALUATION_BLOCK)
        if abs(annual) > 0.002:
            blocks.append({
                "name": "Valuation change", "value": annual,
                "detail": ("on %.1fx earnings against a sector norm of %.1fx"
                           % (pe, sector_median_pe))})
    else:
        skipped.append("no comparable sector multiple, so no re-rating assumed")

    raw = sum(b["value"] for b in blocks)

    # ---- shrinkage toward the market ----
    # More evidence -> more of the company's own character is kept.
    periods = getattr(m, "statement_periods", None) or 0
    evidence = _clamp(periods / 5.0, 0.0, 1.0)
    if not blocks:
        evidence = 0.0
    self_weight = MAX_SELF_WEIGHT * evidence
    expected = self_weight * raw + (1 - self_weight) * market
    expected = _clamp(expected, MIN_EXPECTED, MAX_EXPECTED)

    return {
        "expected_return": expected,
        "raw_from_fundamentals": raw if blocks else None,
        "market_anchor": market,
        "self_weight": round(self_weight, 3),
        "blocks": [{**b, "value_pct": round(b["value"] * 100, 2)} for b in blocks],
        "skipped": skipped,
        "basis": ("%d%% from this company's own figures, %d%% from the "
                  "market-wide expected return"
                  % (round(self_weight * 100), round((1 - self_weight) * 100))),
    }


# ---------------------------------------------------------------------------
# Risk: real volatility and real correlation
# ---------------------------------------------------------------------------
def _aligned_returns(db, securities, lookback_days: int = 3 * 365) -> tuple[list, dict]:
    """Daily returns for each holding, aligned on shared trading dates."""
    cutoff = date.today() - timedelta(days=lookback_days)
    series = {}
    for sec in securities:
        rows = price_series(db, sec.id, cutoff)
        series[sec.ticker] = {p.d: p.adj_close for p in rows}

    common = None
    for m in series.values():
        s = set(m)
        common = s if common is None else (common & s)
    days = sorted(common or [])

    rets = {}
    for tk, m in series.items():
        vals = [m[d] for d in days]
        rets[tk] = daily_returns(vals)
    return days, rets


def _covariance(rets: dict) -> tuple[dict, dict]:
    """Annualised volatility per holding and the correlation matrix between them."""
    tickers = list(rets)
    n = min((len(v) for v in rets.values()), default=0)
    if n < 60:
        return {}, {}

    means = {t: sum(rets[t][:n]) / n for t in tickers}
    vol = {}
    for t in tickers:
        var = sum((r - means[t]) ** 2 for r in rets[t][:n]) / (n - 1)
        vol[t] = math.sqrt(var) * math.sqrt(TRADING_DAYS)

    corr = {}
    for a in tickers:
        corr[a] = {}
        for b in tickers:
            if a == b:
                corr[a][b] = 1.0
                continue
            cov = sum((rets[a][i] - means[a]) * (rets[b][i] - means[b])
                      for i in range(n)) / (n - 1)
            sa = math.sqrt(sum((rets[a][i] - means[a]) ** 2 for i in range(n)) / (n - 1))
            sb = math.sqrt(sum((rets[b][i] - means[b]) ** 2 for i in range(n)) / (n - 1))
            corr[a][b] = (cov / (sa * sb)) if sa > 0 and sb > 0 else 0.0
    return vol, corr


def portfolio_risk(weights: dict, vol: dict, corr: dict) -> float | None:
    """
    Portfolio volatility, accounting for how the holdings actually move together.

    This is the point of using real correlations: five banks are not five
    independent bets, and a naive weighted average of volatilities would
    understate that.
    """
    tickers = [t for t in weights if t in vol]
    if not tickers:
        return None
    var = 0.0
    for a in tickers:
        for b in tickers:
            c = corr.get(a, {}).get(b, 1.0 if a == b else 0.0)
            var += weights[a] * weights[b] * vol[a] * vol[b] * c
    return math.sqrt(var) if var > 0 else None
