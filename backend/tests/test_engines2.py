"""
Tests for the valuation, portfolio, forecast and screener engines.

As with the first suite, these check both that correct answers are produced and
that the engines REFUSE to answer when they cannot do so honestly.
"""
import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.engine import analytics as A
from app.engine import valuation as V
from app.engine import portfolio as P
from app.engine import forecast as F
from app.engine import screener as S
from app.engine import fundamentals as FU
from app.engine import metrics as M

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS  %s" % name)
    else:
        FAIL += 1
        print("  FAIL  %s  %s" % (name, detail))


def approx(a, b, tol=0.01):
    return a is not None and b is not None and abs(a - b) <= tol


db = SessionLocal()

# ---------------------------------------------------------------- valuation
print("\n--- valuation: discount rates ---")
ke = V.cost_of_equity(V.DEFAULTS)
check("cost of equity = risk-free + premium", approx(ke, 0.26, 0.001))
check("Egyptian discount rate is high, not a developed-market default", ke > 0.20,
      "a 8-10%% rate would roughly double every valuation")
check("terminal growth stays below discount rate",
      V.DEFAULTS["terminal_growth"] < ke)

w = V.wacc(V.DEFAULTS, equity=1000.0, debt=1000.0)
check("wacc sits below cost of equity when debt is present", w < ke)
check("wacc falls back to cost of equity with no debt info",
      approx(V.wacc(V.DEFAULTS, None, None), ke, 1e-9))

print("\n--- valuation: growth guards ---")
hist_neg = [{"values": {"revenue": 100}}, {"values": {"revenue": 50}},
            {"values": {"revenue": -10}}]
check("growth from a negative base returns None",
      V.historical_growth(hist_neg, "revenue") is None)
check("growth needs at least 3 periods",
      V.historical_growth([{"values": {"revenue": 100}}], "revenue") is None)
h3 = [{"values": {"revenue": 400}}, {"values": {"revenue": 200}},
      {"values": {"revenue": 100}}]
check("compound growth computed correctly",
      approx(V.historical_growth(h3, "revenue"), 1.0, 0.001))
check("extreme growth is clamped", V._bounded_growth(5.0, 0.12) <= 0.45)
check("missing growth falls back to terminal",
      approx(V._bounded_growth(None, 0.12), 0.12))

print("\n--- valuation: refusals ---")
bad = [{"values": {"free_cash_flow": -500, "total_equity": 100,
                   "total_debt": 0, "shares": 10}}]
check("DCF refuses negative free cash flow",
      V.dcf_fcff(bad, 10, 0, V.DEFAULTS) is None)
check("DCF refuses unknown share count",
      V.dcf_fcff([{"values": {"free_cash_flow": 100}}], None, 0, V.DEFAULTS) is None)
check("residual income refuses negative equity",
      V.residual_income([{"values": {"total_equity": -50, "net_income": 10}}],
                        10, V.DEFAULTS) is None)
check("dividend model refuses a non-payer",
      V.dividend_discount(0, 0.05, V.DEFAULTS) is None)
check("relative multiple refuses with no peer benchmark",
      V.relative_multiple([{"values": {"net_income": 100, "shares": 10}}],
                          10, 50, "pe", None) is None)

print("\n--- valuation: method selection by business type ---")
bank = V.choose_methods("Banks", [{}], True)
indus = V.choose_methods("Industrials", [{}], True)
check("banks are not valued on free cash flow", "dcf" not in bank,
      "for a bank, borrowing is raw material, not financing")
check("banks use residual income", "residual_income" in bank)
check("industrial companies do use cash flow", "dcf" in indus)
check("bank rationale explains the choice",
      "bank" in V.valuation_rationale("Banks").lower())

print("\n--- valuation: classification honesty ---")
c, _ = V._classify(45, 80)
check("large discount classified as potentially undervalued", "undervalued" in c)
c, _ = V._classify(2, 80)
check("small gap classified as fairly valued", "fairly" in c)
c, _ = V._classify(-50, 80)
check("large premium classified as potentially overvalued", "overvalued" in c)
c, _ = V._classify(60, 20)
check("low confidence blocks a confident call", "Insufficient" in c,
      "models that disagree should not produce a verdict")
