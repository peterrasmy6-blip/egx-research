"""
Forward-looking scenarios and Monte Carlo simulation.

These are NOT predictions. They are arithmetic consequences of assumptions the
user can see and change. The module is deliberately built so that every output
carries the assumptions that produced it, and so that the API cannot return a
projection without them.

Two honesty rules are enforced in code:

  1. Historical volatility is used as the *starting point* for uncertainty, not
     as a claim that the future resembles the past. Where history is too short
     to measure, the simulation refuses rather than inventing a number.
  2. Results are reported in real (inflation-adjusted) terms alongside nominal.
     In a high-inflation economy, a nominal projection alone tells the user
     almost nothing about future purchasing power.
"""
from __future__ import annotations

import math
import random
from datetime import date

from .analytics import (
    price_series, daily_returns, annualised_volatility, TRADING_DAYS,
)

DEFAULT_INFLATION = 0.20
MIN_HISTORY_DAYS = 250          # about one trading year


class ForecastError(Exception):
    pass


def estimate_parameters(db, security_id: int, lookback_years: int = 5) -> dict:
    """
    Measure historical drift and volatility.

    Returned as measurements with their sample size attached, so the caller can
    tell the user how much history is behind the numbers.
    """
    series = price_series(db, security_id)
    if len(series) < MIN_HISTORY_DAYS:
        raise ForecastError(
            "Only %d trading days of history are available. At least %d are "
            "needed before a simulation would mean anything."
            % (len(series), MIN_HISTORY_DAYS))

    cutoff = len(series) - lookback_years * TRADING_DAYS
    window = series[max(0, cutoff):]
    adj = [p.adj_close for p in window]
    rets = daily_returns(adj)
    if len(rets) < MIN_HISTORY_DAYS:
        raise ForecastError("Not enough return history to estimate risk.")

    n = len(rets)
    mean_d = sum(rets) / n
    var_d = sum((r - mean_d) ** 2 for r in rets) / (n - 1)
    sd_d = math.sqrt(var_d)

    return {
        "daily_mean": mean_d,
        "daily_sd": sd_d,
        "annual_return_historical": (1 + mean_d) ** TRADING_DAYS - 1,
        "annual_volatility": sd_d * math.sqrt(TRADING_DAYS),
        "observations": n,
        "years_of_history": round(n / TRADING_DAYS, 1),
        "period_start": window[0].d.isoformat(),
        "period_end": window[-1].d.isoformat(),
    }


