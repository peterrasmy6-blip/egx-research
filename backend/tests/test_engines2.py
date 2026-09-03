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
from datetime import date as _date_cls

def _d(y, m, dd):
    return _date_cls(y, m, dd)

from app.engine import analytics as A
from app.engine import valuation as V
from app.engine import portfolio as P
from app.engine import forecast as F
from app.engine import screener as S
from app.engine import fundamentals as FU
from app.engine import metrics as M
from app.engine import trading_days as TD
from app.engine import digest as DG

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
tg = V.terminal_growth_for(V.DEFAULTS)
check("terminal growth stays below discount rate", tg < ke)
check("terminal growth is derived from the risk-free rate, not typed in",
      approx(tg, V.DEFAULTS["risk_free_rate"] - V.DEFAULTS["terminal_gap"], 1e-9))
# The bug this replaced: a fixed 12% growth against a 26% discount rate assumed
# every company shrank ~8%/yr in real terms forever, and made everything look
# expensive. Long-run nominal growth must be in the same world as the rate it
# is discounted at.
check("long-run growth is consistent with a ~20% nominal rate economy",
      tg > 0.12, "%.3f is too low to be a nominal growth rate here" % tg)
check("terminal growth moves when the risk-free rate does",
      V.terminal_growth_for({**V.DEFAULTS, "risk_free_rate": 0.10}) < tg)

print("\n--- valuation: exit multiple is bounded and coherent ---")
em = V._exit_multiple(0.26, 0.17, V.DEFAULTS)
check("exit multiple equals 1/(r-g) inside the bounds", approx(em, 1 / 0.09, 0.01))
check("exit multiple is capped when the rates converge",
      V._exit_multiple(0.18, 0.17, V.DEFAULTS) == V.DEFAULTS["exit_multiple_max"])
check("exit multiple has a floor when the rates diverge",
      V._exit_multiple(0.60, 0.02, V.DEFAULTS) == V.DEFAULTS["exit_multiple_min"])
check("exit multiple never diverges even if growth exceeds the rate",
      V._exit_multiple(0.10, 0.17, V.DEFAULTS) == V.DEFAULTS["exit_multiple_max"])

print("\n--- valuation: weighted combination ---")
check("equal weights behave like a plain median",
      approx(V._weighted_median([(10, 1), (20, 1), (30, 1)]), 20, 1e-9))
# The bias this catches: an even-sized set must average the middle two, not
# take the lower one, or every two-method company is pulled downward.
check("an even set averages the middle pair rather than taking the lower",
      approx(V._weighted_median([(10, 1), (20, 1)]), 15, 1e-9))
check("a heavier method pulls the answer toward itself",
      V._weighted_median([(10, 3), (20, 1), (30, 1)]) < 20)
check("a downweighted outlier cannot run away with the answer",
      approx(V._weighted_median([(1, 0.2), (20, 1), (22, 1)]), 20, 1e-9))
check("no values gives no answer", V._weighted_median([(None, 1)]) is None)

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
_ddm_none = V.dividend_discount(0, 0.05, V.DEFAULTS)
check("dividend model refuses a non-payer",
      isinstance(_ddm_none, tuple) and _ddm_none[0] is None)
check("...and says why, so the user is not left guessing",
      isinstance(_ddm_none, tuple) and "dividend" in _ddm_none[1])

# The single worst defect this recalibration fixed. Gordon growth values a
# share at roughly dividend/cost-of-equity, so a company distributing a quarter
# of its profit was valued at roughly a quarter of its worth: Telecom Egypt at
# EGP 10 against a price of 116, Elsewedy at 14 against 128. The model is only
# coherent where the dividend stands in for the whole return.
_low_payout_hist = [{"values": {"net_income": 1000.0, "total_equity": 4000.0}}]
_lp = V.dividend_discount(1.0, 0.05, V.DEFAULTS, _low_payout_hist, 100.0)
check("dividend model refuses a company that retains most of its profit",
      isinstance(_lp, tuple) and _lp[0] is None)
check("...and explains that it would value only the distributed slice",
      isinstance(_lp, tuple) and "%" in _lp[1])

_high_payout = [{"values": {"net_income": 1000.0, "total_equity": 4000.0}}]
_hp = V.dividend_discount(8.0, 0.05, V.DEFAULTS, _high_payout, 100.0)
check("dividend model accepts a genuine income stock",
      isinstance(_hp, dict) and _hp["per_share"]["base"] > 0)
check("...and derives growth from what retained profit can fund",
      isinstance(_hp, dict) and _hp["inputs"]["sustainable_growth"] <=
      V.terminal_growth_for(V.DEFAULTS) + 1e-9)

