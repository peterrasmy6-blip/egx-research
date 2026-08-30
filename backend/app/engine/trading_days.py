"""
Trading-day validation.

Why this exists
---------------
On Thursday 27 August 2026 the Egyptian Exchange was closed for a public
holiday. The data source nonetheless emitted price bars for 16 securities that
day -- every one with **zero volume** and a price carried over from Wednesday.

That is enough to do real damage. The platform would have reported Thursday as
the latest market date, implying the exchange had traded and that its prices
were current. A "last updated" date that is a day later than reality is exactly
the kind of small, confident falsehood this platform is built to avoid.

The rule
--------
A date is a real trading session only if a meaningful share of the market
actually changed hands on it. On genuine EGX days roughly 185 of ~198 securities
trade; on the holiday, none did. A threshold of 20% separates the two cases with
an enormous margin, so ordinary quiet days are never mistaken for closures.

Phantom bars are deleted rather than merely hidden: leaving them in would skew
returns, volatility and the charts for the affected companies.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select, func, delete, case

# Share of securities that must actually trade for a date to count as a session.
MIN_TRADING_SHARE = 0.20

# Share of a NORMAL session's bar count that a date must carry before it counts
# as a finished session at all.
#
# This exists because `share` above is traded/bars -- a ratio among the
# securities that reported. On a day when the source had published only seven
# companies, all seven had traded, so the ratio was 1.0 and the date was
# accepted as the market's latest session on the strength of seven names out of
# 269. The site then announced that date as its data date, the deploy job
# compared it against today, decided the close was already live, and skipped --
# so the other 262 companies were never fetched. A partial session that claims
# to be a whole one is self-perpetuating, which is why this is a floor on
# coverage rather than a warning.
MIN_SESSION_COVERAGE = 0.60

# How many recent sessions define "normal". Long enough to be stable, short
# enough to follow a universe that grows or shrinks.
COVERAGE_WINDOW = 20


def analyse_dates(db, since: date | None = None) -> list[dict]:
    """Per-date counts of how many securities posted a bar and how many traded."""
    from ..models import Price as P, NON_TRADED_SOURCES

    q = (select(P.d,
                func.count(P.id).label("bars"),
                func.sum(case((P.volume > 0, 1), else_=0)).label("traded"))
         .where(P.source.notin_(NON_TRADED_SOURCES))
         .group_by(P.d).order_by(P.d))
    if since:
        q = q.where(P.d >= since)

    out = []
    for d, bars, traded in db.execute(q).all():
        traded = traded or 0
        out.append({"date": d, "bars": bars, "traded": traded,
                    "share": (traded / bars) if bars else 0.0})
    return out


def find_phantom_dates(db, since: date | None = None) -> list[dict]:
    """
    Dates that look like closures the source reported anyway.

    Only flags dates carrying a small number of bars *and* almost no trading --
    both conditions, so a genuinely thin but real session is left alone.
    """
    rows = analyse_dates(db, since)
    if not rows:
        return []

    typical_bars = sorted(r["bars"] for r in rows)[len(rows) // 2]

    phantoms = []
    for r in rows:
        if r["share"] >= MIN_TRADING_SHARE:
            continue
        # A real session where trading genuinely dried up would still have the
        # usual number of listings quoted.
        if r["bars"] >= typical_bars * 0.5:
            continue
        phantoms.append(r)
    return phantoms


def purge_phantom_dates(db, since: date | None = None,
                        verbose: bool = True) -> dict:
    """Remove price bars belonging to non-sessions."""
    from ..models import Price as P, NON_TRADED_SOURCES

    phantoms = find_phantom_dates(db, since)
    removed = 0
    for r in phantoms:
        n = db.execute(delete(P).where(P.d == r["date"])).rowcount or 0
        removed += n
        if verbose:
            print("  removed %d phantom bars for %s (%d quoted, %d traded)"
                  % (n, r["date"], r["bars"], r["traded"]))
    db.commit()

    if verbose and not phantoms:
        print("  no phantom trading days found")
    return {"dates_removed": len(phantoms), "bars_removed": removed,
            "dates": [str(r["date"]) for r in phantoms]}


def typical_bar_count(rows: list[dict], window: int = COVERAGE_WINDOW) -> float:
    """
    How many securities a normal recent session carries.

    The median rather than the maximum, so one unusually complete day does not
    set a bar every other day fails to clear.
    """
    counts = sorted(r["bars"] for r in rows[-window:] if r["bars"])
    if not counts:
        return 0.0
    mid = len(counts) // 2
    return float(counts[mid] if len(counts) % 2
                 else (counts[mid - 1] + counts[mid]) / 2)


def latest_session(db) -> date | None:
    """
    The most recent date the market genuinely traded, and finished trading.

    Two conditions, and the second is the one that matters here. A date must
    have a normal proportion of its securities actually trading, AND carry a
    normal number of securities at all. Without the second, a half-fetched day
    -- seven companies out of 269 -- looked like a complete session because all
    seven of them had traded.
    """
    from ..models import Price as P, NON_TRADED_SOURCES

    rows = analyse_dates(db)
    if not rows:
        return db.scalar(select(func.max(P.d)))

    normal = typical_bar_count(rows)
    floor = normal * MIN_SESSION_COVERAGE

    for r in reversed(rows):
        if session_is_complete(r["bars"], r["share"], normal):
            return r["date"]
    return db.scalar(select(func.max(P.d)))


def session_is_complete(bars: int, share: float, normal: float) -> bool:
    """
    Whether a date is a finished session rather than a half-loaded one.

    Kept separate so the rule can be tested directly. `share` alone was the
    old rule, and it is a ratio among the securities that reported -- which is
    exactly why seven companies out of 269, all of which traded, scored 1.00.
    """
    if share < MIN_TRADING_SHARE:
        return False
    return normal <= 0 or bars >= normal * MIN_SESSION_COVERAGE


def partial_sessions(db, window: int = COVERAGE_WINDOW) -> list[dict]:
    """
    Recent dates that are real but incomplete, for reporting.

    These are not errors to delete -- the prices in them are genuine. They are
    dates the site must not describe as its data date, because most companies
    are missing from them.
    """
    rows = analyse_dates(db)
    if not rows:
        return []
    floor = typical_bar_count(rows) * MIN_SESSION_COVERAGE
    return [dict(r, expected=round(floor)) for r in rows[-window:]
            if r["bars"] < floor]