c, _ = V._classify(None, 80)
check("no upside means insufficient data", "Insufficient" in c)
check("every classification is hedged with 'potentially'",
      all("Potentially" in V._classify(u, 80)[0] or "Insufficient" in V._classify(u, 80)[0]
          for u in (50, 15, 0, -15, -50)))

conf, reasons = V._confidence([{"per_share": {"base": 100}}], None, [{}], [("x", "y")])
check("single method lowers confidence", conf < 55)
conf2, _ = V._confidence(
    [{"per_share": {"base": 100}}, {"per_share": {"base": 102}},
     {"per_share": {"base": 98}}], 0.05, [{}] * 5, [])
check("agreeing methods raise confidence", conf2 > conf)
conf3, _ = V._confidence(
    [{"per_share": {"base": 100}}, {"per_share": {"base": 300}}], 2.0, [{}] * 5, [])
check("disagreeing methods lower confidence", conf3 < conf2)

print("\n--- valuation: real company ---")
comi = A.get_security(db, "COMI")
hist = FU.statement_history(db, comi.id, "annual")
last = A.latest_price(db, comi.id)
meds = M.sector_medians(db)
res = V.value_security(db, comi, last.close, hist, 6.0, 0.10,
                       meds.get("Banks", {}))
check("CIB valuation produced", res.get("available"))
if res.get("available"):
    check("bear <= base <= bull", res["bear"] <= res["base"] <= res["bull"],
          "%s %s %s" % (res["bear"], res["base"], res["bull"]))
    check("multiple methods used for a bank", len(res["methods"]) >= 2)
    check("assumptions returned with the answer", "assumptions" in res)
    check("disclaimer attached", "not advice" in res["disclaimer"])
    check("no free-cash-flow model applied to a bank",
          not any("cash flow" in m["method"].lower() for m in res["methods"]))

# ---------------------------------------------------------------- backtest
print("\n--- backtest ---")
bt = P.backtest(db, [{"ticker": "COMI", "weight": 60},
                     {"ticker": "SWDY", "weight": 40}],
                date(2021, 1, 4), initial=100000)
check("weights normalise to 100%",
      approx(sum(h["weight_pct"] for h in bt["holdings"]), 100.0, 0.1))
check("final value is positive", bt["final_value"] > 0)
check("total return matches profit and contributions",
      approx(bt["profit"] / bt["total_contributed"] * 100,
             bt["total_return_pct"], 0.05))
check("transaction costs were charged", bt["transaction_costs"] > 0)
check("risk-free rate disclosed with Sharpe", bt["risk_free_used_pct"] > 15,
      "an Egyptian Sharpe against a 2%% rate would flatter results badly")
check("drawdown is negative or zero", bt["max_drawdown_pct"] <= 0)
check("series returned for charting", len(bt["series"]) > 10)
check("assumptions disclosed", len(bt["assumptions"]) >= 5)

bt_reb = P.backtest(db, [{"ticker": "COMI", "weight": 50},
                         {"ticker": "SWDY", "weight": 50}],
                    date(2021, 1, 4), initial=100000, rebalance="annual")
check("rebalancing costs more than never rebalancing",
      bt_reb["transaction_costs"] > bt["transaction_costs"])

bt_dca = P.backtest(db, [{"ticker": "COMI", "weight": 100}],
                    date(2022, 1, 3), initial=0, monthly=5000)
check("monthly contributions accumulate", bt_dca["total_contributed"] > 100000)
check("time-weighted return reported for staggered money",
      bt_dca["time_weighted_return_pct"] is not None)
check("no plain CAGR when money arrived over time",
      bt_dca["cagr_pct"] is None,
      "a single growth rate would misrepresent staggered contributions")