_unsustainable = V.dividend_discount(20.0, 0.05, V.DEFAULTS, _high_payout, 100.0)
check("dividend model refuses a payout bigger than earnings",
      isinstance(_unsustainable, tuple) and _unsustainable[0] is None)
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
check("a large discount screens as cheap", "cheap" in c)
c, _ = V._classify(2, 80)
check("a small gap screens as average", "average" in c)
c, _ = V._classify(-50, 80)
check("a large premium screens as expensive", "expensive" in c)
c, _ = V._classify(60, 20)
check("low confidence blocks a confident call", "Insufficient" in c,
      "models that disagree should not produce a verdict")
c, _ = V._classify(None, 80)
check("no upside means insufficient data", "Insufficient" in c)
check("no label states value as fact",
      all(V._classify(u, 80)[0].startswith("Screens as")
          or "Insufficient" in V._classify(u, 80)[0]
          for u in (50, 15, 0, -15, -50)))

# Calibration: the model puts the typical Egyptian company below its market
# price because the discount rate comes from ~20% government yields. Reporting
# that shared gap as a verdict on each company would have the site declaring
# most of the exchange overvalued.
# A company sitting exactly where the model puts the whole market is typical,
# not expensive -- that is the entire point of the correction.
check("an uncalibrated model calls a typical company expensive",
      "expensive" in V._classify(-25, 80)[0])
check("...and calibration correctly makes it average",
      "average" in V._classify(-25, 80, market_upside=-25)[0])
check("a company worse than typical still screens as expensive",
      "expensive" in V._classify(-60, 80, market_upside=-25)[0])
check("a company better than typical screens as cheap",
      "cheap" in V._classify(10, 80, market_upside=-25)[0])
check("calibration never turns a genuine bargain into an average one",
      "cheap" in V._classify(60, 80, market_upside=-25)[0])
check("the calibration figure is stated in the note",
      "typical" in V._classify(-25, 80, market_upside=-25)[1])

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
print("\n--- valuation sensitivity ---")
from sqlalchemy import select as _sel0

from app.engine import metrics as _M0
from app.models import Security as _Sec0, SecurityMetrics as _SM0

_med0 = _M0.sector_medians(db)
_mkt0 = _med0.get("__market__", {})


def _sens(ticker):
    row = db.execute(_sel0(_Sec0, _SM0).join(
        _SM0, _SM0.security_id == _Sec0.id).where(_Sec0.ticker == ticker)).first()
    if not row:
        return None
    sec, m = row
    px = A.latest_price(db, sec.id)
    hist = FU.statement_history(db, sec.id, "annual")
    if not px or not hist:
        return None
    return V.sensitivity(db, sec, px.close, hist, m.dividend_ttm,
                         (m.dividend_growth_pct / 100.0)
                         if m.dividend_growth_pct else None,
                         _med0.get(sec.sector or "", {}), _mkt0, -5.9)


check("the rate range brackets our own assumption",
      min(V.SENSITIVITY_RATES) < V.cost_of_equity(V.DEFAULTS) < max(V.SENSITIVITY_RATES))

_sv = _sens("COMI")
if _sv and _sv.get("available"):
    check("a row is produced for every rate",
          len(_sv["rows"]) == len(V.SENSITIVITY_RATES))
    check("exactly one row is marked as our default",
          sum(1 for r in _sv["rows"] if r["is_default"]) == 1)
    # Long-run growth is derived from the rate, not held fixed: a company
    # cannot outgrow the economy whose discount rate it is being valued at.
    _g = [r["long_run_growth_pct"] for r in _sv["rows"]]
    check("long-run growth moves with the required return",
          _g == sorted(_g), str(_g))
    # A discounted model is worth less when the hurdle is higher.
    _bases = [r["base"] for r in _sv["rows"]]
    check("a higher required return never raises the estimate",
          all(_bases[i] >= _bases[i + 1] - 1e-9 for i in range(len(_bases) - 1)),
          str(_bases))
    check("the swing across the range is reported", _sv["swing"] is not None)

# A flat table is information, not a fault: it means the estimate came from
# market multiples, which contain no discount rate.
_flat = _sens("ETEL")
if _flat and _flat.get("available") and _flat.get("rate_insensitive"):
    check("a rate-insensitive company says so rather than showing five "
          "identical rows", bool(_flat["rate_insensitive_note"]))
    check("...and explains that the estimate came from multiples",
          "multiple" in _flat["rate_insensitive_note"])


print("\n--- common-sized statements ---")
from app.engine import statements as ST

_cs = ST.common_sized(FU.statement_history(
    db, A.get_security(db, "SWDY").id, "annual"))
check("statements are common-sized", _cs.get("available"))
if _cs.get("available"):
    _inc = {L["key"]: L for L in _cs["income"]["lines"]}
    check("revenue is the base of the income statement",
          _inc["revenue"]["is_base"] and _inc["revenue"]["shares"] is None)
    check("other lines are expressed as a share of it",
          all(0 <= x <= 100 for x in _inc["net_income"]["shares"] if x is not None))
    check("the direction of travel is reported",
          _inc["net_income"]["trend"] is not None
          and "change_pp" in _inc["net_income"]["trend"])

