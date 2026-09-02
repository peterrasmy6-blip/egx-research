"""
Fundamental metrics computed from stored financial statements.

Every ratio here is calculated from raw line items we hold, not copied from a
vendor's pre-computed field. That way the number can always be traced back to
the statement it came from, and a missing input produces None instead of a
silently wrong figure.

Line-item names vary between filings, so each concept lists the aliases we
accept, in priority order.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from ..models import FinancialFact

# Concept -> candidate line-item names, best first.
# Two sources, two vocabularies.
#
# The primary source names a line "Total Revenue" and "Stockholders Equity";
# the second names the same line "Revenue" and "Shareholders' Equity". Both
# appear here so a company is read the same way whichever source supplied it,
# and so the 181 companies the first source skips are not left unreadable
# purely over spelling.
ALIASES = {
    "revenue": ["Total Revenue", "Operating Revenue", "Revenue",
                "Total Interest Income", "Interest Income",
                "Net Interest Income"],
    # Order matters: the first alias present wins.
    #
    # "Net Income Common Stockholders" must come first because it is the
    # profit that belongs to this company's own shareholders. Plain "Net
    # Income" from this source includes the share owned by outside investors
    # in subsidiaries, and using it overstates every per-share figure built on
    # top: earnings per share, return on equity, the earnings yield, and the
    # profit a valuation discounts. CIB's 2025 profit read 82,239m against the
    # 61,634m actually attributable to its shareholders -- a third too high --
    # and a second source agrees to the pound with the narrower figure.
    "net_income": ["Net Income Common Stockholders",
                   "Net Income From Continuing Operation Net Minority Interest",
                   "Net Income", "Net Income Continuous Operations"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "EBIT",
                         "Total Operating Income As Reported"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "pretax_income": ["Pretax Income"],
    "total_assets": ["Total Assets"],
    "total_equity": ["Stockholders Equity", "Shareholders' Equity",
                     "Total Common Equity",
                     "Total Equity Gross Minority Interest",
                     "Common Stock Equity"],
    "total_debt": ["Total Debt", "Long Term Debt And Capital Lease Obligation"],
    "cash": ["Cash And Cash Equivalents", "Cash & Equivalents",
             "Cash Cash Equivalents And Short Term Investments",
             "Cash & Short-Term Investments"],
    "operating_cf": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "capex": ["Capital Expenditure", "Capital Expenditures"],
    "free_cash_flow": ["Free Cash Flow"],
    "shares": ["Diluted Average Shares", "Basic Average Shares",
               "Ordinary Shares Number", "Total Common Shares Outstanding"],
}


def _facts(db, security_id: int, frequency: str = "annual") -> dict:
    """All facts for a security, keyed as {period_end: {item: value}}."""
    rows = db.execute(
        select(FinancialFact.period_end, FinancialFact.item, FinancialFact.value)
        .where(FinancialFact.security_id == security_id,
               FinancialFact.frequency == frequency)).all()
    out: dict[date, dict] = {}
    for pe, item, val in rows:
        out.setdefault(pe, {})[item] = val
    return out


def _pick(period: dict, concept: str):
    for name in ALIASES.get(concept, []):
        if name in period and period[name] is not None:
            return period[name], name
    return None, None


def _safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def statement_history(db, security_id: int, frequency: str = "annual") -> list[dict]:
    """
    Normalised per-period fundamentals, newest first.

    Each entry records which raw line item supplied each concept, so the UI can
    show provenance rather than an unexplained number.
    """
    data = _facts(db, security_id, frequency)
    periods = sorted(data.keys(), reverse=True)
    out = []

    for pe in periods:
        p = data[pe]
        vals, srcs = {}, {}
        for concept in ALIASES:
            v, name = _pick(p, concept)
            vals[concept] = v
            if name:
                srcs[concept] = name

        # Derived figures, only where the inputs genuinely exist.
        if vals["free_cash_flow"] is None and vals["operating_cf"] is not None \
                and vals["capex"] is not None:
            # capex is stored negative by the source
            vals["free_cash_flow"] = vals["operating_cf"] + vals["capex"]
            srcs["free_cash_flow"] = "Operating Cash Flow + Capital Expenditure"

        entry = {
            "period_end": pe.isoformat(),
            "values": vals,
            "sources": srcs,
            "margins": {
                "gross_margin": _safe_div(vals["gross_profit"], vals["revenue"]),
                "operating_margin": _safe_div(vals["operating_income"], vals["revenue"]),
                "net_margin": _safe_div(vals["net_income"], vals["revenue"]),
                "ebitda_margin": _safe_div(vals["ebitda"], vals["revenue"]),
            },
            "returns": {
                "roe": _safe_div(vals["net_income"], vals["total_equity"]),
                "roa": _safe_div(vals["net_income"], vals["total_assets"]),
            },
            "leverage": {
                "debt_to_equity": _safe_div(vals["total_debt"], vals["total_equity"]),
                "net_debt": (vals["total_debt"] - vals["cash"])
                            if vals["total_debt"] is not None and vals["cash"] is not None
                            else None,
            },
            "eps": _safe_div(vals["net_income"], vals["shares"]),
        }
        out.append(entry)

    # Year-on-year growth, computed against the next-older period.
    for i, e in enumerate(out):
        older = out[i + 1] if i + 1 < len(out) else None
        g = {}
        if older:
            for c in ("revenue", "net_income", "operating_income", "ebitda"):
                a, b = e["values"][c], older["values"][c]
                # Growth from a negative or zero base is not meaningful.
                g[c] = (a / b - 1.0) if (a is not None and b is not None and b > 0) else None
        e["growth"] = g

    return out


def summary(db, security_id: int) -> dict:
    """Latest annual fundamentals plus a data-coverage report."""
    hist = statement_history(db, security_id, "annual")
    if not hist:
        return {"available": False,
                "reason": "No financial statements have been collected for this company yet."}

    latest = hist[0]
    present = [k for k, v in latest["values"].items() if v is not None]
    coverage = len(present) / len(ALIASES)

    return {
        "available": True,
        "latest_period": latest["period_end"],
        "coverage_pct": round(coverage * 100),
        "missing_concepts": [k for k, v in latest["values"].items() if v is None],
        "periods_available": len(hist),
        "history": hist,
    }
