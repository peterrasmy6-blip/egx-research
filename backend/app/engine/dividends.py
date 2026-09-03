"""
What a dividend record actually tells you.

A yield is a snapshot and a poor one
------------------------------------
"Pays 6%" is the number every screener shows and the least informative thing
about a dividend. It is last year's payment over today's price, so it rises
when the price falls -- and the highest yields on any exchange belong to
companies the market has marked down because it doubts the dividend will be
paid again. A reader shopping for income by yield alone is systematically
steered toward the payments most likely to be cut.

Three questions matter more, and all three are answerable from records this
platform already holds.

  Has it kept paying? A company that has paid in each of the last eight years
  has told you something a single yield cannot. One that paid, stopped, and
  resumed has told you something too.

  Is it covered? A dividend larger than the profit behind it is being funded
  from somewhere else -- reserves, borrowing, asset sales -- and that is a
  temporary arrangement whatever the yield says.

  Is it growing? Against Egyptian inflation a flat dividend is a shrinking
  one. A payment rising at 8% while prices rise at 15% is a real-terms cut
  that looks like stability.

What is deliberately not here
-----------------------------
No "safe" or "unsafe" label. Cover and consistency are facts; whether a
particular dividend will survive next year is a judgement about a business,
and dressing that judgement as a rating would be the most confident thing on
a page whose whole purpose is calibrated honesty.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from ..models import Dividend

# A gap longer than this between payments is a break in the record rather than
# an irregular schedule. Egyptian companies commonly pay once a year, so the
# window has to be generous enough not to read that as a stoppage.
MAX_GAP_DAYS = 460

# Below this a payment is a token rather than a distribution, and counting it
# as a year of dividends flatters a record it should not.
MIN_MEANINGFUL = 0.001


def history(db, security_id: int, today: date | None = None) -> dict:
    """Everything measurable about one company's dividend record."""
    today = today or date.today()
    rows = [(d, a) for d, a in db.execute(
        select(Dividend.ex_date, Dividend.amount_per_share)
        .where(Dividend.security_id == security_id)
        .order_by(Dividend.ex_date)).all()
        if a is not None and a >= MIN_MEANINGFUL]

    if not rows:
        return {"available": False,
                "reason": "We hold no record of this company paying a dividend."}

    # Group by the calendar year of the ex-date. A company paying twice in a
    # year has paid once that year for the purpose of counting a streak.
    by_year: dict[int, float] = {}
    for d, a in rows:
        by_year[d.year] = by_year.get(d.year, 0.0) + a

    years = sorted(by_year)
    last_year, last_date = years[-1], rows[-1][0]

    # A streak is broken by a missed year, and counted backwards from the most
    # recent payment rather than from today -- a company that paid every year
    # until 2024 has an eight-year record that ended, which is a different
    # thing from an eight-year record that continues, and both are reported.
    streak = 1
    for i in range(len(years) - 1, 0, -1):
        if years[i] - years[i - 1] == 1:
            streak += 1
        else:
            break

    gaps = [(years[i - 1], years[i]) for i in range(1, len(years))
            if years[i] - years[i - 1] > 1]

    days_since = (today - last_date).days
    still_paying = days_since <= MAX_GAP_DAYS

    # Growth of the annual total, over as long a run as is unbroken.
    span = [by_year[y] for y in years[-min(len(years), 6):]]
    growth = None
    if len(span) >= 3 and span[0] > 0:
        growth = ((span[-1] / span[0]) ** (1.0 / (len(span) - 1)) - 1.0) * 100

    return {
        "available": True,
        "years_paid": len(years),
        "consecutive_years": streak,
        "still_paying": still_paying,
        "last_paid": last_date.isoformat(),
        "days_since_last": days_since,
        "first_paid": rows[0][0].isoformat(),
        "gaps": [{"after": a, "resumed": b} for a, b in gaps][-4:],
        "annual": [{"year": y, "total": round(by_year[y], 4)} for y in years[-10:]],
        "growth_pct": None if growth is None else round(growth, 1),
        "growth_years": len(span) - 1 if growth is not None else None,
        "latest_annual": round(by_year[last_year], 4),
    }