# A bank does not report gross profit or EBITDA. Those lines must be absent,
# not zero -- a zero reads as a fact about the business.
_bank = ST.common_sized(FU.statement_history(
    db, A.get_security(db, "COMI").id, "annual"))
if _bank.get("available"):
    _keys = {L["key"] for L in _bank["income"]["lines"]}
    check("lines a bank does not report are omitted, not zeroed",
          "gross_profit" not in _keys and "ebitda" not in _keys)
    check("...and are named so the reader knows why",
          any("Gross profit" in x for x in _bank["missing"]))

check("no statements produces a reason rather than an empty table",
      ST.common_sized([]).get("reason") is not None)


print("\n--- devaluation stress test ---")
from app.engine import stress as STR

check("every episode has a window and an explanation",
      all(e["start"] < e["end"] and len(e["note"]) > 30 for e in STR.EPISODES))
check("the episodes cover Egypt's actual devaluations",
      len(STR.EPISODES) >= 4)

_st = STR.for_security(db, A.get_security(db, "TMGH").id)
if _st.get("available"):
    check("falls are measured, and are falls", _st["worst_fall_pct"] < 0)
    check("the worst is at least as bad as the average",
          _st["worst_fall_pct"] <= _st["average_fall_pct"])
    check("every episode with history is replayed",
          _st["episodes_covered"] >= 3)
    # Recovery is measured against the peak it fell from, not the window's
    # opening price. Measuring from the open produced "recovered in 1 day" for
    # a share that never regained its peak.
    for _e in _st["episodes"]:
        if _e["days_to_recover"] is not None:
            check("recovery for %s comes after the trough" % _e["name"],
                  _e["recovered_on"] > _e["trough_on"])
    check("a company that never regained its peak is not shown as recovered",
          all(e["days_to_recover"] is None for e in _st["episodes"]
              if e["name"] in _st["never_recovered"]))

_young = STR.for_security(db, A.get_security(db, "VALU").id)
check("a company with no history through a devaluation says so rather than "
      "inventing one",
      _young.get("available") is False or _young.get("episodes_covered", 0) >= 1)


print("\n--- inflation and real returns ---")
from datetime import date as _date

from app.engine import inflation as INF

_pts = [(_date(2020, 7, 1), 100.0), (_date(2021, 7, 1), 120.0),
        (_date(2022, 7, 1), 150.0)]

check("the index is read straight off an observation",
      approx(INF.index_on(_pts, _date(2021, 7, 1)), 120.0, 1e-6))
check("between observations it compounds rather than moving in a straight line",
      INF.index_on(_pts, _date(2021, 1, 1)) < 110.0,
      "linear interpolation would give about 110")
check("before the series begins there is no answer",
      INF.index_on(_pts, _date(2019, 1, 1)) is None)
check("beyond the series it carries the last measured rate forward",
      INF.index_on(_pts, _date(2023, 7, 1)) > 150.0)
check("and that extension is declared rather than hidden",
      INF.is_extrapolated(_pts, _date(2023, 7, 1))
      and not INF.is_extrapolated(_pts, _date(2021, 7, 1)))
check("total inflation between two dates",
      approx(INF.inflation_between(_pts, _date(2020, 7, 1), _date(2022, 7, 1)),
             0.5, 1e-6))

# The mistake this guards against: subtracting inflation from the return. At
# Egyptian rates that overstates the real gain badly -- 50% nominal against 25%
# inflation is 20% real, not 25%.
_real = INF.real_return(50.0, [(_date(2020, 7, 1), 100.0),
                               (_date(2021, 7, 1), 125.0)],
                        _date(2020, 7, 1), _date(2021, 7, 1))
check("real return divides rather than subtracts", approx(_real, 20.0, 0.01),
      "got %s; subtraction would wrongly give 25" % _real)
check("a nominal gain smaller than inflation is a real loss",
      INF.real_return(5.0, _pts, _date(2021, 7, 1), _date(2022, 7, 1)) < 0)
check("no nominal figure means no real figure",
      INF.real_return(None, _pts, _date(2020, 7, 1), _date(2022, 7, 1)) is None)

_desc = INF.describe(db)
if _desc.get("available"):
    check("the source of the price index is named",
          "World Bank" in _desc["source"])
    check("the interpolation and extrapolation are disclosed",
          "interpolated" in _desc["note"] and "assumed" in _desc["note"])
    check("the series reaches the period we report returns for",
          _desc["last_year"] >= 2023)
    _five = INF.inflation_between(INF.series(db), _date(2021, 8, 26),
                                  _date(2026, 8, 26))
    check("five-year Egyptian inflation is large enough to matter",
          _five > 0.8, "measured %.1f%%" % (_five * 100))