print("\n--- backtest refusals ---")
for label, fn in [
    ("empty holdings", lambda: P.backtest(db, [], date(2022, 1, 1))),
    ("zero weights", lambda: P.backtest(db, [{"ticker": "COMI", "weight": 0}],
                                        date(2022, 1, 1))),
    ("unknown ticker", lambda: P.backtest(db, [{"ticker": "ZZZZ", "weight": 1}],
                                          date(2022, 1, 1))),
    ("start after end", lambda: P.backtest(db, [{"ticker": "COMI", "weight": 1}],
                                           date(2025, 1, 1), date(2024, 1, 1))),
    ("no money", lambda: P.backtest(db, [{"ticker": "COMI", "weight": 1}],
                                    date(2022, 1, 1), initial=0, monthly=0)),
]:
    try:
        fn()
        check("refuses %s" % label, False, "should have raised")
    except P.BacktestError:
        check("refuses %s" % label, True)

# ---------------------------------------------------------------- portfolio
print("\n--- portfolio composition ---")
comp = P.analyse_composition(db, [{"ticker": "COMI", "value": 70000},
                                  {"ticker": "HDBK", "value": 30000}])
check("weights sum to 100",
      approx(sum(h["weight_pct"] for h in comp["holdings"]), 100.0, 0.1))
check("concentration observed", any("COMI" in o for o in comp["observations"]))
check("sector concentration observed",
      any("Banks" in o for o in comp["observations"]))
check("effective holdings below actual count when concentrated",
      comp["effective_holdings"] < 2)
check("output is descriptive, not prescriptive",
      "not advice" in comp["note"])
check("no buy/sell language in observations",
      not any(w in " ".join(comp["observations"]).lower()
              for w in ["you should", "sell ", "buy ", "recommend"]),
      "the platform describes; it does not instruct")

# ---------------------------------------------------------------- forecast
print("\n--- forecast: scenarios ---")
proj = F.scenario_projection(100000, 5000, 10,
                             {"conservative": 0.08, "base": 0.15, "optimistic": 0.22})
check("optimistic beats base beats conservative",
      proj["scenarios"]["optimistic"]["final_nominal"] >
      proj["scenarios"]["base"]["final_nominal"] >
      proj["scenarios"]["conservative"]["final_nominal"])
check("real value below nominal under inflation",
      proj["scenarios"]["base"]["final_real"] <
      proj["scenarios"]["base"]["final_nominal"])
check("contributions tracked separately from growth",
      approx(proj["scenarios"]["base"]["total_contributed"]
             + proj["scenarios"]["base"]["growth_from_returns"],
             proj["scenarios"]["base"]["final_nominal"], 1.0))
check("path has one entry per year", len(proj["scenarios"]["base"]["path"]) == 10)
check("labelled as scenario not prediction",
      "not forecasts" in proj["disclaimer"] or "not a" in proj["disclaimer"])

# Compound arithmetic sanity: no contributions, 10% for 10 years.
flat = F.scenario_projection(100000, 0, 10, {"base": 0.10}, inflation=0.0)
check("compounding maths correct (100k at 10% for 10y ~= 259k)",
      approx(flat["scenarios"]["base"]["final_nominal"], 259374.25, 500),
      str(flat["scenarios"]["base"]["final_nominal"]))

for label, fn in [
    ("zero horizon", lambda: F.scenario_projection(1000, 0, 0, {"base": 0.1})),
    ("no money", lambda: F.scenario_projection(0, 0, 10, {"base": 0.1})),
]:
    try:
        fn(); check("refuses %s" % label, False, "should have raised")
    except F.ForecastError:
        check("refuses %s" % label, True)

print("\n--- forecast: monte carlo ---")
mc = F.monte_carlo(100000, 5000, 10, 0.15, 0.30, simulations=2000)
p = mc["percentiles"]
check("percentiles are ordered",
      p["p10"] <= p["p25"] <= p["median"] <= p["p75"] <= p["p90"])
check("outcome spread is wide under 30% volatility",
      p["p90"] > p["p10"] * 1.5)
check("probability of loss is a percentage",
      0 <= mc["probability_of_loss_pct"] <= 100)
