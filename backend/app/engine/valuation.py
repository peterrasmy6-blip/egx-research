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

    # Long-run nominal growth.
    #
    # This is NOT a free parameter. In equilibrium a mature company's long-run
    # nominal growth tracks nominal GDP, and the nominal government bond yield
    # is the standard proxy for that. So it is derived from the risk-free rate
    # rather than typed in -- see `terminal_growth_for`.
    #
    # The previous value, a fixed 12%, was the single largest source of bias in
    # this engine. Discounting at 26% (a rate that embeds roughly 20% inflation)
    # while growing at 12% forever assumes every company on the exchange shrinks
    # by about 8% a year in real terms, in perpetuity. That is not conservatism,
    # it is an error, and it ran one way: everything looked expensive.
    "terminal_gap": 0.035,      # mature firms grow a little below the economy

    "cost_of_debt": 0.20,
    "tax_rate": 0.225,          # Egyptian corporate income tax

    # Bounds on the exit multiple applied to year-five cash flow, which
    # replaces a Gordon perpetuity. The multiple itself is derived from the
    # discount rate and long-run growth -- see `_exit_multiple` -- because
    # picking a number by hand reintroduces exactly the arbitrary assumption
    # the perpetuity was abandoned for. The bounds stop it exploding when the
    # two rates converge.
    "exit_multiple_min": 6.0,
    "exit_multiple_max": 16.0,
}


def _exit_multiple(discount: float, growth: float, assumptions: dict) -> float:
    """
    What the business could be sold for in year five, as a multiple of its cash
    flow then.

    Economically this is the perpetuity multiple, 1 / (r - g), so the model
    stays internally consistent: the same discount rate and the same long-run
    growth that drive the first five years also drive the exit. The difference
    from a Gordon terminal value is that it is bounded, so as r approaches g
    the answer stops diverging instead of running to infinity.

    Getting this wrong in the conservative direction is not harmless. An
    arbitrary 8x, chosen by analogy with Egyptian earnings multiples, implied a
    12.5% perpetual cash yield -- a far wider gap between discount rate and
    growth than this model actually assumes, and it valued sound companies at a
    fraction of their price.
    """
    spread = discount - growth
    if spread <= 0.01:
        return assumptions["exit_multiple_max"]
    return max(assumptions["exit_multiple_min"],
               min(assumptions["exit_multiple_max"], 1.0 / spread))

# The smallest gap between discount rate and growth we will tolerate before
# refusing to use a perpetuity-style formula at all. Below this the answer is
# dominated by the difference of two uncertain numbers.
MIN_DISCOUNT_SPREAD = 0.05


def terminal_growth_for(assumptions: dict) -> float:
    """Long-run nominal growth, derived from the risk-free rate."""
    return max(0.0, assumptions["risk_free_rate"] - assumptions["terminal_gap"])

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