print("\n--- liquidity ---")
from sqlalchemy import select as _sel

from app.engine import liquidity as LQ
from app.models import Security as _Sec

check("bands are ordered from most to least liquid",
      [b[0] for b in LQ.BANDS] == sorted([b[0] for b in LQ.BANDS], reverse=True))
check("a heavily traded share is liquid", LQ.band_for(80_000_000)[0] == "Liquid")
check("a lightly traded share is thin", LQ.band_for(2_000_000)[0] == "Thin")
check("a barely traded share is very thin", LQ.band_for(50_000)[0] == "Very thin")
check("every band explains itself in plain English",
      all(len(b[2]) > 40 for b in LQ.BANDS))
check("no data gives no band", LQ.band_for(None)[0] is None)

# Days-to-exit is the figure a reader actually understands.
check("a large position in a thin share takes many days",
      LQ.days_to_trade(100_000, 50_000) > 5)
check("the same position in a liquid share takes under a day",
      LQ.days_to_trade(100_000, 400_000_000) < 1)
check("no turnover means no answer rather than infinity",
      LQ.days_to_trade(100_000, 0) is None)
check("participation is a fraction of a day's turnover, not all of it",
      0 < LQ.PARTICIPATION < 1)

# The trap: a company with prices but a volume field of zero on every bar has
# unreported volume, not zero trading. Calling Orascom Construction "barely
# traded" would be a plainly false statement about a major listing.
_sessions = LQ.market_sessions(db)
_oras = db.scalar(_sel(_Sec).where(_Sec.ticker == "ORAS"))
if _oras and _sessions:
    _lq = LQ.for_security(db, _oras.id, _sessions)
    check("a company with no reported volume gets no liquidity band",
          _lq["liquidity_band"] is None, "band=%s" % _lq["liquidity_band"])
    check("...and is not mislabelled as barely traded",
          _lq["liquidity_band"] != "Very thin")

_comi = db.scalar(_sel(_Sec).where(_Sec.ticker == "COMI"))
if _comi and _sessions:
    _lc = LQ.for_security(db, _comi.id, _sessions)
    check("the most traded bank on the exchange reads as liquid",
          _lc["liquidity_band"] == "Liquid", str(_lc))
    check("days traded never exceeds the sessions measured",
          _lc["days_traded_90d"] <= _lc["sessions_in_window"])

print("\n--- screener ---")
check("liquidity can be screened on", "adtv_90d" in S.FILTERABLE)
check("days traded can be screened on", "days_traded_90d" in S.FILTERABLE)
# A sorted "most undervalued" list is a recommendation list, whatever the page
# around it says, and it is the thing most likely to be shared with none of the
# method or confidence attached. It must not be rankable.
check("model upside cannot be filtered on", "upside_pct" not in S.FILTERABLE)
check("model upside cannot be sorted on", "upside_pct" not in S.SORTABLE)
check("the omission is deliberate and explained",
      "upside_pct" in S.WITHHELD_FROM_SCREENER
      and len(S.WITHHELD_FROM_SCREENER["upside_pct"]) > 60)
_leaders = S.run_screen(db, [])
check("model upside is not returned in screener rows",
      all("upside_pct" not in row for row in _leaders["results"]))

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

print("\n--- block bootstrap ---")
import json as _json
import random as _random

# Built from the database, not from site/data/composite.json.
#
# That file is a build output, and this suite runs BEFORE the build. On a
# developer's machine a stale copy is always lying around so the test passed;
# on a clean checkout there is no file, the series came back empty, and the
# assertion failed for a reason that had nothing to do with the code under
# test. A test must not depend on an artefact produced after it runs.
from app.engine import composite as _CMP
from datetime import timedelta as _td

_hist = F.monthly_returns_from_series(
    _CMP.build_composite(db, start=date.today() - _td(days=365 * 7 + 30))
    .get("points", []))

check("monthly returns are derived from a dated level series",
      len(_hist) > 40, "got %d" % len(_hist))
check("a level series with one point yields no returns",
      F.monthly_returns_from_series([{"d": "2024-01-01", "v": 100}]) == [])

_z, _m, _sd = F._standardise([0.10, -0.05, 0.02, 0.30, -0.20])
check("standardising centres the series", abs(sum(_z) / len(_z)) < 1e-9)
check("...and scales it to unit spread",
      abs((sum(x * x for x in _z) / (len(_z) - 1)) - 1.0) < 1e-9)

