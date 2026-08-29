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


def analyse_dates(db, since: date | None = None) -> list[dict]:
    """Per-date counts of how many securities posted a bar and how many traded."""
    from ..models import Price as P

    q = (select(P.d,
                func.count(P.id).label("bars"),
                func.sum(case((P.volume > 0, 1), else_=0)).label("traded"))
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
    from ..models import Price as P

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


def latest_session(db) -> date | None:
    """The most recent date the market genuinely traded."""
    from ..models import Price as P

    rows = analyse_dates(db)
    for r in reversed(rows):
        if r["share"] >= MIN_TRADING_SHARE:
            return r["date"]
    return db.scalar(select(func.max(P.d)))