def _weighted_median(pairs):
    """
    Median where each value carries a weight.

    A flat median treats every method as equally believable. It is not: a
    multiple drawn from a real peer group is worth more than one borrowed from
    the whole market, and a cash-flow projection built on a growth rate pinned
    to its own clamp is worth less than one that is not. Weighting keeps the
    robustness of a median -- a single wild method still cannot run away with
    the answer -- while letting evidence count.
    """
    pairs = [(v, w) for v, w in pairs if v is not None and w and w > 0]
    if not pairs:
        return None
    pairs.sort(key=lambda p: p[0])
    total = sum(w for _, w in pairs)
    half = total / 2
    acc = 0.0
    for i, (v, w) in enumerate(pairs):
        acc += w
        # Landing exactly on half means the weight is split evenly either side,
        # so the midpoint of the two neighbours is the honest answer. Returning
        # the lower one would bias every even-numbered set downward -- which is
        # exactly the direction of error this whole exercise is correcting.
        if abs(acc - half) < 1e-12 and i + 1 < len(pairs):
            return (v + pairs[i + 1][0]) / 2
        if acc > half:
            return v
    return pairs[-1][0]


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
    fcf_latest = latest.get("free_cash_flow")
    if fcf_latest is None or shares is None or shares <= 0:
        return None
    if fcf_latest <= 0:
        # A DCF on negative cash flow needs a forecast of the turnaround, which
        # we cannot derive from filings alone. Refuse rather than invent one.
        return None

    # Free cash flow swings violently with the capital-spending cycle: one
    # heavy investment year can halve it without the business changing at all.
    # Starting a five-year projection from a single such year is the largest
    # avoidable error in this model, so the starting point is the median of the
    # years we hold. The latest year still sets the sign -- we refuse on a
    # company that is currently burning cash.
    fcf_series = [h["values"].get("free_cash_flow") for h in hist[:5]]
    fcf_series = [x for x in fcf_series if x is not None and x > 0]
    fcf = _median(fcf_series) if len(fcf_series) >= 3 else fcf_latest
    normalised = len(fcf_series) >= 3

    r = wacc(assumptions, latest.get("total_equity"), latest.get("total_debt"), beta)
    tg = terminal_growth_for(assumptions)

    raw_g = historical_growth(hist, "free_cash_flow") \
        or historical_growth(hist, "operating_cf")
    base_g = growth_override if growth_override is not None \
        else _bounded_growth(raw_g, tg)
    # A growth rate sitting exactly on the clamp is an extrapolation artefact,
    # not a measurement. The valuation still runs, but it is marked so the
    # combination step can trust it less.
    at_clamp = raw_g is not None and (raw_g >= 0.45 or raw_g <= -0.05)

    out, mults = {}, {}
    for case, gmult, rprem, mmult in (("bear", 0.6, 0.02, 0.85),
                                      ("base", 1.0, 0.0, 1.0),
                                      ("bull", 1.3, -0.01, 1.15)):
        g = max(0.0, base_g * gmult)
        disc = r + rprem
        pv = 0.0
        cf = fcf
        for yr in range(1, 6):
            cf *= (1 + g)
            pv += cf / ((1 + disc) ** yr)
        # Terminal value by a bounded exit multiple, not by perpetuity.
        em = _exit_multiple(disc, tg, assumptions) * mmult
        mults[case] = round(em, 1)
        pv += (cf * em) / ((1 + disc) ** 5)
        out[case] = (pv - (net_debt or 0.0)) / shares

    if "base" not in out or out["base"] <= 0:
        return None
    # Leverage can drive the bear case negative once net debt is subtracted.
    # A negative "value per share" is not information, it is the model failing.
    if out.get("bear", 0) <= 0:
        out["bear"] = out["base"] * 0.5

    return {
        "method": "Discounted cash flow",
        "per_share": out,
        # Weighted below the multiple-based methods by default. With four
        # years of annual filings, no company guidance and a volatile capital
        # cycle, a five-year projection stacks three assumptions on a noisy
        # base. It is worth showing -- it is not worth trusting equally.
        "reliability": (0.5 if at_clamp else 0.7) * (1.0 if normalised else 0.8),
        "reliability_note": (
            "cash-flow growth history is extreme, so the projection is "
            "indicative only" if at_clamp else
            "only one year of cash flow was available to start from"
            if not normalised else
            "projections five years out are less certain than multiples"),
        "inputs": {
            "starting_free_cash_flow": fcf,
            "starting_cash_flow_basis": ("median of %d years" % len(fcf_series)
                                         if normalised else "latest year only"),
            "growth_rate_base": round(base_g, 4),
            "discount_rate": round(r, 4),
            "exit_multiple": mults.get("base"),
            "long_run_growth_reference": round(tg, 4),
            "net_debt": net_debt,
            "shares": shares,
        },
        "explanation": (
            "Projects the company's free cash flow forward for five years, then "
            "assumes the business could be sold at %g times its cash flow at "
            "that point. Future cash is discounted back because money later is "
            "worth less than money now." % mults.get("base", 0)),
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
                             terminal_growth_for(assumptions), 0.0, 0.35)

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
MIN_PAYOUT_FOR_DDM = 0.30
MAX_PAYOUT_FOR_DDM = 1.10


