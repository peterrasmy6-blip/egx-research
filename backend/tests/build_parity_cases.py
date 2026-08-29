"""
Build the parity fixture: every expected value computed by the Python engine.

The JavaScript engine in the browser is then run against these in
`parity_harness.html`. Anything that disagrees beyond tolerance is a defect in
the port, not an acceptable difference — the whole point of the static build is
that moving the calculations into the browser must not change the answers.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.engine import analytics as A
from app.engine import scenario as S
from app.engine import portfolio as P
from app.engine import forecast as F
from app.engine import metrics as M

HERE = os.path.dirname(os.path.abspath(__file__))
SITE_DATA = os.path.join(os.path.dirname(os.path.dirname(HERE)), "site", "data")


def load_company(ticker: str) -> dict:
    """Load the exported company file the browser will actually use."""
    with open(os.path.join(SITE_DATA, "company", "%s.json" % ticker),
              encoding="utf-8") as f:
        return json.load(f)


def build() -> dict:
    db = SessionLocal()
    cases: dict = {}

    # ---------------- statistics ----------------
    vol_input = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01, 0.003, 0.008,
                 -0.012, 0.017, -0.004, 0.009, 0.011, -0.016, 0.002,
                 0.014, -0.007, 0.006, -0.003, 0.012, 0.001, -0.009,
                 0.018, -0.011, 0.004] * 3
    cases["stats"] = {
        "cagr_double": A.cagr(100, 200, 1.0),
        "cagr_subyear": A.cagr(100, 150, 0.5),
        "dd_input": [100, 120, 60, 90],
        "dd_expected": A.max_drawdown([100, 120, 60, 90])["max_drawdown"],
        "vol_input": vol_input,
        "vol_expected": A.annualised_volatility(vol_input),
        "sharpe_expected": A.sharpe_ratio(vol_input, 0.205),
    }

    LUMP_KEYS = ["entry_date", "exit_date", "entry_price", "exit_price",
                 "shares_bought", "shares_final", "market_value",
                 "dividends_received", "final_value", "profit",
                 "total_return_pct", "price_only_return_pct", "cagr_pct",
                 "volatility_pct", "max_drawdown_pct", "real_value",
                 "real_return_pct", "beat_inflation", "transaction_costs",
                 "years_held", "entry_date_adjusted"]

    # ---------------- lump sum ----------------
    lump = []
    for label, ticker, amount, start, opts in [
        ("CIB 5y", "COMI", 100000, date(2021, 8, 30), {}),
        ("CIB 5y, dividends reinvested", "COMI", 100000, date(2021, 8, 30),
         {"reinvest_dividends": True}),
        ("Fawry 3y (no dividends)", "FWRY", 50000, date(2023, 1, 2), {}),
        ("Sewedy 2y", "SWDY", 250000, date(2024, 1, 2), {}),
        ("CIB weekend entry", "COMI", 100000, date(2021, 8, 28), {}),
        ("Telecom 1y, 12% inflation", "ETEL", 75000, date(2025, 8, 4),
         {"inflation_annual": 0.12}),
    ]:
        sec = A.get_security(db, ticker)
        r = S.lump_sum(db, sec, amount, start, **opts)
        lump.append({
            "label": label,
            "company": load_company(ticker),
            "amount": amount,
            "start": start.isoformat(),
            "opts": {"reinvest_dividends": opts.get("reinvest_dividends", False),
                     "inflation_annual": opts.get("inflation_annual",
                                                  S.DEFAULT_INFLATION_ANNUAL)},
            "expect": {k: r[k] for k in LUMP_KEYS},
        })
    cases["lump_sum"] = lump

    # ---------------- monthly plan ----------------
    MONTHLY_KEYS = ["start_date", "exit_date", "n_purchases", "total_contributed",
                    "transaction_costs", "shares_final", "average_cost_per_share",
                    "market_value", "dividends_received", "final_value", "profit",
                    "total_return_pct", "real_value"]
    monthly = []
    for label, ticker, amt, start, opts in [
        ("CIB 5k/month from 2022", "COMI", 5000, date(2022, 1, 3), {}),
        ("Sewedy 10k/month + 100k start", "SWDY", 10000, date(2023, 3, 1),
         {"initial_amount": 100000}),
        ("Fawry 2k/month", "FWRY", 2000, date(2023, 6, 4), {}),
    ]:
        sec = A.get_security(db, ticker)
        r = S.monthly_plan(db, sec, amt, start, **opts)
        monthly.append({
            "label": label,
            "company": load_company(ticker),
            "monthly_amount": amt,
            "start": start.isoformat(),
            "opts": {"initial_amount": opts.get("initial_amount", 0),
                     "inflation_annual": S.DEFAULT_INFLATION_ANNUAL},
            "expect": {k: r[k] for k in MONTHLY_KEYS},
        })
    cases["monthly"] = monthly

    # ---------------- backtest ----------------
    BT_KEYS = ["start_date", "end_date", "trading_days", "total_contributed",
               "final_value", "profit", "total_return_pct", "cagr_pct",
               "time_weighted_return_pct", "dividends_received",
               "transaction_costs", "volatility_pct", "max_drawdown_pct",
               "sharpe", "sortino"]
    bt = []
    for label, holdings, start, opts in [
        ("60/40 CIB+Sewedy, no rebalance",
         [{"ticker": "COMI", "weight": 60}, {"ticker": "SWDY", "weight": 40}],
         date(2021, 1, 4), {}),
        ("50/50 annual rebalance",
         [{"ticker": "COMI", "weight": 50}, {"ticker": "SWDY", "weight": 50}],
         date(2021, 1, 4), {"rebalance": "annual"}),
        ("Four-way, quarterly rebalance, monthly top-up",
         [{"ticker": "COMI", "weight": 25}, {"ticker": "SWDY", "weight": 25},
          {"ticker": "ETEL", "weight": 25}, {"ticker": "ABUK", "weight": 25}],
         date(2022, 1, 3), {"rebalance": "quarterly", "monthly": 5000}),
        ("Single holding, dividends as cash",
         [{"ticker": "COMI", "weight": 100}], date(2020, 1, 2),
         {"reinvest_dividends": False}),
    ]:
        r = P.backtest(db, holdings, start, **opts)
        bt.append({
            "label": label,
            "companies": {h["ticker"]: load_company(h["ticker"]) for h in holdings},
            "holdings": holdings,
            "start": start.isoformat(),
            "opts": {"initial": opts.get("initial", 100000),
                     "monthly": opts.get("monthly", 0),
                     "rebalance": opts.get("rebalance", "none"),
                     "reinvest_dividends": opts.get("reinvest_dividends", True)},
            "expect": {k: r[k] for k in BT_KEYS},
        })
    cases["backtest"] = bt

    # ---------------- projections ----------------
    proj = []
    for label, init, mo, yrs, rets, infl, inc, which in [
        ("100k + 5k/mo, 10y", 100000, 5000, 10,
         {"conservative": 0.08, "base": 0.15, "optimistic": 0.22}, 0.20, 0.0, "base"),
        ("no inflation, flat 10%", 100000, 0, 10,
         {"conservative": 0.05, "base": 0.10, "optimistic": 0.15}, 0.0, 0.0, "base"),
        ("rising contributions", 50000, 3000, 15,
         {"conservative": 0.10, "base": 0.18, "optimistic": 0.25}, 0.18, 0.10, "optimistic"),
    ]:
        r = F.scenario_projection(init, mo, yrs, rets, inflation=infl,
                                  annual_increase=inc)
        proj.append({
            "label": label, "initial": init, "monthly": mo, "years": yrs,
            "returns": rets, "inflation": infl, "increase": inc,
            "scenario": which,
            "expect": {k: r["scenarios"][which][k] for k in
                       ["final_nominal", "final_real", "total_contributed",
                        "growth_from_returns"]},
        })
    cases["projection"] = proj

    # ---------------- portfolio composition ----------------
    with open(os.path.join(SITE_DATA, "metrics.json"), encoding="utf-8") as f:
        metrics_json = json.load(f)
    comp = []
    for label, holdings in [
        ("Two banks", [{"ticker": "COMI", "value": 70000},
                       {"ticker": "HDBK", "value": 30000}]),
        ("Spread of five", [{"ticker": "COMI", "value": 20000},
                            {"ticker": "SWDY", "value": 20000},
                            {"ticker": "ETEL", "value": 20000},
                            {"ticker": "ABUK", "value": 20000},
                            {"ticker": "JUFO", "value": 20000}]),
    ]:
        r = P.analyse_composition(db, holdings)
        comp.append({
            "label": label, "metrics": metrics_json, "holdings": holdings,
            "expect": {"largest_holding_pct": r["largest_holding_pct"],
                       "largest_sector_pct": r["largest_sector_pct"],
                       "effective_holdings": r["effective_holdings"]},
        })
    cases["composition"] = comp

    # ---------------- monte carlo ----------------
    mc = []
    for label, init, mo, yrs, ret, vol, opts in [
        ("100k+5k/mo 10y @26%/31%", 100000, 5000, 10, 0.26, 0.31,
         {"simulations": 8000, "inflation": 0.20}),
        ("500k lump 15y @20%/25%", 500000, 0, 15, 0.20, 0.25,
         {"simulations": 8000, "inflation": 0.18}),
    ]:
        r = F.monte_carlo(init, mo, yrs, ret, vol, **opts)
        mc.append({
            "label": label, "initial": init, "monthly": mo, "years": yrs,
            "annual_return": ret, "annual_volatility": vol,
            "opts": {"simulations": opts["simulations"],
                     "inflation": opts["inflation"]},
            "expect": {"percentiles": r["percentiles"],
                       "total_contributed": r["total_contributed"],
                       "total_contributed_real": r["total_contributed_real"]},
        })
    cases["monte_carlo"] = mc

    db.close()
    return cases


if __name__ == "__main__":
    data = build()
    out = os.path.join(HERE, "parity_cases.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("window.CASES = ")
        json.dump(data, f, separators=(",", ":"), default=str)
        f.write(";\n")
    size = os.path.getsize(out)
    print("wrote %s (%.1f MB)" % (out, size / 1e6))
    print("cases: %d lump sum, %d monthly, %d backtest, %d projection, "
          "%d composition, %d monte carlo"
          % (len(data["lump_sum"]), len(data["monthly"]), len(data["backtest"]),
             len(data["projection"]), len(data["composition"]),
             len(data["monte_carlo"])))