def cover(latest_dps: float | None, eps: float | None) -> dict:
    """
    How many times over the profit covers the payment.

    Below one, the company is distributing more than it earned. That is not
    automatically alarming -- a single weak year, or a deliberate return of
    capital, both look like this -- but it cannot continue indefinitely, and a
    reader choosing on yield alone would never see it.
    """
    if not latest_dps or not eps or eps <= 0:
        return {"available": False,
                "reason": ("Cover needs both a dividend and a positive profit "
                           "per share, and we do not hold both.")}
    times = eps / latest_dps
    if times >= 2.0:
        band, note = "comfortable", (
            "Profit covers the dividend more than twice over, so an ordinary "
            "bad year need not threaten it.")
    elif times >= 1.2:
        band, note = "adequate", (
            "Profit covers the dividend, with something left over.")
    elif times >= 1.0:
        band, note = "thin", (
            "Profit barely covers the dividend. A weaker year would not.")
    else:
        band, note = "uncovered", (
            "The dividend is larger than the profit behind it, so it is being "
            "paid from somewhere other than this year's earnings.")
    return {"available": True, "times": round(times, 2), "band": band,
            "note": note}


def describe(db, security_id: int, latest_dps: float | None,
             eps: float | None, inflation_pct: float | None = None) -> dict:
    """The whole picture, ready for a page to render."""
    h = history(db, security_id)
    if not h.get("available"):
        return h
    h["cover"] = cover(latest_dps, eps)

    # Against Egyptian inflation a flat dividend is a falling one, and this is
    # the comparison a yield never makes.
    if h.get("growth_pct") is not None and inflation_pct:
        real = ((1 + h["growth_pct"] / 100) / (1 + inflation_pct / 100) - 1) * 100
        h["real_growth_pct"] = round(real, 1)
        h["real_note"] = (
            "The payment has grown %.1f%% a year while Egyptian prices rose "
            "%.1f%%, so in what the money buys it has %s."
            % (h["growth_pct"], inflation_pct,
               "grown %.1f%% a year" % real if real >= 0
               else "shrunk %.1f%% a year" % abs(real)))
    return h


# --------------------------------------------------------------------------
def price_position(price: float | None, low: float | None,
                   high: float | None) -> dict:
    """
    Where today's price sits inside its own year, as a percentage of the range.

    Useful because it is concrete and self-referencing: it compares a company
    only with itself, so it needs no peer group, no sector median and no
    model. A share at 4% of its range has fallen nearly as far as it has been;
    one at 96% is close to its best.

    It carries no verdict, because it does not support one. Near the low is
    where both bargains and failing businesses are found, and near the high is
    where both bubbles and compounding businesses are found. The number tells
    a reader where they are standing, not which of those they are looking at.
    """
    if price is None or low is None or high is None or high <= low:
        return {"available": False}
    pos = (price - low) / (high - low) * 100
    pos = max(0.0, min(100.0, pos))
    if pos <= 15:
        where = "near its 12-month low"
    elif pos <= 40:
        where = "in the lower part of its 12-month range"
    elif pos < 60:
        where = "around the middle of its 12-month range"
    elif pos < 85:
        where = "in the upper part of its 12-month range"
    else:
        where = "near its 12-month high"
    return {
        "available": True,
        "position_pct": round(pos, 1),
        "low": round(low, 4), "high": round(high, 4),
        "from_low_pct": round((price / low - 1) * 100, 1) if low > 0 else None,
        "from_high_pct": round((price / high - 1) * 100, 1) if high > 0 else None,
        "where": where,
        "note": ("Where the price sits between its own highest and lowest "
                 "points of the past year. It says where you are standing, "
                 "not whether that is a good place to stand: shares sit near "
                 "their low both when they are cheap and when the business is "
                 "failing."),
    }