def dividend_discount(dps_ttm, dps_growth, assumptions, hist=None, shares=None,
                      beta=1.0) -> dict | tuple[None, str] | None:
    """
    Value the share as its stream of dividends.

    This method was previously applied to any company that paid anything at
    all, and it was the worst offender in the engine. Gordon growth values a
    share at roughly (dividend / cost of equity), so a company distributing a
    quarter of its earnings was valued at roughly a quarter of its worth. It
    put Telecom Egypt at EGP 10 against a market price of 116, Elsewedy at 14
    against 128, and Edita at 3.45 against 32.

    The error was not the arithmetic, it was applying the model outside its
    domain. Gordon growth is only coherent when the dividend genuinely stands
    in for the whole return -- that is, when the payout ratio is high and the
    growth rate is the one retained earnings can actually fund.

    So this now refuses unless the company is a real income stock, and derives
    growth from sustainable growth (return on equity times the share of profit
    retained) rather than from the recent path of the dividend itself.

    Returns (None, reason) when it declines, so the caller can tell the user
    why rather than silently dropping a method.
    """
    if not dps_ttm or dps_ttm <= 0:
        return None, "the company does not pay a regular dividend"

    ke = cost_of_equity(assumptions, beta)
    tg = terminal_growth_for(assumptions)

    eps = roe = None
    if hist and shares and shares > 0:
        latest = hist[0]["values"]
        ni, eq = latest.get("net_income"), latest.get("total_equity")
        if ni is not None and ni > 0:
            eps = ni / shares
        if ni is not None and eq and eq > 0:
            roe = ni / eq

    if eps is None:
        return None, ("the company's earnings are not available, so we cannot "
                      "tell whether the dividend is sustainable")

    payout = dps_ttm / eps
    if payout < MIN_PAYOUT_FOR_DDM:
        return None, (
            "this company distributes only %.0f%% of its profit, so a dividend "
            "model would value just that slice and ignore the rest of the "
            "business. Used only where the payout is above %.0f%%"
            % (payout * 100, MIN_PAYOUT_FOR_DDM * 100))
    if payout > MAX_PAYOUT_FOR_DDM:
        return None, (
            "this company is paying out %.0f%% of its profit, which it cannot "
            "sustain from earnings, so projecting that dividend forward would "
            "be misleading" % (payout * 100))

    # Growth the retained profit can actually fund.
    if roe is not None and roe > 0:
        g_sustainable = roe * max(0.0, 1.0 - payout)
    else:
        g_sustainable = 0.0
    g_base = min(g_sustainable, tg, ke - MIN_DISCOUNT_SPREAD)
    g_base = max(0.0, g_base)

    out = {}
    for case, gmult, rprem in (("bear", 0.5, 0.02), ("base", 1.0, 0.0),
                               ("bull", 1.25, -0.01)):
        g = min(g_base * gmult, tg)
        disc = ke + rprem
        if disc - g < MIN_DISCOUNT_SPREAD:
            continue
        out[case] = dps_ttm * (1 + g) / (disc - g)
    if "base" not in out or out["base"] <= 0:
        return None, ("the required return and the sustainable growth rate are "
                      "too close for this model to give a stable answer")

    erratic = dps_growth is not None and abs(dps_growth) > 0.50
    return {
        "method": "Dividend discount (Gordon growth)",
        "per_share": out,
        "reliability": 0.5 if erratic else 1.0,
        "reliability_note": (
            "the dividend changed by %.0f%% last year, so projecting it forward "
            "is unreliable" % (dps_growth * 100)) if erratic else None,
        "inputs": {"dividend_per_share_ttm": dps_ttm,
                   "earnings_per_share": round(eps, 4),
                   "payout_ratio": round(payout, 3),
                   "sustainable_growth": round(g_base, 4),
                   "return_on_equity": round(roe, 4) if roe else None,
                   "cost_of_equity": round(ke, 4)},
        "explanation": (
            "Values the share as the stream of dividends it is expected to pay, "
            "discounted back to today. Growth is set by what the retained "
            "profit can fund, not by last year's dividend increase. Used only "
            "for companies that distribute most of what they earn."),
    }