check("real values below nominal",
      mc["percentiles_real"]["median"] < p["median"])
check("limitations stated, including fat tails",
      any("extreme" in l.lower() or "cluster" in l.lower() for l in mc["limitations"]))
check("labelled as model output not prediction",
      "not a prediction" in mc["disclaimer"])

mc2 = F.monte_carlo(100000, 5000, 10, 0.15, 0.30, simulations=2000)
check("same inputs give the same answer",
      mc["percentiles"]["median"] == mc2["percentiles"]["median"],
      "a reloaded page must not show different probabilities")

mct = F.monte_carlo(100000, 0, 5, 0.15, 0.25, simulations=2000, target=1000000)
check("unreachable target gets a low probability",
      mct["probability_of_target_pct"] < 5,
      "100k reaching 1m in 5 years should be near-impossible at 15%")

for label, fn in [
    ("too many simulations", lambda: F.monte_carlo(1000, 0, 5, .1, .2, simulations=999999)),
    ("zero volatility", lambda: F.monte_carlo(1000, 0, 5, .1, 0)),
    ("absurd horizon", lambda: F.monte_carlo(1000, 0, 99, .1, .2)),
]:
    try:
        fn(); check("refuses %s" % label, False, "should have raised")
    except F.ForecastError:
        check("refuses %s" % label, True)

print("\n--- forecast: parameter estimation ---")
try:
    par = F.estimate_parameters(db, comi.id)
    check("volatility measured from real history", par["annual_volatility"] > 0)
    check("sample size reported", par["observations"] > 250)
    check("measurement window reported", "period_start" in par)
except F.ForecastError as e:
    check("parameter estimation", False, str(e))

# ---------------------------------------------------------------- screener
print("\n--- screener ---")
r = S.run_screen(db, [{"field": "roe_pct", "op": "gte", "value": 15}])
check("screen returns a count", "count" in r)
check("companies missing the metric are excluded and counted",
      r["skipped_missing_data"] >= 0 and "skipped_missing_data" in r)
check("every result actually passes the filter",
      all(x["roe_pct"] >= 15 for x in r["results"] if x["roe_pct"] is not None))
check("missing data is never treated as zero",
      all(x["roe_pct"] is not None for x in r["results"]))
r2 = S.run_screen(db, [{"field": "pe", "op": "lte", "value": 8}])
check("less-than filter works",
      all(x["pe"] <= 8 for x in r2["results"] if x["pe"] is not None))
r3 = S.run_screen(db, [])
check("no filters returns the universe", r3["count"] > 50)

print("\n--- comparison ---")
try:
    cmp = S.compare(db, ["COMI", "HDBK"])
    check("comparison table built", len(cmp["table"]) > 8)
    check("leaders identified per measure",
          any(row["leader"] for row in cmp["table"]))
    check("comparison refuses to name an overall winner",
          "which measures matter" in cmp["note"].lower())
    check("no advice language in observations",
          not any(w in " ".join(cmp["observations"]).lower()
                  for w in ["you should", "recommend", "best buy"]))
except ValueError as e:
    check("comparison", False, str(e))

for label, fn in [
    ("one company", lambda: S.compare(db, ["COMI"])),
    ("too many companies", lambda: S.compare(db, ["A"] * 8)),
    ("unknown ticker", lambda: S.compare(db, ["COMI", "ZZZZ"])),
]:
    try:
        fn(); check("refuses %s" % label, False, "should have raised")
    except ValueError:
        check("refuses %s" % label, True)

# ------------------------------------------------- integrity & real returns
print("\n--- price integrity ---")
from app.engine import integrity as IG
from app.models import SecurityMetrics as SM
from sqlalchemy import select as sql_select

check("consolidation named correctly", "consolidation" in IG._describe(6.0))
check("split named correctly", "split" in IG._describe(1 / 5.0))
check("threshold sits well above EGX daily limits", IG.JUMP_THRESHOLD > 0.25,
      "EGX caps daily moves near 10-20%, so a 60% threshold flags corporate "
      "actions without catching real volatility")

