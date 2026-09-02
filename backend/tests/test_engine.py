"""
Tests for the deterministic financial engine.

These check arithmetic and, just as importantly, that the engine REFUSES to
produce a number when it should not. A wrong figure is worse than a blank.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select as sa_select

from app.db import SessionLocal
from app.models import Security, FinancialFact
from app.engine import analytics as A
from app.engine import scenario as S
from app.engine import fundamentals as F

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


print("\n--- pure maths ---")
check("cagr doubles over 1y", approx(A.cagr(100, 200, 1.0), 1.0))
check("cagr 4x over 2y = 100%/yr", approx(A.cagr(100, 400, 2.0), 1.0))
check("cagr refuses sub-year window", A.cagr(100, 150, 0.5) is None,
      "annualising months overstates wildly")
check("cagr refuses zero start", A.cagr(0, 100, 2.0) is None)
check("cagr refuses negative end", A.cagr(100, -5, 2.0) is None)

dd = A.max_drawdown([100, 120, 60, 90])
check("max drawdown 120->60 = -50%", approx(dd["max_drawdown"], -0.5))
check("drawdown of rising series is 0",
      approx(A.max_drawdown([1, 2, 3, 4])["max_drawdown"], 0.0))
check("drawdown needs 2+ points", A.max_drawdown([5]) is None)

check("volatility refuses short series", A.annualised_volatility([0.01] * 5) is None)
check("zero-variance series has zero vol",
      approx(A.annualised_volatility([0.0] * 60), 0.0))
check("sharpe refuses short series", A.sharpe_ratio([0.01] * 5, 0.20) is None)

r = A.daily_returns([100, 110, 99])
check("daily returns computed", approx(r[0], 0.10) and approx(r[1], -0.10))
check("daily returns skip zero base", len(A.daily_returns([0, 100])) == 0)

print("\n--- real data: lump sum ---")
db = SessionLocal()
comi = A.get_security(db, "COMI")
check("COMI exists in universe", comi is not None)

res = S.lump_sum(db, comi, 100_000, date(2021, 8, 30))
check("shares x exit price == market value",
      approx(res["shares_bought"] * res["exit_price"], res["market_value"], 1.0))
check("final = market value + dividends",
      approx(res["market_value"] + res["dividends_received"], res["final_value"], 0.05))
check("profit = final - invested",
      approx(res["final_value"] - res["amount_invested"], res["profit"], 0.05))
check("total return matches profit",
      approx(res["profit"] / res["amount_invested"] * 100, res["total_return_pct"], 0.05))
check("total return exceeds price-only (dividends paid)",
      res["total_return_pct"] > res["price_only_return_pct"])
check("costs deducted before buying",
      res["shares_bought"] < 100_000 / res["entry_price"])
check("real value below nominal under positive inflation",
      res["real_value"] < res["final_value"])
check("assumptions disclosed", len(res["assumptions"]) >= 4)

wk = S.lump_sum(db, comi, 100_000, date(2021, 8, 28))   # a Saturday
check("weekend entry rolls to next trading day",
      wk["entry_date_adjusted"] and wk["entry_date"] > "2021-08-28")

print("\n--- refusals ---")
try:
    S.lump_sum(db, comi, 100_000, date(1990, 1, 1))
    check("refuses pre-history date", False, "should have raised")
except S.InsufficientData:
    check("refuses pre-history date", True)

try:
    S.lump_sum(db, comi, -50, date(2022, 1, 1))
    check("refuses negative amount", False, "should have raised")
except S.InsufficientData:
    check("refuses negative amount", True)

fw = A.get_security(db, "FWRY")
nodiv = S.lump_sum(db, fw, 50_000, date(2023, 1, 2))
check("zero-dividend stock handled", nodiv["dividends_received"] == 0.0)
# With no dividends the only gap between total and price-only return is the
# purchase commission, so it must match the cost drag almost exactly.
_drag = -S.DEFAULT_COST_RATE * (1 + nodiv["price_only_return_pct"] / 100) * 100
check("zero-dividend gap equals transaction cost drag",
      approx(nodiv["total_return_pct"] - nodiv["price_only_return_pct"], _drag, 0.02),
      "got %.4f expected %.4f" % (
          nodiv["total_return_pct"] - nodiv["price_only_return_pct"], _drag))

try:
    S.lump_sum(db, comi, 100_000, date(2016, 8, 27))
    check("small weekend roll still allowed", True)
except S.InsufficientData as e:
    check("small weekend roll still allowed", False, str(e))

print("\n--- monthly plan ---")
m = S.monthly_plan(db, comi, 5_000, date(2022, 1, 3))
check("contributed = monthly x purchases",
      approx(m["total_contributed"], 5_000 * m["n_purchases"], 1.0))
check("monthly plan bought repeatedly", m["n_purchases"] > 12)
check("monthly final = market + dividends",
      approx(m["market_value"] + m["dividends_received"], m["final_value"], 0.05))
check("no misleading CAGR on staggered contributions", "cagr_pct" not in m)

print("\n--- fundamentals ---")
s = F.summary(db, comi.id)
check("COMI has statements", s["available"])
check("multiple periods stored", s["periods_available"] >= 3)
h = s["history"][0]
check("net margin = profit / revenue",
      approx(h["margins"]["net_margin"],
             h["values"]["net_income"] / h["values"]["revenue"], 1e-9))
check("ROE = profit / equity",
      approx(h["returns"]["roe"],
             h["values"]["net_income"] / h["values"]["total_equity"], 1e-9))
check("bank correctly has no EBITDA (not zero)",
      h["values"]["ebitda"] is None)
check("provenance recorded for revenue", "revenue" in h["sources"])

# A company we genuinely hold no statements for must say so rather than
# reporting zeroes. Chosen from the database rather than named, because the
# list of such companies shrinks every time a new source is added -- this test
# used to name IRON, which now has accounts and turned a passing test red for
# the happiest possible reason.
_no_facts = db.execute(sa_select(Security.id, Security.ticker).where(
    Security.asset_type == "equity",
    Security.listing_status == "listed",
    ~Security.id.in_(sa_select(FinancialFact.security_id))).limit(1)).first()
if _no_facts:
    si = F.summary(db, _no_facts[0])
    check("a company without statements reports unavailable, not zero",
          si.get("available") is False,
          "%s returned %s" % (_no_facts[1], si.get("available")))
else:
    check("a company without statements reports unavailable, not zero", True,
          "every listed company now has statements")

check("safe divide by zero returns None", F._safe_div(10, 0) is None)
check("safe divide by None returns None", F._safe_div(None, 5) is None)

db.close()
print("\n" + "=" * 52)

# --- whose profit is it? ---------------------------------------------------
#
# The source publishes several figures called some variant of "net income".
# Plain "Net Income" includes the share owned by outside investors in
# subsidiaries; "Net Income Common Stockholders" is what belongs to this
# company's own shareholders. Every per-share number on this site rests on the
# second: earnings per share, return on equity, the earnings yield, and the
# profit a valuation discounts.
#
# The alias list had the wrong one first, so CIB's 2025 profit read 82,239m
# against the 61,634m actually attributable to its shareholders -- a third too
# high, carried into its P/E and its return on equity. A second source,
# stockanalysis.com, agrees with the narrower figure to the pound.
print(chr(10) + "--- net income belongs to shareholders ---")

_ni = F.ALIASES["net_income"]
check("the shareholders' figure is preferred over the consolidated one",
      _ni.index("Net Income Common Stockholders") < _ni.index("Net Income"),
      "order is %s" % _ni)
check("...and over the figure that keeps minority interests",
      _ni.index("Net Income Common Stockholders")
      < _ni.index("Net Income Continuous Operations"),
      "order is %s" % _ni)



print("  %d passed, %d failed" % (PASS, FAIL))
print("=" * 52)
sys.exit(1 if FAIL else 0)
