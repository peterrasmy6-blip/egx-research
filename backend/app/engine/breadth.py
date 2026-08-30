"""
What the market as a whole did, beyond the index level.

Why breadth rather than just an index
-------------------------------------
An index can rise while most shares fall. Egypt's is concentrated enough that
a good day for two or three large banks carries the whole number, and a reader
looking only at the index would conclude the market was healthy on a day when
four companies in five went down.

Breadth answers the question the index cannot: how many companies actually
participated. A rise on narrow breadth and a rise on broad breadth are
different events, and the difference is usually the more informative half.

What is counted
---------------
Only companies that genuinely traded that session. A share that did not trade
carries yesterday's price forward, and counting it as "unchanged" would put
dozens of dormant companies into the middle of every distribution and flatten
everything. On this exchange that is not a rounding error — a quarter of the
listed companies can be untraded on a given day.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select, func

from ..models import Price, Security, NON_TRADED_SOURCES

# A move smaller than this is noise, not a direction. The EGX quotes to two
# decimals, so a sub-0.1% move on a low-priced share is often a single tick.
FLAT_THRESHOLD_PCT = 0.1


def _sessions(db, limit: int = 2) -> list[date]:
    return [d for (d,) in db.execute(
        select(Price.d).where(Price.source.notin_(NON_TRADED_SOURCES))
        .distinct().order_by(Price.d.desc()).limit(limit))]


def daily(db) -> dict:
    """Breadth for the most recent session."""
    days = _sessions(db, 2)
    if len(days) < 2:
        return {"available": False,
                "reason": "Not enough trading history to compare two sessions."}
    today, prev = days[0], days[1]

    rows = db.execute(
        select(Security.ticker, Security.name_en, Security.sector,
               Price.d, Price.close, Price.volume)
        .join(Price, Price.security_id == Security.id)
        .where(Security.asset_type == "equity",
               Security.listing_status == "listed",
               Price.d.in_([today, prev]),
               Price.source.notin_(NON_TRADED_SOURCES),
               Price.suspect.is_(None) | (Price.suspect == False))  # noqa: E712
    ).all()

    by_ticker: dict[str, dict] = {}
    for ticker, name, sector, d, close, vol in rows:
        rec = by_ticker.setdefault(ticker, {"name": name, "sector": sector})
        if d == today:
            rec["close"], rec["volume"] = close, vol
        else:
            rec["prev"] = close

    moves = []
    for ticker, r in by_ticker.items():
        if not r.get("close") or not r.get("prev") or r["prev"] <= 0:
            continue
        # Not traded today: the price is carried forward, not agreed on.
        if not r.get("volume"):
            continue
        moves.append({
            "ticker": ticker, "name": r["name"], "sector": r["sector"],
            "change_pct": round((r["close"] / r["prev"] - 1) * 100, 2),
            "close": r["close"], "value": (r["close"] or 0) * (r["volume"] or 0),
        })

    if not moves:
        return {"available": False,
                "reason": "No company traded in the most recent session."}

    up = [m for m in moves if m["change_pct"] > FLAT_THRESHOLD_PCT]
    down = [m for m in moves if m["change_pct"] < -FLAT_THRESHOLD_PCT]
    flat = [m for m in moves if abs(m["change_pct"]) <= FLAT_THRESHOLD_PCT]

    ranked = sorted(moves, key=lambda m: m["change_pct"])
    by_value = sorted(moves, key=lambda m: -m["value"])

    # Sector direction, but only where enough companies traded to mean
    # anything. One company is not a sector.
    sectors: dict[str, list] = {}
    for m in moves:
        if m["sector"]:
            sectors.setdefault(m["sector"], []).append(m["change_pct"])
    sector_rows = []
    for name, vals in sectors.items():
        if len(vals) < 3:
            continue
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        median = (vals_sorted[n // 2] if n % 2
                  else (vals_sorted[n // 2 - 1] + vals_sorted[n // 2]) / 2)
        sector_rows.append({
            "sector": name, "median_pct": round(median, 2),
            "companies": n,
            "up": sum(1 for v in vals if v > FLAT_THRESHOLD_PCT),
            "down": sum(1 for v in vals if v < -FLAT_THRESHOLD_PCT),
        })
    sector_rows.sort(key=lambda r: -r["median_pct"])

    traded = len(moves)
    total_value = sum(m["value"] for m in moves)

    return {
        "available": True,
        "session": today.isoformat(),
        "previous_session": prev.isoformat(),
        "traded": traded,
        "advancing": len(up),
        "declining": len(down),
        "unchanged": len(flat),
        "advance_decline_ratio": (round(len(up) / len(down), 2)
                                  if down else None),
        "share_advancing_pct": round(len(up) / traded * 100, 1),
        "total_value_traded": round(total_value, 2),
        "best": ranked[-5:][::-1],
        "worst": ranked[:5],
        "most_traded": by_value[:5],
        "sectors": sector_rows,
        "note": (
            "Counts only the %d companies that actually traded on %s. A share "
            "that did not trade keeps yesterday's price, and counting it as "
            "unchanged would put dozens of dormant companies in the middle of "
            "the distribution."
            % (traded, today.isoformat())),
    }


def participation(db, days: int = 30) -> dict:
    """
    How much of the exchange is actually trading, over recent sessions.

    A useful health measure in its own right: when participation falls, the
    prices being quoted are increasingly stale even though the screen looks
    normal.
    """
    sessions = _sessions(db, days)
    if not sessions:
        return {"available": False}
    cutoff = min(sessions)

    rows = db.execute(
        select(Price.d,
               func.count(Price.id),
               func.sum(func.iif(Price.volume > 0, 1, 0)))
        .join(Security, Security.id == Price.security_id)
        .where(Security.asset_type == "equity",
               Security.listing_status == "listed",
               Price.d >= cutoff,
               Price.source.notin_(NON_TRADED_SOURCES))
        .group_by(Price.d).order_by(Price.d)).all()

    points = [{"d": d.isoformat(),
               "quoted": quoted,
               "traded": traded or 0,
               "share_pct": round((traded or 0) / quoted * 100, 1) if quoted else 0}
              for d, quoted, traded in rows]
    if not points:
        return {"available": False}

    latest = points[-1]
    avg = round(sum(p["share_pct"] for p in points) / len(points), 1)
    return {
        "available": True,
        "points": points,
        "latest_pct": latest["share_pct"],
        "average_pct": avg,
        "sessions": len(points),
        "note": ("The share of listed companies that traded at all in each "
                 "session. When this falls, more of the prices on screen are "
                 "yesterday's."),
    }
