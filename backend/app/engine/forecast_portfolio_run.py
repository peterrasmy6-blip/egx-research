"""
Whole-portfolio forecast orchestration.

Sits on top of `portfolio_forecast`, which supplies the per-holding expected
return and the risk model. This module assembles them into the numbers the page
shows: scenarios, a simulated distribution, and the profit or loss implied.

Kept in a separate module so the modelling decisions stay readable rather than
buried in a single very long function.
"""
from __future__ import annotations

import math
import random

from datetime import date, timedelta

from sqlalchemy import select

from ..models import Security, SecurityMetrics
from . import forecast as forecast_mod
from .metrics import sector_medians
from .portfolio_forecast import (
    expected_return_for, _aligned_returns, _covariance, portfolio_risk,
    MIN_EXPECTED,
)


class ForecastError(Exception):
    pass


def forecast_portfolio(db, holdings: list[dict], initial: float, years: int,
                       monthly: float = 0.0, inflation: float = 0.20,
                       simulations: int = 5000, seed: int = 42) -> dict:
    """
    Model how a portfolio built today might behave over `years`.

    holdings: [{"ticker": "COMI", "weight": 40}, ...] - weights are normalised.
    """
    if not holdings:
        raise ForecastError("Add at least one holding.")
    if years < 1 or years > 30:
        raise ForecastError("Choose a holding period between 1 and 30 years.")
    if initial <= 0 and monthly <= 0:
        raise ForecastError("Enter a starting amount or a monthly amount.")

    total_w = sum(h.get("weight", 0) for h in holdings)
    if total_w <= 0:
        raise ForecastError("Weights must add up to more than zero.")

    medians = sector_medians(db)
    secs, weights, details = [], {}, []

    for h in holdings:
        tk = str(h["ticker"]).upper()
        sec = db.scalar(select(Security).where(Security.ticker == tk))
        if sec is None:
            raise ForecastError("We do not hold data for '%s'." % tk)
        if sec.asset_type == "fund":
            raise ForecastError(
                "%s is a fund. Funds cannot be forecast here, because our free "
                "source publishes only a current value for them and no history "
                "of daily values to measure risk from." % tk)

        m = db.scalar(select(SecurityMetrics)
                      .where(SecurityMetrics.security_id == sec.id))
        if m is None or m.price is None:
            raise ForecastError(
                "We have no usable price history for %s, so it cannot be "
                "included in a forecast." % tk)

        w = h["weight"] / total_w
        weights[tk] = w
        secs.append(sec)

        med = (medians.get(sec.sector or "", {}) or {}).get("pe")
        er = expected_return_for(m, med)
        details.append({
            "ticker": tk, "name": sec.name_en, "sector": sec.sector,
            "weight_pct": round(w * 100, 2),
            "price": m.price,
            "expected_return_pct": round(er["expected_return"] * 100, 2),
            "blocks": er["blocks"],
            "skipped": er["skipped"],
            "basis": er["basis"],
            "volatility_pct": m.volatility_pct,
            "max_drawdown_pct": m.max_drawdown_pct,
            "pe": m.pe, "roe_pct": m.roe_pct,
            "dividend_yield_pct": m.dividend_yield_pct,
            "data_quality": sec.data_quality,
        })

    mu = sum(weights[d["ticker"]] * d["expected_return_pct"] / 100 for d in details)

    # ---- risk from real price history ----
    _, rets = _aligned_returns(db, secs)
    vol, corr = _covariance(rets)
    sigma = portfolio_risk(weights, vol, corr)

    risk_note = None
    if not sigma:
        # Weighted average of individual volatilities ignores correlation and
        # therefore understates the risk of a concentrated portfolio.
        sigma = sum(weights[d["ticker"]] * (d["volatility_pct"] or 30) / 100
                    for d in details) or 0.30
        risk_note = ("There is not enough overlapping price history to measure "
                     "how these holdings move together, so the risk figure is "
                     "an approximation. A portfolio of similar companies is "
                     "probably riskier than it suggests.")

    weighted_avg_vol = sum(weights[t] * vol.get(t, 0) for t in weights) if vol else 0
    diversification = ((1 - sigma / weighted_avg_vol) * 100
                       if weighted_avg_vol > 0 and sigma < weighted_avg_vol else None)

    # ---- simulate ----
    #
    # Shape from real market history, drift from the building blocks above.
    # Independent monthly draws give a world with no crashes -- no runs of bad
    # months and none of the currency breaks Egypt has had several times -- and
    # this is precisely the page where someone asks what could go wrong.
    rng = random.Random(seed)
    months = years * 12
    sd_m = sigma / math.sqrt(12)
    mu_m = math.log(1 + mu) / 12 - 0.5 * sd_m ** 2 if mu > -0.99 else -0.01

    z_pool, sim_method = [], "lognormal"
    hist_months: list[float] = []
    try:
        from .composite import build_composite
        comp = build_composite(db, start=date.today() - timedelta(days=365 * 8))
        if comp.get("available") and comp.get("points"):
            hist_months = forecast_mod.monthly_returns_from_series(comp["points"])
            if len(hist_months) >= forecast_mod.MIN_HISTORY_MONTHS:
                z_pool, _m, _sd = forecast_mod._standardise(hist_months)
                if len(z_pool) >= forecast_mod.MIN_HISTORY_MONTHS:
                    sim_method = "block_bootstrap"
    except Exception:
        pass

    # The expected return is the least precisely known input; treating it as
    # certain narrows the outcome range, always reassuringly.
    mu_se = (sigma / math.sqrt(max(1.0, len(hist_months) / 12.0))) / 12.0         if hist_months else 0.0

    finals, paths = [], []
    contributed = initial + monthly * months
    for i in range(simulations):
        bal = initial
        path = [round(bal, 2)] if i < 40 else None
        mu_path = mu_m + (rng.gauss(0.0, mu_se) if mu_se > 0 else 0.0)
        shocks = (forecast_mod._bootstrap_path(
            z_pool, months, rng, forecast_mod.BLOCK_MONTHS)
            if sim_method == "block_bootstrap" else None)
        for k in range(months):
            shock = (mu_path + sd_m * shocks[k]) if shocks is not None                 else rng.gauss(mu_path, sd_m)
            bal = bal * math.exp(shock) + monthly
            if path is not None and (k + 1) % 12 == 0:
                path.append(round(bal, 2))
        finals.append(bal)
        if path is not None:
            paths.append(path)
    finals.sort()

    def pctile(p):
        return finals[min(len(finals) - 1, max(0, int(p * len(finals))))]

    infl_factor = (1 + inflation) ** years
    real_contributed = initial + sum(
        monthly / ((1 + inflation) ** (k / 12.0)) for k in range(1, months + 1))

    def path_at(rate):
        bal, out = initial, []
        mr = (1 + rate) ** (1 / 12) - 1
        for y in range(1, years + 1):
            for _ in range(12):
                bal = bal * (1 + mr) + monthly
            out.append({"year": y, "value": round(bal, 2),
                        "real": round(bal / ((1 + inflation) ** y), 2)})
        return out

    # Scenario spread comes from the portfolio's own volatility, so a risky
    # portfolio shows a genuinely wider cone than a steady one.
    conservative = max(MIN_EXPECTED, mu - sigma * 0.75)
    optimistic = mu + sigma * 0.75

    worst_hist = min((d["max_drawdown_pct"] for d in details
                      if d["max_drawdown_pct"] is not None), default=None)

    median_final = pctile(0.50)

    return {
        "holdings": details,
        "years": years, "initial": initial, "monthly": monthly,
        "total_contributed": round(contributed, 2),
        "total_contributed_real": round(real_contributed, 2),

        "expected_return_pct": round(mu * 100, 2),
        "volatility_pct": round(sigma * 100, 2),
        "diversification_benefit_pct": (round(diversification, 1)
                                        if diversification else None),
        "risk_note": risk_note,
        "correlations": ({a: {b: round(v, 2) for b, v in row.items()}
                          for a, row in corr.items()} if corr else None),

        "scenarios": {
            "conservative": {"annual_return_pct": round(conservative * 100, 2),
                             "final": round(path_at(conservative)[-1]["value"], 2),
                             "path": path_at(conservative)},
            "base": {"annual_return_pct": round(mu * 100, 2),
                     "final": round(path_at(mu)[-1]["value"], 2),
                     "path": path_at(mu)},
            "optimistic": {"annual_return_pct": round(optimistic * 100, 2),
                           "final": round(path_at(optimistic)[-1]["value"], 2),
                           "path": path_at(optimistic)},
        },

        "percentiles": {"p10": round(pctile(0.10), 2), "p25": round(pctile(0.25), 2),
                        "median": round(median_final, 2),
                        "p75": round(pctile(0.75), 2), "p90": round(pctile(0.90), 2)},
        "percentiles_real": {"p10": round(pctile(0.10) / infl_factor, 2),
                             "median": round(median_final / infl_factor, 2),
                             "p90": round(pctile(0.90) / infl_factor, 2)},
        "projected_value": round(median_final, 2),
        "projected_profit": round(median_final - contributed, 2),
        "projected_profit_pct": (round((median_final / contributed - 1) * 100, 2)
                                 if contributed else None),
        "probability_of_loss_pct": round(
            sum(1 for f in finals if f < contributed) / simulations * 100, 1),
        "probability_of_real_loss_pct": round(
            sum(1 for f in finals if f / infl_factor < real_contributed)
            / simulations * 100, 1),
        "worst_historical_drawdown_pct": worst_hist,
        "sample_paths": paths[:40],
        "simulations": simulations,
        "simulation_method": sim_method,
        "simulation_note": (
            "Monthly moves are resampled from real Egyptian market history in "
            "six-month stretches, so runs of bad months and the fat tails a "
            "bell curve misses are preserved."
            if sim_method == "block_bootstrap" else
            "Monthly moves are drawn from a bell curve; not enough market "
            "history was available to resample real ones."),
        "inflation_assumption_pct": round(inflation * 100, 2),

        "method": (
            "Each holding's expected return is built from what it actually "
            "reports - the dividend it pays, how fast its earnings have grown, "
            "and how its valuation compares with its sector - then pulled "
            "toward the market-wide expected return so recent form is not "
            "projected forever. Risk uses each holding's real volatility and "
            "the real correlations between them."),
        "assumptions": [
            "Expected returns are estimates built from past figures, not forecasts.",
            "Recent earnings growth is halved, because it rarely persists at full rate.",
            "Valuation is assumed to drift toward the sector norm over five years.",
            "Risk is measured from up to three years of daily prices.",
            "Returns are treated as independent month to month; real markets "
            "have runs of bad months, so the true chance of a poor outcome is "
            "somewhat higher than shown.",
            "Inflation of %.1f%% a year is used for purchasing-power figures."
            % (inflation * 100),
            "No tax, dealing costs or rebalancing are included.",
        ],
        "disclaimer": (
            "This is a model, not a prediction. It shows what the stated "
            "assumptions imply, and those assumptions can be wrong. Real "
            "results will differ, possibly by a wide margin. Nothing here is "
            "advice or a recommendation to buy anything."),
    }