check("window spanning a break is refused",
      not IG.return_is_trustworthy("2025-09-10", date(2024, 1, 1), date(2026, 1, 1)))
check("window after a break is allowed",
      IG.return_is_trustworthy("2025-09-10", date(2025, 10, 1), date(2026, 1, 1)))
check("clean series is always trustworthy",
      IG.return_is_trustworthy(None, date(2015, 1, 1), date(2026, 1, 1)))

ferc = A.get_security(db, "FERC")
if ferc:
    a = IG.assess_security(db, ferc)
    check("FERC's unadjusted consolidation is caught", not a["clean"],
          "9.22 -> 97.57 overnight cannot be genuine trading")
    row = db.scalar(sql_select(SM).where(SM.security_id == ferc.id))
    if row:
        check("the fabricated long-term return is not published",
              row.ret_1y is None,
              "publishing +805% because a 6-for-1 consolidation was never "
              "applied backwards would be fiction")

print("\n--- monte carlo: purchasing power ---")
mcr = F.monte_carlo(100000, 5000, 10, 0.26, 0.31, simulations=1500, inflation=0.20)
check("contributions are also expressed in today's money",
      mcr["total_contributed_real"] < mcr["total_contributed"],
      "money paid in later is worth less today")
check("real loss probability exceeds nominal loss probability",
      mcr["probability_of_real_loss_pct"] > mcr["probability_of_loss_pct"],
      "at 20% inflation, getting your pounds back is still a real loss")
check("comparison is like-for-like, not deflated-vs-nominal",
      "same money" in mcr["real_loss_note"])

mc0 = F.monte_carlo(100000, 0, 10, 0.15, 0.25, simulations=1500, inflation=0.0)
check("with no inflation, real and nominal loss agree",
      approx(mc0["probability_of_real_loss_pct"],
             mc0["probability_of_loss_pct"], 0.1))
check("with no inflation, contributions are unchanged",
      approx(mc0["total_contributed_real"], mc0["total_contributed"], 1.0))
check("inflation caveat present in limitations",
      any("inflation" in l.lower() for l in mcr["limitations"]))

print("\n--- units / currency consistency ---")
# Several EGX companies have a dollar-quoted share class alongside the pound
# one. Dividing a dollar price by pound earnings produced "undervalued by
# 2,934%" before this guard existed.
faita = A.get_security(db, "FAITA")
fait = A.get_security(db, "FAIT")
if faita and fait:
    mf = db.scalar(sql_select(SM).where(SM.security_id == faita.id))
    mg = db.scalar(sql_select(SM).where(SM.security_id == fait.id))
    if mf and mg:
        check("dollar share class flagged as unit-mismatched", bool(mf.units_suspect))
        check("its per-share figures are withheld",
              mf.pe is None and mf.pb is None,
              "a P/E of 0.15 is a currency error, not a bargain")
        check("no fair value published for it", mf.fair_value_base is None)
        check("the pound share class is unaffected",
              not mg.units_suspect and mg.pe is not None)
        check("the pound class has a sane P/E", 1 < (mg.pe or 0) < 100,
              "got %s" % mg.pe)

rows_all = db.execute(sql_select(SM)).scalars().all()
bad_pe = [r for r in rows_all if r.pe is not None and r.pe < 1.0]
check("no company is published with a P/E below 1", not bad_pe,
      "offenders: %s" % [r.security_id for r in bad_pe][:5])
bad_pb = [r for r in rows_all if r.pb is not None and r.pb < 0.10]
check("no company is published with a P/B below 0.10", not bad_pb,
      "offenders: %s" % [r.security_id for r in bad_pb][:5])

unreliable = [r for r in rows_all
              if r.valuation_class == "Insufficient reliable data"
              and r.upside_pct is not None]
check("no upside figure is stored where we refuse to classify", not unreliable,
      "the screener must not rank an estimate we will not stand behind")

db.close()
print("\n" + "=" * 54)
print("  %d passed, %d failed" % (PASS, FAIL))
print("=" * 54)
sys.exit(1 if FAIL else 0)
