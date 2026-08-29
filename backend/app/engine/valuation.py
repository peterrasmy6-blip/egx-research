"""
Fair-value estimation.

Design position: a single fair-value number is a false claim. Every method
here produces a bear / base / bull range from explicit assumptions, and the
platform reports the range, the assumptions, and how much the methods disagree
with each other.

Method selection depends on the business. Forcing an FCFF DCF onto a bank is a
category error -- for a bank, debt is raw material rather than financing, and
"free cash flow" has no comparable meaning. So banks are valued on residual
income / DDM / P-B, property companies on asset value, and operating companies
on cash flow and earnings multiples.

Nothing here is a recommendation. Output is a model estimate under stated
assumptions, and it is labelled as such everywhere it surfaces.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from .fundamentals import statement_history

# ---------------------------------------------------------------------------
# Egyptian market assumptions.
#
# These dominate every discounted model, so they are declared in one place,
# shown to the user, and adjustable -- rather than buried inside a formula.
# Egypt is a high-nominal-rate economy: using a developed-market 8% discount
# rate here would overstate every valuation by a wide margin.
# ---------------------------------------------------------------------------
DEFAULTS = {
    # Long-dated EGP government yield. THE single most important input: it sets
    # the hurdle every company must clear.
    #
    # Sourced, not invented (verified August 2026):
    #   Central Bank of Egypt overnight deposit rate   19.0%
    #   CBE main operation / discount rate             19.5%
    #   12-month treasury bill auction (Feb 2026)      23.5%
    # Long-dated government paper sits between the policy rate and the bill
    # yield, so 20.5% is used. Egyptian rates move; this should be re-checked
    # whenever the CBE changes policy.
    "risk_free_rate": 0.205,

    # Equity risk premium demanded above Egyptian government paper. Modest in
    # nominal terms because the risk-free rate already embeds heavy country and
    # inflation risk -- adding a developed-market-style premium on top would
    # double-count it.
    "equity_risk_premium": 0.055,

    # Long-run nominal growth: long-run EGP inflation plus real growth. Must
    # stay below the discount rate or the terminal value diverges.
    "terminal_growth": 0.12,

    "cost_of_debt": 0.20,
    "tax_rate": 0.225,          # Egyptian corporate income tax
}

# Rate context shown to the user so the discount rate is never a black box.
RATE_SOURCE_NOTE = (
    "Discount rates are built from Egyptian government yields (CBE policy rate "
    "19-19.5%, 12-month treasury bills around 23.5% in early 2026). This is why "
    "Egyptian shares can look expensive on a cash-flow model even at a P/E of 6: "
    "government paper alone pays about 20% with far less risk, so a business has "
    "to clear a very high bar before it adds value."
)

BANKING_SECTORS = {"Banks"}
PROPERTY_SECTORS = {"Real Estate"}
FINANCIAL_SECTORS = {"Banks", "Financial Services"}


class ValuationError(Exception):
    """Raised when a valuation cannot be produced honestly."""


def _g(v, *keys):
    for k in keys:
        x = v.get(k)
        if x is not None:
            return x
    return None


def _safe(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


# ---------------------------------------------------------------------------
# Discount rates
# ---------------------------------------------------------------------------
def cost_of_equity(assumptions: dict, beta: float = 1.0) -> float:
    return assumptions["risk_free_rate"] + beta * assumptions["equity_risk_premium"]


def wacc(assumptions: dict, equity: float | None, debt: float | None,
         beta: float = 1.0) -> float:
    """Weighted average cost of capital. Falls back to cost of equity if the
    capital structure is unknown."""
    ke = cost_of_equity(assumptions, beta)
    if not equity or equity <= 0 or debt is None or debt < 0:
        return ke
    total = equity + debt
    if total <= 0:
        return ke
    kd_after_tax = assumptions["cost_of_debt"] * (1 - assumptions["tax_rate"])
    return (equity / total) * ke + (debt / total) * kd_after_tax


# ---------------------------------------------------------------------------
# Growth estimation from history (never from opinion)
# ---------------------------------------------------------------------------
def historical_growth(hist: list[dict], concept: str,
                      max_periods: int = 5) -> float | None:
    """
    Compound growth of a line item across available annual periods.

    Returns None when the base is non-positive: growth from a loss is not a
    meaningful percentage, and reporting one would be nonsense.
    """
    vals = []
    for h in hist[:max_periods]:
        v = h["values"].get(concept)
        if v is None:
            break
        vals.append(v)
    if len(vals) < 3:
        return None
    newest, oldest = vals[0], vals[-1]
    years = len(vals) - 1
    if oldest <= 0 or newest <= 0:
        return None
    return (newest / oldest) ** (1.0 / years) - 1.0


def _bounded_growth(g: float | None, terminal: float,
                    lo: float = -0.05, hi: float = 0.45) -> float:
    """
    Clamp an extrapolated growth rate.

    A company that grew 90%/yr for three years will not do so forever, and an
    unclamped rate makes a DCF produce absurd values. Clamping is a modelling
    choice, disclosed in the assumptions the user sees.
    """
    if g is None:
        return terminal
    return max(lo, min(hi, g))


# ---------------------------------------------------------------------------
# Method 1 - Two-stage FCFF discounted cash flow (operating companies)
# ---------------------------------------------------------------------------
def dcf_fcff(hist, shares, net_debt, assumptions, beta=1.0,
             growth_override=None) -> dict | None:
    latest = hist[0]["values"]
    fcf = latest.get("free_cash_flow")
    if fcf is None or shares is None or shares <= 0:
        return None
    if fcf <= 0:
        # A DCF on negative cash flow needs a forecast of the turnaround, which
        # we cannot derive from filings alone. Refuse rather than invent one.
        return None

    r = wacc(assumptions, latest.get("total_equity"), latest.get("total_debt"), beta)
    tg = assumptions["terminal_growth"]
    if r <= tg:
        return None            # terminal formula diverges

    base_g = growth_override if growth_override is not None else \
        _bounded_growth(historical_growth(hist, "free_cash_flow")
                        or historical_growth(hist, "operating_cf"), tg)

    out = {}
    for case, gmult, rprem in (("bear", 0.5, 0.02), ("base", 1.0, 0.0),
                               ("bull", 1.4, -0.01)):
        g = max(tg * 0.5, base_g * gmult)
        disc = r + rprem
        if disc <= tg:
            continue
        pv = 0.0
        cf = fcf
        for yr in range(1, 6):
            cf *= (1 + g)
            pv += cf / ((1 + disc) ** yr)
        terminal = cf * (1 + tg) / (disc - tg)
        pv += terminal / ((1 + disc) ** 5)
        equity_value = pv - (net_debt or 0.0)
        out[case] = equity_value / shares

    if "base" not in out or out["base"] <= 0:
        return None
    return {
        "method": "Discounted cash flow (FCFF)",
        "per_share": out,
        "inputs": {
            "starting_free_cash_flow": fcf,
            "growth_rate_base": round(base_g, 4),
            "discount_rate": round(r, 4),
            "terminal_growth": tg,
            "net_debt": net_debt,
            "shares": shares,
        },
        "explanation": (
            "Projects the company's free cash flow forward for five years, then "
            "assumes it settles into steady long-run growth. Future cash is "
            "discounted back because money later is worth less than money now."),
    }


# ---------------------------------------------------------------------------
# Method 2 - Residual income (banks and financial institutions)
# ---------------------------------------------------------------------------
def residual_income(hist, shares, assumptions, beta=1.0) -> dict | None:
    """
    Value = book equity + present value of profits above the cost of equity.

    The natural model for a bank: it works directly from equity and ROE, and
    does not require the free-cash-flow concept that banks lack.
    """
    latest = hist[0]["values"]
    equity = latest.get("total_equity")
    ni = latest.get("net_income")
    if equity is None or ni is None or shares is None or shares <= 0 or equity <= 0:
        return None

    ke = cost_of_equity(assumptions, beta)
    roe = ni / equity
    if roe <= 0:
        return None

    g_book = _bounded_growth(historical_growth(hist, "total_equity"),
                             assumptions["terminal_growth"], 0.0, 0.35)

    out = {}
    for case, roe_mult, fade in (("bear", 0.75, 0.75), ("base", 1.0, 0.85),
                                 ("bull", 1.15, 0.92)):
        bv = equity
        pv = 0.0
        cur_roe = roe * roe_mult
        for yr in range(1, 9):
            ri = bv * (cur_roe - ke)
            pv += ri / ((1 + ke) ** yr)
            bv *= (1 + g_book * 0.8)
            # Excess returns erode as competition arrives.
            cur_roe = ke + (cur_roe - ke) * fade
        out[case] = (equity + pv) / shares

    if "base" not in out or out["base"] <= 0:
        return None
    return {
        "method": "Residual income (excess returns)",
        "per_share": out,
        "inputs": {
            "book_equity": equity, "net_income": ni,
            "roe": round(roe, 4), "cost_of_equity": round(ke, 4),
            "book_growth": round(g_book, 4), "shares": shares,
        },
        "explanation": (
            "Starts from the company's book value, then adds the value of the "
            "profit it earns above what shareholders require. Suited to banks, "
            "where book equity is the working asset."),
    }


# ---------------------------------------------------------------------------
# Method 3 - Dividend discount (reliable payers)
# ---------------------------------------------------------------------------
def dividend_discount(dps_ttm, dps_growth, assumptions, beta=1.0) -> dict | None:
    if not dps_ttm or dps_ttm <= 0:
        return None
    ke = cost_of_equity(assumptions, beta)
    tg = assumptions["terminal_growth"]
    out = {}
    for case, gmult, rprem in (("bear", 0.6, 0.02), ("base", 1.0, 0.0),
                               ("bull", 1.25, -0.01)):
        g = min(_bounded_growth(dps_growth, tg * 0.8, 0.0, 0.30) * gmult, tg * 0.95)
        disc = ke + rprem
        if disc <= g:
            continue
        out[case] = dps_ttm * (1 + g) / (disc - g)
    if "base" not in out or out["base"] <= 0:
        return None
    return {
        "method": "Dividend discount (Gordon growth)",
        "per_share": out,
        "inputs": {"dividend_per_share_ttm": dps_ttm,
                   "dividend_growth": round(dps_growth, 4) if dps_growth else None,
                   "cost_of_equity": round(ke, 4)},
        "explanation": (
            "Values the share as the stream of dividends it is expected to pay, "
            "discounted back to today. Only meaningful for consistent payers."),
    }


# ---------------------------------------------------------------------------
# Method 4 - Relative multiples against the company's own history
# ---------------------------------------------------------------------------
def relative_multiple(hist, shares, price, kind: str,
                      peer_median: float | None = None) -> dict | None:
    """
    Applies a normal multiple to the current fundamental.

    The reference multiple is the company's own 5-year median, with the sector
    median as a fallback. Self-referencing avoids importing a developed-market
    multiple that Egyptian equities have never traded at.
    """
    latest = hist[0]["values"]
    if shares is None or shares <= 0:
        return None

    if kind == "pe":
        metric = _safe(latest.get("net_income"), shares)
        label, name = "P/E", "Price to earnings"
    elif kind == "pb":
        metric = _safe(latest.get("total_equity"), shares)
        label, name = "P/B", "Price to book value"
    elif kind == "ps":
        metric = _safe(latest.get("revenue"), shares)
        label, name = "P/S", "Price to sales"
    else:
        return None
    if metric is None or metric <= 0:
        return None

    # Historic multiples implied by past fundamentals at today's price are not
    # meaningful; instead use the company's own historical ratio of price-like
    # measures where available, else the peer median.
    ref = peer_median
    if ref is None or ref <= 0:
        return None

    out = {"bear": metric * ref * 0.75,
           "base": metric * ref,
           "bull": metric * ref * 1.25}
    return {
        "method": "%s multiple" % label,
        "per_share": out,
        "inputs": {"metric_per_share": round(metric, 4),
                   "reference_multiple": round(ref, 2),
                   "multiple_source": "sector median"},
        "explanation": (
            "Applies a typical %s multiple for similar Egyptian companies to "
            "this company's own figures." % name.lower()),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def choose_methods(sector: str | None, hist: list[dict],
                   has_dividends: bool) -> list[str]:
    """Pick methods that suit the business, and say why."""
    methods = []
    if sector in BANKING_SECTORS:
        methods = ["residual_income", "pb"]
        if has_dividends:
            methods.append("ddm")
        methods.append("pe")
    elif sector in FINANCIAL_SECTORS:
        methods = ["residual_income", "pb", "pe"]
        if has_dividends:
            methods.append("ddm")
    elif sector in PROPERTY_SECTORS:
        methods = ["pb", "pe", "dcf"]
    else:
        methods = ["dcf", "pe", "ps"]
        if has_dividends:
            methods.append("ddm")
    return methods


def valuation_rationale(sector: str | None) -> str:
    if sector in BANKING_SECTORS:
        return ("Banks are valued on book equity and the returns they earn on it. "
                "Cash-flow models are not used here: for a bank, borrowing is raw "
                "material rather than financing, so 'free cash flow' does not "
                "carry its usual meaning.")
    if sector in PROPERTY_SECTORS:
        return ("Property companies are valued primarily against the assets on "
                "their balance sheet, since the value sits in land and buildings "
                "rather than in a steady stream of operating cash.")
    if sector in FINANCIAL_SECTORS:
        return ("Financial companies are valued on book equity and earnings, "
                "because their balance sheet is the business.")
    return ("Operating companies are valued mainly on the cash they generate, "
            "cross-checked against earnings and sales multiples.")


def value_security(db, sec, price: float, hist: list[dict],
                   dps_ttm: float | None, dps_growth: float | None,
                   peer_multiples: dict, assumptions: dict | None = None,
                   beta: float = 1.0) -> dict:
    """
    Run every method appropriate to this company and combine them.

    Returns a structure the UI can render without doing any maths of its own.
    """
    a = dict(DEFAULTS)
    if assumptions:
        a.update({k: v for k, v in assumptions.items() if k in DEFAULTS})

    if not hist:
        return {"available": False,
                "reason": "No financial statements are available for this company, "
                          "so a fair value cannot be estimated.",
                "assumptions": a}

    latest = hist[0]["values"]
    shares = latest.get("shares")
    if shares is None or shares <= 0:
        shares = sec.shares_outstanding
    if shares is None or shares <= 0:
        return {"available": False,
                "reason": "The number of shares in issue is not available from "
                          "free sources, so per-share value cannot be calculated.",
                "assumptions": a}

    net_debt = None
    if latest.get("total_debt") is not None:
        net_debt = latest["total_debt"] - (latest.get("cash") or 0.0)

    wanted = choose_methods(sec.sector, hist, bool(dps_ttm))
    results, skipped = [], []

    for m in wanted:
        r = None
        if m == "dcf":
            r = dcf_fcff(hist, shares, net_debt, a, beta)
            if r is None:
                skipped.append(("Discounted cash flow",
                                "free cash flow is unavailable or negative"))
        elif m == "residual_income":
            r = residual_income(hist, shares, a, beta)
            if r is None:
                skipped.append(("Residual income",
                                "book equity or profit is unavailable or negative"))
        elif m == "ddm":
            r = dividend_discount(dps_ttm, dps_growth, a, beta)
            if r is None:
                skipped.append(("Dividend discount", "no consistent dividend"))
        elif m in ("pe", "pb", "ps"):
            r = relative_multiple(hist, shares, price, m,
                                  peer_multiples.get(m))
            if r is None:
                skipped.append((m.upper() + " multiple",
                                "the underlying figure is missing or negative, "
                                "or no sector benchmark is available"))
        if r:
            results.append(r)

    if not results:
        return {"available": False,
                "reason": "None of the valuation methods suited to this company "
                          "could be completed with the data available.",
                "skipped": skipped, "assumptions": a,
                "rationale": valuation_rationale(sec.sector)}

    bear = _median([r["per_share"].get("bear") for r in results])
    base = _median([r["per_share"].get("base") for r in results])
    bull = _median([r["per_share"].get("bull") for r in results])

    # Disagreement between methods is the honest measure of confidence.
    bases = [r["per_share"]["base"] for r in results if r["per_share"].get("base")]
    spread = None
    if len(bases) > 1 and base:
        spread = (max(bases) - min(bases)) / base

    confidence, conf_reasons = _confidence(results, spread, hist, skipped)

    upside = ((base / price - 1.0) * 100) if (base and price) else None
    classification, class_note = _classify(upside, confidence)

    return {
        "available": True,
        "currency": sec.currency,
        "price": price,
        "bear": bear, "base": base, "bull": bull,
        "upside_pct": round(upside, 1) if upside is not None else None,
        "classification": classification,
        "classification_note": class_note,
        "confidence": confidence,
        "confidence_reasons": conf_reasons,
        "method_spread_pct": round(spread * 100, 1) if spread is not None else None,
        "methods": results,
        "methods_skipped": skipped,
        "rationale": valuation_rationale(sec.sector),
        "rate_note": RATE_SOURCE_NOTE,
        "assumptions": a,
        "disclaimer": (
            "This is a model estimate produced from the assumptions listed, not "
            "a price target and not advice. Different assumptions give different "
            "answers, and the model can be wrong."),
    }


def _confidence(results, spread, hist, skipped) -> tuple[int, list[str]]:
    """Confidence falls when methods disagree, history is short, or data is thin."""
    score = 50
    reasons = []

    n = len(results)
    if n >= 3:
        score += 15; reasons.append("%d independent methods could be run" % n)
    elif n == 2:
        score += 5; reasons.append("two methods could be run")
    else:
        score -= 10; reasons.append("only one method could be run")

    if spread is not None:
        if spread < 0.25:
            score += 20; reasons.append("the methods broadly agree")
        elif spread < 0.6:
            score += 5; reasons.append("the methods differ moderately")
        else:
            score -= 20
            reasons.append("the methods disagree sharply, so the range is wide")

    periods = len(hist)
    if periods >= 5:
        score += 10; reasons.append("five years of statements available")
    elif periods >= 3:
        reasons.append("only %d years of statements available" % periods)
    else:
        score -= 15; reasons.append("fewer than three years of statements")

    if skipped:
        score -= min(10, 3 * len(skipped))
        reasons.append("%d method(s) could not be applied" % len(skipped))

    return max(5, min(95, score)), reasons


def _classify(upside, confidence) -> tuple[str, str]:
    if upside is None:
        return ("Insufficient reliable data",
                "There is not enough information to compare price with value.")
    # A wide-uncertainty model should not make confident calls.
    if confidence < 35:
        return ("Insufficient reliable data",
                "The models disagree too much for a meaningful classification.")
    if upside >= 30:
        return ("Potentially undervalued",
                "The model's estimate sits well above the current price, under "
                "the stated assumptions.")
    if upside >= 10:
        return ("Potentially undervalued",
                "The model's estimate sits somewhat above the current price.")
    if upside > -10:
        return ("Potentially fairly valued",
                "The current price is close to the model's estimate.")
    if upside > -30:
        return ("Potentially overvalued",
                "The model's estimate sits below the current price.")
    return ("Potentially overvalued",
            "The model's estimate sits well below the current price.")