# ---------------------------------------------------------------------------
# Deterministic scenarios
# ---------------------------------------------------------------------------
def scenario_projection(initial: float, monthly: float, years: int,
                        annual_returns: dict,
                        inflation: float = DEFAULT_INFLATION,
                        annual_increase: float = 0.0) -> dict:
    """
    Grow a savings plan at fixed assumed rates.

    `annual_returns` is {"conservative": r, "base": r, "optimistic": r}. These
    are inputs chosen by the user, not forecasts produced by the platform.
    """
    if years < 1 or years > 40:
        raise ForecastError("Choose a horizon between 1 and 40 years.")
    if initial <= 0 and monthly <= 0:
        raise ForecastError("Enter a starting amount or a monthly amount.")

    out = {}
    for name, r in annual_returns.items():
        balance = initial
        contributed = initial
        month_r = (1 + r) ** (1 / 12) - 1
        path = []
        contrib = monthly
        for y in range(1, years + 1):
            for _ in range(12):
                balance = balance * (1 + month_r) + contrib
                contributed += contrib
            contrib *= (1 + annual_increase)
            infl_factor = (1 + inflation) ** y
            path.append({
                "year": y,
                "nominal": round(balance, 2),
                "real": round(balance / infl_factor, 2),
                "contributed": round(contributed, 2),
            })
        out[name] = {
            "annual_return_pct": round(r * 100, 2),
            "final_nominal": round(balance, 2),
            "final_real": round(balance / ((1 + inflation) ** years), 2),
            "total_contributed": round(contributed, 2),
            "growth_from_returns": round(balance - contributed, 2),
            "path": path,
        }

    return {
        "type": "scenario",
        "years": years,
        "initial": initial,
        "monthly": monthly,
        "annual_contribution_increase_pct": round(annual_increase * 100, 2),
        "inflation_assumption_pct": round(inflation * 100, 2),
        "scenarios": out,
        "assumptions": [
            "Returns are assumed to be steady every year. Real markets are not "
            "steady - they rise and fall, and the order matters.",
            "Contributions are added at the end of each month.",
            "Inflation of %.1f%% a year is applied to show future purchasing "
            "power." % (inflation * 100),
            "No tax, fees or charges are deducted.",
        ],
        "disclaimer": (
            "These are arithmetic projections of the rates you chose. They are "
            "not forecasts and not a promise of any outcome."),
    }


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------
def monte_carlo(initial: float, monthly: float, years: int,
                annual_return: float, annual_volatility: float,
                simulations: int = 5000,
                inflation: float = DEFAULT_INFLATION,
                target: float | None = None,
                seed: int | None = 42) -> dict:
    """
    Simulate many possible paths using a lognormal monthly return model.

    A fixed default seed makes the same inputs give the same answer, so a user
    who reloads the page does not see different "probabilities" each time.

    The model assumes returns are independent month to month and normally
    distributed in log terms. Real markets have fatter tails and crashes
    cluster, so the true probability of a bad outcome is somewhat higher than
    this model shows. That caveat is returned with the result.
    """
    if simulations < 100 or simulations > 20000:
        raise ForecastError("Choose between 100 and 20,000 simulations.")
    if years < 1 or years > 40:
        raise ForecastError("Choose a horizon between 1 and 40 years.")
    if annual_volatility <= 0:
        raise ForecastError("Volatility must be greater than zero.")

    rng = random.Random(seed)
    months = years * 12

    # Convert annual arithmetic assumptions to lognormal monthly parameters.
    sd_m = annual_volatility / math.sqrt(12)
    mu_m = math.log(1 + annual_return) / 12 - 0.5 * sd_m ** 2

    finals = []
    contributed = initial + monthly * months
    # Keep a handful of representative paths for charting.
    sample_paths = []

    for i in range(simulations):
        bal = initial
        path = [bal] if i < 40 else None
        for m in range(months):
            shock = rng.gauss(mu_m, sd_m)
            bal = bal * math.exp(shock) + monthly
            if path is not None and (m + 1) % 12 == 0:
                path.append(bal)
        finals.append(bal)
        if path is not None:
            sample_paths.append([round(x, 2) for x in path])

    finals.sort()

    def pctile(p):
        idx = min(len(finals) - 1, max(0, int(p * len(finals))))
        return finals[idx]

    infl_factor = (1 + inflation) ** years
    loss_count = sum(1 for f in finals if f < contributed)
    target_count = sum(1 for f in finals if target and f >= target) if target else None

    # The nominal loss probability is close to meaningless in a high-inflation
    # economy: at 20% inflation, merely getting your pounds back is a large real
    # loss. The purchasing-power measure answers "will I be better off?".
    #
    # Both sides must be in the same money. Deflating the final value while
    # comparing it against the raw sum of contributions is a category error --
    # a 5,000 EGP payment made in year 10 is not worth 5,000 in today's terms.
    # Each contribution is therefore discounted back to today before summing.
    real_contributed = initial
    for m in range(1, months + 1):
        real_contributed += monthly / ((1 + inflation) ** (m / 12.0))

    real_loss_count = sum(1 for f in finals if f / infl_factor < real_contributed)

    return {
        "type": "monte_carlo",
        "simulations": simulations,
        "years": years,
        "initial": initial,
        "monthly": monthly,
        "total_contributed": round(contributed, 2),
        "total_contributed_real": round(real_contributed, 2),
        "assumed_annual_return_pct": round(annual_return * 100, 2),
        "assumed_annual_volatility_pct": round(annual_volatility * 100, 2),
        "inflation_assumption_pct": round(inflation * 100, 2),

        "percentiles": {
            "p10": round(pctile(0.10), 2),
            "p25": round(pctile(0.25), 2),
            "median": round(pctile(0.50), 2),
            "p75": round(pctile(0.75), 2),
            "p90": round(pctile(0.90), 2),
        },
        "percentiles_real": {
            "p10": round(pctile(0.10) / infl_factor, 2),
            "median": round(pctile(0.50) / infl_factor, 2),
            "p90": round(pctile(0.90) / infl_factor, 2),
        },
        "probability_of_loss_pct": round(loss_count / simulations * 100, 1),
        "probability_of_real_loss_pct": round(real_loss_count / simulations * 100, 1),
        "real_loss_note": (
            "Compares the final value in today's money against what you paid "
            "in, also expressed in today's money (%s). Both sides are in the "
            "same money, which is the only way the comparison means anything."
            % ("EGP {:,.0f}".format(real_contributed))),
        "target": target,
        "probability_of_target_pct": (round(target_count / simulations * 100, 1)
                                      if target else None),
        "sample_paths": sample_paths[:40],

        "assumptions": [
            "Monthly returns are drawn at random from a bell-shaped "
            "distribution built from the return and volatility you chose.",
            "Each month is assumed independent of the last.",
            "Contributions are added at the end of each month.",
            "Inflation of %.1f%% a year is used for the purchasing-power "
            "figures." % (inflation * 100),
            "The same inputs always produce the same result.",
        ],
        "limitations": [
            "A low chance of nominal loss is not reassurance. At "
            "%.0f%% inflation, simply getting your pounds back is a large loss "
            "in what they can buy - which is why the purchasing-power figure is "
            "shown next to it." % (inflation * 100),
            "Real markets have more extreme days than a bell curve predicts, "
            "and bad months tend to cluster together. The genuine chance of a "
            "poor outcome is therefore somewhat higher than shown here.",
            "The simulation assumes the chosen return and volatility hold for "
            "the whole period. Neither is stable in reality.",
            "This is a model of the assumptions, not a forecast of the market.",
        ],
        "disclaimer": (
            "These probabilities describe the model, not the future. They are "
            "not a prediction and not advice."),
    }
