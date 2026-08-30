"""
What the market has actually paid for a company, historically.

Why this is worth more than another model
-----------------------------------------
A discounted cash-flow model built on four years of annual filings stacks three
assumptions on a noisy base and produces an answer that moves by a factor of
two when any one of them changes. "This company has traded between 4 and 11
times earnings over the last decade and sits at 5.8 today" needs no assumptions
at all. It is a measurement, and it is the sort of context a reader can argue
with -- which is the point.

It is also the honest counterweight to the fair-value engine. Where the model
says a company screens as expensive, its own trading history can say whether
the market has ever paid this much for it before.

How it is built
---------------
For each annual period we hold, take the figures the company reported and the
share price at the point the market could plausibly have known them -- the
period end plus a reporting lag, not the period end itself, because the
accounts did not exist on the last day of the year.

What it refuses to do
---------------------
Companies whose price series contains an unadjusted split are skipped
entirely. Their historical prices are on a different share count from their
historical earnings, so every ratio would be wrong by the split factor, and
wrong in a way that looks perfectly plausible on a chart.

Fewer than three usable periods produces nothing. Two points are not a range.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from ..models import Price, Security
from .analytics import price_on_or_before
from .fundamentals import statement_history

# Egyptian annual results are typically published in the first quarter after
# the year end. Using the period-end price would credit the market with
# knowing figures that had not been released.
REPORTING_LAG_DAYS = 90

MIN_PERIODS = 3

RATIOS = (
    ("pe", "Price / earnings", "net_income"),
    ("pb", "Price / book", "total_equity"),
)


def _percentile_of(value: float, series: list[float]) -> float | None:
    """Where today's ratio sits within the company's own history, 0-100."""
    if not series or value is None:
        return None
    below = sum(1 for x in series if x < value)
    return round(below / len(series) * 100, 0)


def bands_for(db, sec, current_price: float | None) -> dict:
    """Historical multiple ranges for one company."""
    out = {"available": False}

    if sec.price_integrity == "discontinuous":
        out["reason"] = (
            "This company's price history contains a share split that our "
            "source did not apply backwards, so its past prices and its past "
            "earnings are on different share counts. Any historical multiple "
            "would be wrong by the split factor.")
        return out

    hist = statement_history(db, sec.id, "annual")
    if len(hist) < MIN_PERIODS:
        out["reason"] = ("We hold %d year%s of accounts for this company, and a "
                         "range needs at least %d."
                         % (len(hist), "" if len(hist) == 1 else "s",
                            MIN_PERIODS))
        return out

    series: dict[str, list[dict]] = {k: [] for k, _, _ in RATIOS}

    for h in hist:
        v = h["values"]
        shares = v.get("shares") or sec.shares_outstanding
        if not shares or shares <= 0:
            continue
        end = h["period_end"]
        if hasattr(end, "isoformat"):
            end_date = end
        else:
            from datetime import date as _d
            end_date = _d.fromisoformat(str(end))

        px = price_on_or_before(db, sec.id, end_date + timedelta(days=REPORTING_LAG_DAYS))
        if px is None or not px.close or px.close <= 0:
            continue

        for key, _label, concept in RATIOS:
            base = v.get(concept)
            if base is None or base <= 0:
                continue
            per_share = base / shares
            if per_share <= 0:
                continue
            ratio = px.close / per_share
            # A multiple beyond this is a data fault, not a valuation.
            if not (0 < ratio < 200):
                continue
            series[key].append({"period": str(end_date), "ratio": round(ratio, 2),
                                "price": round(px.close, 4)})

    result = {}
    latest = hist[0]["values"]
    latest_shares = latest.get("shares") or sec.shares_outstanding

    for key, label, concept in RATIOS:
        points = series[key]
        if len(points) < MIN_PERIODS:
            continue
        vals = sorted(p["ratio"] for p in points)
        n = len(vals)
        median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2

        current = None
        base = latest.get(concept)
        if current_price and base and base > 0 and latest_shares:
            per_share = base / latest_shares
            if per_share > 0:
                current = round(current_price / per_share, 2)

        result[key] = {
            "label": label,
            "low": vals[0],
            "median": round(median, 2),
            "high": vals[-1],
            "current": current,
            "percentile": _percentile_of(current, vals),
            "periods": n,
            "points": points,
        }

    if not result:
        out["reason"] = ("The figures needed to work out a historical multiple "
                         "are missing or negative for this company.")
        return out

    return {
        "available": True,
        "ratios": result,
        "reporting_lag_days": REPORTING_LAG_DAYS,
        "note": ("Each year's multiple uses the share price about %d days after "
                 "that year ended, which is roughly when the results were "
                 "published — the market could not have known them any earlier."
                 % REPORTING_LAG_DAYS),
    }


def describe_position(band: dict) -> str | None:
    """One sentence on where a company sits against its own history."""
    if not band or band.get("current") is None or band.get("percentile") is None:
        return None
    p = band["percentile"]
    if p <= 20:
        where = "near the cheapest it has been"
    elif p <= 40:
        where = "below its usual level"
    elif p < 60:
        where = "about where it usually trades"
    elif p < 80:
        where = "above its usual level"
    else:
        where = "near the most expensive it has been"
    return ("At %.2f, its %s is %s on this measure over the %d years we hold "
            "(range %.2f to %.2f, usually around %.2f)."
            % (band["current"], band["label"].lower(), where, band["periods"],
               band["low"], band["high"], band["median"]))
