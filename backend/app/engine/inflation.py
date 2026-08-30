"""
Egyptian consumer prices, and turning nominal returns into real ones.

Why this matters more here than almost anywhere else
----------------------------------------------------
Commercial International Bank returned about 400% over five years. Over the
same five years Egyptian consumer prices roughly two-and-a-half-folded and the
pound lost most of its value against the dollar. The shareholder did well --
but not four-times-richer well, which is what the headline number implies.

Every multi-year figure the platform shows was nominal: returns, revenue
growth, "what if I invested". The scenario tools deflated correctly while the
company pages did not, so the site taught the right lesson in one room and
broke it in every other. This module closes that gap.

Where the numbers come from
---------------------------
The World Bank's consumer price index for Egypt (indicator FP.CPI.TOTL), which
is free, requires no key, carries no usage restriction that affects us, and
runs back to 1960. It is annual.

The honest limitations, both shown to the reader
------------------------------------------------
1. Annual data is interpolated to give a figure for a date part-way through a
   year. Prices do not actually rise in a smooth line, so a real return
   measured over a period shorter than a year or two is approximate.
2. The series ends at the last completed year. Beyond it, the most recent
   observed rate is carried forward. That is an assumption, it is labelled as
   one, and it is the only alternative to refusing to show a real figure for
   the current year at all.

Neither is hidden. `describe()` returns the wording the site uses.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from ..models import MacroSeries

SERIES = "EGY_CPI"
SOURCE = "World Bank (FP.CPI.TOTL)"
SOURCE_URL = ("https://api.worldbank.org/v2/country/EGY/indicator/"
              "FP.CPI.TOTL?format=json&per_page=100")

# A last-resort assumption if even the carried-forward rate cannot be computed.
FALLBACK_ANNUAL_INFLATION = 0.20


def fetch(verbose: bool = True) -> list[tuple[date, float]]:
    """Annual CPI for Egypt, oldest first. Raises rather than returning junk."""
    from curl_cffi import requests as cr

    s = cr.Session(impersonate="chrome")
    r = s.get("https://api.worldbank.org/v2/country/EGY/indicator/FP.CPI.TOTL",
              params={"format": "json", "per_page": 200}, timeout=45)
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, list) or len(payload) < 2:
        raise RuntimeError("unexpected response shape from the World Bank API")

    out = []
    for row in payload[1]:
        if row.get("value") is None:
            continue
        try:
            year = int(row["date"])
        except (TypeError, ValueError):
            continue
        # Index dated to the middle of the year it describes, which is what an
        # annual average actually represents.
        out.append((date(year, 7, 1), float(row["value"])))
    out.sort()

    if len(out) < 20:
        raise RuntimeError(
            "CPI series returned only %d observations; refusing to overwrite "
            "a good series with a short one" % len(out))
    if verbose:
        print("  CPI: %d annual observations, %s to %s"
              % (len(out), out[0][0].year, out[-1][0].year))
    return out


def store(db, rows: list[tuple[date, float]], verbose: bool = True) -> int:
    """Upsert the series."""
    existing = {m.period: m for m in db.scalars(
        select(MacroSeries).where(MacroSeries.series == SERIES))}
    today = date.today()
    added = 0
    for period, value in rows:
        row = existing.get(period)
        if row is None:
            db.add(MacroSeries(series=SERIES, period=period, value=value,
                               source=SOURCE, fetched_on=today))
            added += 1
        else:
            row.value = value
            row.fetched_on = today
    db.commit()
    if verbose:
        print("  CPI stored: %d new, %d updated" % (added, len(rows) - added))
    return added


def refresh(db, verbose: bool = True) -> dict:
    try:
        rows = fetch(verbose)
    except Exception as e:
        if verbose:
            print("  CPI refresh failed (%s); keeping what we have" % e)
        return {"ok": False, "error": str(e)}
    added = store(db, rows, verbose)
    return {"ok": True, "observations": len(rows), "added": added}


def series(db) -> list[tuple[date, float]]:
    return [(m.period, m.value) for m in db.scalars(
        select(MacroSeries).where(MacroSeries.series == SERIES)
        .order_by(MacroSeries.period))]


def _trailing_rate(points: list[tuple[date, float]]) -> float:
    """The most recent full-year rate of change, used to extend the series."""
    if len(points) < 2:
        return FALLBACK_ANNUAL_INFLATION
    (d0, v0), (d1, v1) = points[-2], points[-1]
    if v0 <= 0 or v1 <= 0:
        return FALLBACK_ANNUAL_INFLATION
    years = max(0.5, (d1 - d0).days / 365.25)
    return (v1 / v0) ** (1.0 / years) - 1.0


def index_on(points: list[tuple[date, float]], when: date) -> float | None:
    """
    The price index on a given day.

    Between observations the index is interpolated geometrically, because
    prices compound rather than rise in a straight line. Before the first
    observation there is no answer. After the last, the most recent rate is
    carried forward -- an assumption, labelled as one wherever it is used.
    """
    if not points:
        return None
    if when <= points[0][0]:
        return points[0][1] if when == points[0][0] else None

    for i in range(1, len(points)):
        d0, v0 = points[i - 1]
        d1, v1 = points[i]
        if when <= d1:
            span = (d1 - d0).days
            if span <= 0 or v0 <= 0 or v1 <= 0:
                return v1
            frac = (when - d0).days / span
            return v0 * ((v1 / v0) ** frac)

    d_last, v_last = points[-1]
    rate = _trailing_rate(points)
    years = (when - d_last).days / 365.25
    return v_last * ((1.0 + rate) ** years)


def is_extrapolated(points: list[tuple[date, float]], when: date) -> bool:
    return bool(points) and when > points[-1][0]


def inflation_between(points, start: date, end: date) -> float | None:
    """Total price increase between two dates, as a fraction."""
    a, b = index_on(points, start), index_on(points, end)
    if not a or not b or a <= 0:
        return None
    return b / a - 1.0


def real_return(nominal_pct: float | None, points, start: date,
                end: date) -> float | None:
    """
    A nominal return restated in constant purchasing power.

    real = (1 + nominal) / (1 + inflation) - 1

    Subtracting inflation from the return is the common shortcut and it is
    wrong by a wide margin at Egyptian rates: a 50% nominal return with 25%
    inflation is 20% real, not 25%.
    """
    if nominal_pct is None:
        return None
    infl = inflation_between(points, start, end)
    if infl is None or infl <= -1:
        return None
    return ((1.0 + nominal_pct / 100.0) / (1.0 + infl) - 1.0) * 100.0


def describe(db, *, with_points: bool = False) -> dict:
    """
    Everything the site needs to explain the figure and its limits.

    `with_points` also returns the index itself. The browser needs it because
    the historical scenario tools ran on a flat assumed rate while the company
    pages used this series, so the same holding period produced two different
    real returns depending on which page you were standing on.
    """
    points = series(db)
    if not points:
        return {"available": False}
    last_d, last_v = points[-1]
    rate = _trailing_rate(points)
    return {
        "available": True,
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "first_year": points[0][0].year,
        "last_year": last_d.year,
        "latest_annual_rate_pct": round(rate * 100, 2),
        "note": (
            "Real figures use the World Bank's consumer price index for Egypt, "
            "which is published once a year. Values between yearly readings are "
            "interpolated, and beyond the last reading (%d) prices are assumed "
            "to keep rising at %.1f%% a year — the most recent measured rate. "
            "So a real return is a good guide over several years and only "
            "approximate over a few months."
            % (last_d.year, rate * 100)),
        "short_note": "adjusted for Egyptian inflation",
        **({"points": [[d.isoformat(), v] for d, v in points],
            "trailing_rate": rate} if with_points else {}),
    }