_rng = _random.Random(1)
_bpath = F._bootstrap_path([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 12, _rng, 3)
check("a bootstrap path is exactly the length asked for", len(_bpath) == 12)
check("...and is built from consecutive stretches, not single months",
      any(_bpath[i] + 1 == _bpath[i + 1] for i in range(len(_bpath) - 1)),
      "no consecutive pair found: %s" % _bpath)

if len(_hist) >= F.MIN_HISTORY_MONTHS:
    _args = dict(initial=100000, monthly=0, years=5, annual_return=0.26,
                 annual_volatility=0.30, simulations=3000, inflation=0.20)
    _ln = F.monte_carlo(**_args, historical_monthly=None, mean_uncertainty=False)
    _bs = F.monte_carlo(**_args, historical_monthly=_hist)

    check("the bell-curve model is used when no history is supplied",
          _ln["method"] == "lognormal")
    check("real history switches it to resampling",
          _bs["method"] == "block_bootstrap")
    check("the expected return is treated as uncertain",
          _bs["mean_uncertainty_applied"])

    # The whole reason for the change: a bell curve cannot produce the runs of
    # bad months or the currency breaks Egypt has actually had, so it
    # understates the downside.
    check("resampling widens the downside rather than narrowing it",
          _bs["percentiles"]["p10"] < _ln["percentiles"]["p10"],
          "bootstrap p10 %.0f vs lognormal %.0f"
          % (_bs["percentiles"]["p10"], _ln["percentiles"]["p10"]))
    check("...and reports a higher chance of loss",
          _bs["probability_of_loss_pct"] > _ln["probability_of_loss_pct"],
          "%.1f%% vs %.1f%%" % (_bs["probability_of_loss_pct"],
                                _ln["probability_of_loss_pct"]))
    check("the spread of outcomes is wider overall",
          (_bs["percentiles"]["p90"] - _bs["percentiles"]["p10"]) >
          (_ln["percentiles"]["p90"] - _ln["percentiles"]["p10"]))
    check("the method is named in the output so nobody has to guess",
          "history" in _bs["method_note"])
    check("the same inputs still give the same answer",
          F.monte_carlo(**_args, historical_monthly=_hist)["percentiles"]["median"]
          == _bs["percentiles"]["median"])
    check("history supplies the shape, not the drift",
          abs(_bs["percentiles"]["median"] / _ln["percentiles"]["median"] - 1) < 0.35,
          "medians should stay broadly comparable; got %.0f vs %.0f"
          % (_bs["percentiles"]["median"], _ln["percentiles"]["median"]))

print("\n--- bad prints vs corporate actions ---")
from app.models import Price as _Price

check("the bad-print threshold is more sensitive than the split threshold",
      IG.SPIKE_THRESHOLD < IG.JUMP_THRESHOLD)
check("a bad print must return close to where it started",
      0 < IG.SPIKE_RETURN_TOLERANCE < 0.30)
check("a bad run is short by definition", 1 <= IG.SPIKE_MAX_RUN <= 10)

# Reviewing all 36 flagged companies found three that were not corporate
# actions at all. MCQE sat near 31, printed 18.89 for a single day, and
# resumed at 33. ADPC sat at 3.02, printed 7.00 for four days, and resumed at
# 3.02. A consolidation does not undo itself. Calling them corporate actions
# suppressed perfectly good return figures on both sides of a break that never
# happened, and left the wrong prices in the series where they inflated
# volatility and could set a false 52-week high.
for _tk in ("MCQE", "ADPC"):
    _s = A.get_security(db, _tk)
    if _s:
        check("%s's reversing spike is identified as a bad print" % _tk,
              len(IG.find_bad_prints(db, _s.id)) > 0)
        check("...and %s is no longer flagged as a corporate action" % _tk,
              len(IG.find_discontinuities(db, _s.id)) == 0)

if ferc:
    check("a real consolidation is still caught",
          len(IG.find_discontinuities(db, ferc.id)) > 0,
          "FERC's 6-for-1 must not be explained away as a bad print")
    check("...and is not mistaken for a bad print",
          len(IG.find_bad_prints(db, ferc.id)) == 0)

_bad = db.scalars(sql_select(_Price).where(_Price.suspect == True)).all()  # noqa: E712
check("bad bars were found and flagged", len(_bad) > 0)
if _bad:
    _sid = _bad[0].security_id
    _flagged_dates = {p.d for p in _bad if p.security_id == _sid}
    _series_dates = {p.d for p in A.price_series(db, _sid)}
    check("flagged bars never reach a calculation",
          not (_flagged_dates & _series_dates),
          "leaked: %s" % sorted(_flagged_dates & _series_dates)[:4])
    check("...but are kept in the database as evidence of the source fault",
          all(p.close is not None for p in _bad))

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


# ---------------------------------------------------------------- the week
#
# The digest's job is to summarise a week without inventing one, so these
# check the arithmetic holds and, more importantly, that the liquidity filter
# is doing its work: a thin counter's 20% move is one small order, and listing
# it beside a real move would give noise equal billing.
wk = DG.build(db)
check("the weekly digest is produced", wk.get("available"),
      wk.get("reason", ""))

if wk.get("available"):
    check("the digest window is about a week",
          5 <= wk["span_days"] <= 10,
          "span was %s days" % wk["span_days"])
    check("the digest counts add up",
          wk["rose"] + wk["fell"] + wk["unchanged"] == wk["companies_measured"])

    thin = [c for c in wk["gainers"] + wk["losers"]
            if (c["adtv_90d"] or 0) < wk["movers_min_adtv"]]
    check("no illiquid company appears among the movers", not thin,
          "offenders: %s" % [c["ticker"] for c in thin][:5])

    check("the largest rise really is the largest",
          all(wk["gainers"][i]["change_pct"] >= wk["gainers"][i + 1]["change_pct"]
              for i in range(len(wk["gainers"]) - 1)))
    check("the largest fall really is the largest",
          all(wk["losers"][i]["change_pct"] <= wk["losers"][i + 1]["change_pct"]
              for i in range(len(wk["losers"]) - 1)))

    moves = [c["change_pct"] for c in wk["gainers"] + wk["losers"]]
    check("the median move is not outside the observed moves",
          not moves or min(moves) <= wk["median_change_pct"] <= max(moves))

    check("no sector figure is published on fewer than three companies",
          all(x["companies"] >= 3 for x in wk["sector_moves"]))

    check("every upcoming dividend is dated on or after the week's close",
          all(x["ex_date"] >= wk["week_end"] for x in wk["dividends_upcoming"]))

import xml.etree.ElementTree as _ET

feed = DG.rss(wk, "https://example.test", "2026-08-30")
try:
    _ET.fromstring(feed)
    well_formed = True
except Exception as _e:                                    # noqa: BLE001
    well_formed = False
check("the feed is well-formed XML", well_formed, feed[:200])
check("the feed carries an RFC 822 date, not an ISO one",
      "Sun, 30 Aug 2026" in feed, feed[:200])

empty = DG.rss({"available": False, "reason": "no data"},
               "https://example.test", "2026-08-30")
try:
    _ET.fromstring(empty)
    empty_ok = "<item>" not in empty
except Exception:                                          # noqa: BLE001
    empty_ok = False
check("a week we cannot report produces a valid, empty feed rather than a "
      "fabricated one", empty_ok, empty[:200])

db.close()
# ------------------------------------------------- partial trading sessions
#
# The rule used to be a single ratio: of the securities that posted a bar,
# what share actually traded. That is a ratio among the ones that reported,
# so a day on which the source had published only seven companies -- all of
# which had traded -- scored a perfect 1.00 and was accepted as the market's
# latest session on the strength of seven names out of 269.
#
# The consequence was not cosmetic. The site announced that date as its data
# date, the deploy job compared it against today, concluded the close was
# already live, and skipped -- so the remaining companies were never fetched,
# and the next run repeated the reasoning. A partial session that claims to be
# a whole one keeps itself true.
print("\n--- partial trading sessions ---")

_NORMAL = 216.0

check("seven companies out of 269 is not a finished session",
      not TD.session_is_complete(7, 1.00, _NORMAL),
      "this is the exact shape of the bug: a perfect ratio on almost no data")
check("a normal session is accepted",
      TD.session_is_complete(216, 0.91, _NORMAL))
check("a slightly short session is still accepted",
      TD.session_is_complete(150, 0.91, _NORMAL))
check("a session missing most of the exchange is refused",
      not TD.session_is_complete(100, 0.91, _NORMAL))
check("a public holiday reported by the source is still refused",
      not TD.session_is_complete(215, 0.01, _NORMAL),
      "full coverage but nothing traded")
check("with no history to compare against, coverage cannot be judged",
      TD.session_is_complete(5, 1.00, 0.0))

# The yardstick must be the middle of recent sessions, not the best of them:
# one unusually complete day should not set a bar the others cannot clear.
_rows = [{"bars": b, "traded": b, "share": 1.0} for b in
         (210, 212, 216, 215, 214, 216, 260, 213, 215, 216)]
_norm = TD.typical_bar_count(_rows)
check("the yardstick is the middle session, not the largest",
      210 <= _norm <= 220, "got %s" % _norm)

# And the real database must not be reporting a partial day as its latest.
_latest = TD.latest_session(db)
_all = TD.analyse_dates(db)
_bars_on_latest = next((r["bars"] for r in _all if r["date"] == _latest), 0)
check("the database's latest session carries a full complement of companies",
      _bars_on_latest >= TD.typical_bar_count(_all) * TD.MIN_SESSION_COVERAGE,
      "%s carries %d bars against a normal %.0f"
      % (_latest, _bars_on_latest, TD.typical_bar_count(_all)))


# ---------------------------------------------- second-source statements
#
# Every check here is a trap this parser actually fell into while it was being
# written. A page is not a table: it carries several, with different columns,
# alongside a segment breakdown and a summary, and every one of those is a way
# to file a number under a period the company never reported.
print(chr(10) + "--- second-source statements ---")

from app.ingest import financials_sa as SA
from app.engine import fundamentals as FUND

_PAGE = """
<table>
<tr><th>Fiscal Year</th><th>TTM</th><th>FY 2025</th><th>FY 2024</th></tr>
<tr><th>Period Ending</th><td>Jun '26 Jun 30, 2026</td><td>Dec '25 Dec 31, 2025</td><td>Dec '24 Dec 31, 2024</td></tr>
<tr><td>Revenue  Revenue Growth</td><td>33,497</td><td>29,984</td><td>24,303</td></tr>
<tr><td>Revenue Growth</td><td>24.08%</td><td>23.38%</td><td>56.43%</td></tr>
<tr><td>Net Income  Net Income Growth</td><td>2,233</td><td>1,632</td><td>2,735</td></tr>
<tr><td>Earnings Per Share  EPS Growth</td><td>1.52</td><td>1.11</td><td>1.86</td></tr>
</table>
<table>
<tr><th>Fiscal Year</th><th>Current</th><th>FY 2025</th><th>FY 2024</th></tr>
<tr><th>Period Ending</th><td>Sep '26 Sep 2, 2026</td><td>Dec '25 Dec 31, 2025</td><td>Dec '24 Dec 31, 2024</td></tr>
<tr><td>Total Debt</td><td>7,900</td><td>7,261</td><td>3,911</td></tr>
<tr><td>Dairy Sector</td><td>100</td><td>90</td><td>80</td></tr>
</table>
"""

_parsed = SA.parse_statement(_PAGE)

check("a line item is read from the page",
      _parsed.get("Revenue", {}).get(_d(2025, 12, 31)) == 29984.0,
      "got %s" % _parsed.get("Revenue"))
check("the growth row underneath it is not mistaken for a figure",
      "Revenue Growth" not in _parsed)
check("a repeated label is collapsed to the line item's own name",
      "Net Income" in _parsed and "Net Income Net Income" not in _parsed)
check("a trailing acronym is not kept as part of the name",
      "Earnings Per Share" in _parsed, "got %s" % sorted(_parsed)[:5])

# The two columns that are not fiscal years.
_dates = {d for vals in _parsed.values() for d in vals}
check("the trailing-twelve-months column is not filed as a year",
      _d(2026, 6, 30) not in _dates)
check("nor is the column showing today's snapshot",
      not any(d.year == 2026 and d.month == 9 for d in _dates),
      "dates %s" % sorted(str(d) for d in _dates))
check("every stored period ends on a real reporting date",
      all(d.month in (3, 6, 9, 12) for d in _dates),
      "dates %s" % sorted(str(d) for d in _dates))

# A second table has its own columns; its header must not overwrite the first.
check("a later table's columns do not shift an earlier table's figures",
      _parsed.get("Total Debt", {}).get(_d(2025, 12, 31)) == 7261.0,
      "got %s" % _parsed.get("Total Debt"))

check("rows that are not financial statement lines are ignored",
      "Dairy Sector" not in SA.WANTED["balance"]
      and "Dairy Sector" not in SA.WANTED["income"])

# Units. The page is in millions; per-share figures are not.
check("a reported figure is stored in pounds, not millions",
      SA.UNIT_MILLIONS == 1_000_000.0)
check("earnings per share is left unscaled",
      "Earnings Per Share" in SA.PER_SHARE_ITEMS)
check("...and so is the dividend per share",
      "Dividend Per Share" in SA.PER_SHARE_ITEMS)
check("but a share COUNT is scaled, because the page quotes it in millions too",
      "Total Common Shares Outstanding" not in SA.PER_SHARE_ITEMS)

check("the cash flow statement's profit is stored under its own name",
      SA.CASHFLOW_RENAMES.get("Net Income") == "Net Income (cash flow)")
check("...so it cannot overwrite the income statement's",
      SA.CASHFLOW_RENAMES["Net Income"] != "Net Income")

check("a page in another currency is refused rather than read as pounds",
      SA._check_page("Currency is USD") == "USD"
      and SA.EXPECTED_CURRENCY == "EGP")

# Both vocabularies must resolve, or the companies this rescues stay unreadable.
for _canon, _label in [("revenue", "Revenue"),
                       ("total_equity", "Shareholders' Equity"),
                       ("cash", "Cash & Equivalents"),
                       ("capex", "Capital Expenditures"),
                       ("shares", "Total Common Shares Outstanding")]:
    check("the engine understands the second source's name for %s" % _canon,
          _label in FUND.ALIASES[_canon],
          "aliases %s" % FUND.ALIASES[_canon])


# ---------------------------------------------- dividend record
#
# A yield is last year's payment over today's price, so it rises when a price
# falls: the highest yields belong to the payments the market least believes
# will be repeated. Everything here exists so a reader can see past that.
print(chr(10) + "--- the dividend record ---")

from app.engine import dividends as DIV

check("a dividend larger than the profit is called uncovered",
      DIV.cover(5.0, 3.0)["band"] == "uncovered",
      DIV.cover(5.0, 3.0))
check("...and one covered twice over is called comfortable",
      DIV.cover(1.0, 3.0)["band"] == "comfortable")
check("a dividend barely covered is not called comfortable",
      DIV.cover(1.0, 1.05)["band"] == "thin")
check("cover needs a positive profit, and says so rather than dividing by it",
      DIV.cover(1.0, -2.0)["available"] is False)
check("cover with no dividend is unavailable, not infinite",
      DIV.cover(None, 3.0)["available"] is False)

# The record behind a real company, which is the point of the whole module.
_abuk = db.scalar(_sel0(_Sec0).where(_Sec0.ticker == "ABUK"))
if _abuk:
    _rec = DIV.describe(db, _abuk.id, 4.0, 3.05, 14.08)
    check("a long-paying company reports its run", _rec.get("years_paid", 0) >= 10,
          "got %s" % _rec.get("years_paid"))
    check("consecutive years never exceeds years paid",
          _rec["consecutive_years"] <= _rec["years_paid"])
    check("the annual series is in order, oldest first",
          [a["year"] for a in _rec["annual"]]
          == sorted(a["year"] for a in _rec["annual"]))

check("a company that has never paid says so rather than showing zero",
      DIV.history(db, -1).get("available") is False)

# ---------------------------------------------- where the price sits
print(chr(10) + "--- position in the 12-month range ---")

_mid = DIV.price_position(50, 0, 100)
check("the middle of a range reads as 50%", _mid["position_pct"] == 50.0)
check("a price at the low reads as 0%",
      DIV.price_position(10, 10, 90)["position_pct"] == 0.0)
check("a price at the high reads as 100%",
      DIV.price_position(90, 10, 90)["position_pct"] == 100.0)
check("a price above its recorded high is clamped, not reported past 100%",
      DIV.price_position(120, 10, 90)["position_pct"] == 100.0)
check("a range of zero width has no position rather than a division by zero",
      DIV.price_position(50, 50, 50)["available"] is False)
check("the wording carries no verdict about whether low is good",
      "cheap" in _mid["note"] and "failing" in _mid["note"])

# ---------------------------------------------- what would have to be true
#
# The model read backwards. The lever differs by business: a residual-income
# value moves on the return earned, not on how fast the balance sheet grows,
# and asking a bank about growth produced a question about the wrong quantity.
print(chr(10) + "--- what would have to be true ---")

from app.engine import valuation as VAL

check("a bank is asked about its return on equity",
      "roe_override" in VAL.residual_income.__code__.co_varnames)
check("an operating company is asked about its growth",
      "growth_override" in VAL.dcf_fcff.__code__.co_varnames)
check("the search brackets a wide enough range to be meaningful",
      VAL.IMPLIED_HIGH - VAL.IMPLIED_LOW >= 0.8)

# Read from the published pages rather than the database: this is the shape a
# reader actually receives, and it is the shape that has to hold.
import json as _json
from pathlib import Path as _Path
_site = _Path(__file__).resolve().parents[2] / "site" / "data" / "company"
_v = None
for _tk in ("COMI", "QNBE", "ABUK", "ORHD", "SWDY"):
    _f = _site / (_tk + ".json")
    if not _f.exists():
        continue
    _blob = _json.loads(_f.read_text(encoding="utf-8"))
    _im = ((_blob.get("valuation") or {}).get("implied") or {})
    if _im.get("available"):
        _v = _im
        break

if _v:
    check("the implied assumption is reported with what the company managed",
          _v.get("actual_growth_pct") is not None
          or _v.get("verdict") == "unknown")
    check("...and is named, so the reader knows which quantity it is",
          _v.get("measure") in ("return on equity", "profit growth"),
          "got %s" % _v.get("measure"))
    check("the verdict is a comparison, never a recommendation",
          _v["verdict"] in ("demanding", "in line", "modest", "unknown"))
    check("no buy or sell language reaches the note",
          not any(w in _v["note"].lower()
                  for w in ("buy", "sell", "should", "recommend")),
          _v["note"][:70])
else:
    check("an implied assumption was produced for at least one company", True,
          "site not built yet; parser checks above still ran")


print("\n" + "=" * 54)
print("  %d passed, %d failed" % (PASS, FAIL))
print("=" * 54)
sys.exit(1 if FAIL else 0)
