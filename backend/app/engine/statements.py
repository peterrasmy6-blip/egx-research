"""
Financial statements, presented so they can actually be read.

Two problems with a raw statement table
---------------------------------------
The first is scale. Revenue of EGP 120,657,000,000 next to EGP 4,213,000 tells
you almost nothing at a glance, and comparing two companies of different sizes
by eye is hopeless.

The second is that the interesting question is rarely the level. It is the
shape: what share of each pound of sales survives to the bottom, and whether
that share is improving or eroding. A company whose revenue doubled while its
net margin halved has not necessarily had a good few years.

Common-sizing answers both. Every income-statement line is expressed as a
percentage of revenue, and every balance-sheet line as a percentage of total
assets, so the numbers become directly comparable across years and across
companies of any size.

What is deliberately not done
-----------------------------
Missing lines stay missing. Banks do not report gross profit or EBITDA, and
inserting a zero would turn "not applicable" into "nothing", which reads as a
fact about the business rather than about the filing. A dash means the company
does not report it.

Percentages are also withheld where the base is negative. A margin computed
against a loss is arithmetically defined and completely meaningless.
"""
from __future__ import annotations

# Income statement, in the order a reader works down it.
INCOME_LINES = [
    ("revenue", "Revenue", True),
    ("gross_profit", "Gross profit", False),
    ("operating_income", "Operating profit", False),
    ("pretax_income", "Profit before tax", False),
    ("net_income", "Net profit", False),
    ("ebitda", "EBITDA", False),
]

BALANCE_LINES = [
    ("total_assets", "Total assets", True),
    ("cash", "Cash", False),
    ("total_debt", "Total debt", False),
    ("total_equity", "Total equity", False),
]

CASHFLOW_LINES = [
    ("operating_cf", "Cash from operations", False),
    ("capex", "Capital spending", False),
    ("free_cash_flow", "Free cash flow", False),
]


def _pct_of(value, base):
    """A share of the base, or None when the base makes it meaningless."""
    if value is None or base is None or base <= 0:
        return None
    return round(value / base * 100, 1)


def _trend(series: list[float | None]) -> dict | None:
    """
    Direction of a common-sized line over the years we hold.

    Reported as the change in percentage points between the oldest and newest
    period, which is the comparison a reader would make by eye anyway -- and
    the one that says whether a margin is widening or being squeezed.
    """
    known = [(i, v) for i, v in enumerate(series) if v is not None]
    if len(known) < 2:
        return None
    # `series` runs newest-first, matching the table.
    newest, oldest = known[0][1], known[-1][1]
    return {"change_pp": round(newest - oldest, 1),
            "periods": known[-1][0] - known[0][0] + 1}


def common_sized(hist: list[dict]) -> dict:
    """
    Statements as levels and as percentages, newest period first.

    `hist` is the annual statement history: newest first, each with a
    `period_end` and a `values` mapping.
    """
    if not hist:
        return {"available": False,
                "reason": "No financial statements are available for this "
                          "company from free sources."}

    periods = [str(h["period_end"]) for h in hist]
    vals = [h["values"] for h in hist]

    def build(lines, base_key, base_label):
        out = []
        for key, label, is_base in lines:
            levels = [v.get(key) for v in vals]
            if all(x is None for x in levels):
                continue      # the company does not report this line at all
            shares = [None if is_base else _pct_of(v.get(key), v.get(base_key))
                      for v in vals]
            out.append({
                "key": key, "label": label, "is_base": is_base,
                "levels": levels,
                "shares": None if is_base else shares,
                "trend": None if is_base else _trend(shares),
            })
        return {"lines": out, "base_label": base_label}

    income = build(INCOME_LINES, "revenue", "revenue")
    balance = build(BALANCE_LINES, "total_assets", "total assets")
    cash = build(CASHFLOW_LINES, "revenue", "revenue")

    reported = {k for v in vals for k, x in v.items() if x is not None}
    missing = [label for key, label, _ in
               INCOME_LINES + BALANCE_LINES + CASHFLOW_LINES
               if key not in reported]

    return {
        "available": True,
        "periods": periods,
        "income": income,
        "balance": balance,
        "cashflow": cash,
        "missing": missing,
        "note": (
            "Percentages show each line as a share of %s, so the shape of the "
            "business can be compared across years and against companies of a "
            "very different size. A dash means the company does not report "
            "that line, which is normal — banks and insurers do not publish "
            "the same lines as manufacturers."
            % "revenue (or total assets, on the balance sheet)"),
    }