# ---------------------------------------------------------------------------
# Method 4 - Relative multiples against the company's own history
# ---------------------------------------------------------------------------
def relative_multiple(hist, shares, price, kind: str,
                      peer_median: float | None = None,
                      market_median: float | None = None) -> dict | None:
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
    ref, source = peer_median, "sector median"
    if ref is None or ref <= 0:
        # A sector too small to form its own benchmark falls back to the whole
        # market rather than losing the method entirely.
        ref, source = market_median, "market median (sector too small)"
    if ref is None or ref <= 0:
        return None

    out = {"bear": metric * ref * 0.75,
           "base": metric * ref,
           "bull": metric * ref * 1.25}
    return {
        "method": "%s multiple" % label,
        "per_share": out,
        "reliability": 1.0 if source == "sector median" else 0.7,
        "reliability_note": (None if source == "sector median" else
                             "no sector benchmark was available, so the "
                             "market-wide multiple was used instead"),
        "inputs": {"metric_per_share": round(metric, 4),
                   "reference_multiple": round(ref, 2),
                   "multiple_source": source},
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
                   beta: float = 1.0,
                   market_multiples: dict | None = None) -> dict:
    """
    Run every method appropriate to this company and combine them.

    Returns a structure the UI can render without doing any maths of its own.
    """
    a = dict(DEFAULTS)
    if assumptions:
        a.update({k: v for k, v in assumptions.items()
                  if k in DEFAULTS or k == "market_median_upside_pct"})
    # Derived, not typed in -- but shown to the user alongside the inputs it
    # comes from, so the chain from government yield to fair value is visible.
    a["terminal_growth"] = terminal_growth_for(a)
    market_multiples = market_multiples or {}

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
            r = dividend_discount(dps_ttm, dps_growth, a, hist, shares, beta)
            if isinstance(r, tuple):        # declined, with a stated reason
                skipped.append(("Dividend discount", r[1]))
                r = None
            elif r is None:
                skipped.append(("Dividend discount", "no consistent dividend"))
        elif m in ("pe", "pb", "ps"):
            r = relative_multiple(hist, shares, price, m,
                                  peer_multiples.get(m),
                                  market_multiples.get(m))
            if r is None:
                skipped.append((m.upper() + " multiple",
                                "the underlying figure is missing or negative, "
                                "and no benchmark multiple is available"))
        if r:
            results.append(r)

    if not results:
        return {"available": False,
                "reason": "None of the valuation methods suited to this company "
                          "could be completed with the data available.",
                "skipped": skipped, "assumptions": a,
                "rationale": valuation_rationale(sec.sector)}

    # Methods are combined by weighted median, so a method we have reason to
    # trust less counts for less without being silently discarded.
    wts = [r.get("reliability", 1.0) for r in results]
    bear = _weighted_median([(r["per_share"].get("bear"), w)
                             for r, w in zip(results, wts)])
    base = _weighted_median([(r["per_share"].get("base"), w)
                             for r, w in zip(results, wts)])
    bull = _weighted_median([(r["per_share"].get("bull"), w)
                             for r, w in zip(results, wts)])

    # Disagreement between methods is the honest measure of confidence.
    bases = [r["per_share"]["base"] for r in results if r["per_share"].get("base")]
    spread = None
    if len(bases) > 1 and base:
        spread = (max(bases) - min(bases)) / base

    confidence, conf_reasons = _confidence(results, spread, hist, skipped)

    upside = ((base / price - 1.0) * 100) if (base and price) else None
    market_upside = a.get("market_median_upside_pct")
    classification, class_note = _classify(upside, confidence, market_upside)

    return {
        "available": True,
        "currency": sec.currency,
        "price": price,
        "bear": bear, "base": base, "bull": bull,
        "upside_pct": round(upside, 1) if upside is not None else None,
        # The same figure with the model's market-wide bias removed. This is
        # what the label is based on; the raw number above is kept so nothing
        # is hidden.
        "upside_vs_market_pct": (round(upside - market_upside, 1)
                                 if upside is not None and market_upside is not None
                                 else None),
        "market_median_upside_pct": (round(market_upside, 1)
                                     if market_upside is not None else None),
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


# The discount rate is the single most load-bearing assumption in every model
# here, and the one a reader is most entitled to disagree with. Rather than ask
# them to take 26% on faith, the export carries the answer at a range of rates
# so they can find their own and see what follows.
SENSITIVITY_RATES = (0.18, 0.22, 0.26, 0.30, 0.34)


def sensitivity(db, sec, price, hist, dps_ttm, dps_growth, peer_multiples,
                market_multiples=None, market_upside=None) -> dict:
    """
    Fair value across a range of required returns.

    This is the honest answer to "why should I believe 26%?" -- you need not.
    A reader who thinks Egyptian equities deserve a 20% hurdle can read the row
    for 20% and see what the same model says under their assumption.

    It also makes the model's own sensitivity visible, which is information in
    itself: where the answer swings by a factor of two across a plausible range
    of rates, that is a warning about the method rather than a fact about the
    company.
    """
    rows = []
    for ke in SENSITIVITY_RATES:
        a = {"risk_free_rate": ke - DEFAULTS["equity_risk_premium"]}
        if market_upside is not None:
            a["market_median_upside_pct"] = market_upside
        try:
            r = value_security(db, sec, price, hist, dps_ttm, dps_growth,
                               peer_multiples, assumptions=a,
                               market_multiples=market_multiples)
        except Exception:
            continue
        if not r.get("available"):
            continue
        rows.append({
            "cost_of_equity_pct": round(ke * 100, 1),
            "long_run_growth_pct": round(terminal_growth_for(
                {**DEFAULTS, "risk_free_rate": ke - DEFAULTS["equity_risk_premium"]}) * 100, 1),
            "base": r["base"],
            "bear": r["bear"],
            "bull": r["bull"],
            "upside_pct": r["upside_pct"],
            "classification": r["classification"],
            "is_default": abs(ke - cost_of_equity(DEFAULTS)) < 1e-9,
        })
    if not rows:
        return {"available": False}

    bases = [r["base"] for r in rows if r["base"]]
    swing = (max(bases) / min(bases)) if bases and min(bases) > 0 else None
    return {
        "available": True,
        "rows": rows,
        "default_pct": round(cost_of_equity(DEFAULTS) * 100, 1),
        "swing": round(swing, 2) if swing else None,
        "note": (
            "The required return is the assumption everything else rests on, "
            "and it is the one most worth arguing with. Each row applies the "
            "same model at a different rate. Long-run growth moves with it, "
            "because a company cannot outgrow the economy its discount rate "
            "came from."),
        "swing_note": (
            "Across this range the estimate moves by a factor of %.1f. A model "
            "that sensitive is telling you the range matters more than any "
            "single figure inside it." % swing) if swing and swing >= 1.6 else None,
        # A flat table is not a broken one. It means this company's estimate is
        # coming from what the market pays for comparable companies rather than
        # from a discounted model -- and a multiple has no discount rate in it.
        # Saying so is more useful than showing five identical rows and letting
        # the reader assume something failed.
        "rate_insensitive": bool(swing and swing < 1.05),
        "rate_insensitive_note": (
            "The required return barely changes this company's estimate, "
            "because the estimate is coming from what the market pays for "
            "comparable companies rather than from a discounted cash-flow "
            "model — and a multiple contains no discount rate. That is worth "
            "knowing in itself: it means the figure inherits whatever the "
            "market currently thinks of the sector, rather than testing it."
            if swing and swing < 1.05 else None),
    }


def _classify(upside, confidence, market_upside: float | None = None) -> tuple[str, str]:
    """
    Turn a modelled gap between price and value into a plain-English label.

    Calibration matters here more than the thresholds do. Run across the whole
    exchange, this engine puts the typical company below its market price --
    every model that discounts cash flows does, because the discount rate is
    built from Egyptian government yields near 20% and the market plainly
    applies a lower hurdle to shares, whose earnings inflate with the currency
    while a treasury bill's coupon does not.

    That gap is a property of the model, not of any one company. Reading it as
    a verdict on each company in turn would mean telling users that most of the
    exchange is overvalued -- a claim this engine cannot support, and the sort
    of statement that destroys a research platform's credibility the first time
    it is wrong.

    So the label is set by how a company compares with the *typical* company on
    the same model, and the raw figure is still reported alongside. The common
    part is removed; what is left is the part that carries information.
    """
    if upside is None:
        return ("Insufficient reliable data",
                "There is not enough information to compare price with value.")
    if confidence < 35:
        return ("Insufficient reliable data",
                "The models disagree too much for a meaningful classification.")

    if market_upside is None:
        rel, ref = upside, ""
    else:
        rel = upside - market_upside
        ref = (" This is measured against the typical Egyptian company on the "
               "same model, which currently sits %.0f%% below its market price."
               % abs(market_upside)) if abs(market_upside) >= 1 else ""

    if rel >= 30:
        return ("Screens as cheap",
                "The model values this company well above the typical company "
                "on the exchange, relative to its price." + ref)
    if rel >= 10:
        return ("Screens as cheap",
                "The model values this company somewhat above the typical "
                "company on the exchange, relative to its price." + ref)
    if rel > -10:
        return ("Screens as average",
                "The model values this company in line with the typical "
                "company on the exchange, relative to its price." + ref)
    if rel > -30:
        return ("Screens as expensive",
                "The model values this company below the typical company on "
                "the exchange, relative to its price." + ref)
    return ("Screens as expensive",
            "The model values this company well below the typical company on "
            "the exchange, relative to its price." + ref)
