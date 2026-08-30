"""
The week, summarised.

Why a weekly digest at all
--------------------------
Someone who opens this site every day is not the reader we can help most. The
reader we can help is the one who checks in occasionally, and who otherwise
learns about the Egyptian market from whichever share moved 15% that morning.
A weekly page is the smallest thing that gives them a fair picture: what the
market as a whole did, how many companies actually took part, and which moves
were large enough and liquid enough to be worth a second look.

Why weekly and not daily
------------------------
Because daily movement on this exchange is mostly noise, and a daily digest
would train exactly the habit the rest of the site argues against. A week is
long enough that the number means something and short enough to still be news.

How it is delivered, given no server and no budget
--------------------------------------------------
There is no mailing list. Sending email needs a service, a service needs an
account and eventually money, and it would need somewhere to store subscriber
addresses -- which this project deliberately does not have. So the digest is a
page that is rebuilt with the data, plus an RSS feed, which any reader can
subscribe to without giving us anything. That is stated on the page rather than
leaving people waiting for an email that will never arrive.

What is deliberately not here
-----------------------------
No share of the week, no "one to watch", no interpretation of why anything
moved. Every entry is a measured number with the company beside it. The moment
a digest starts explaining moves it is inventing narrative, and the honest
answer for almost every weekly move on this exchange is that nobody knows.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from ..models import Dividend, Price, Security, SecurityMetrics, NON_TRADED_SOURCES

# A move only earns a place in the digest if the share actually trades. On a
# thin counter a single small order moves the close 15%, and listing that beside
# a real move in a liquid company would give the two equal weight.
MIN_ADTV_FOR_MOVERS = 1_000_000.0     # EGP of value per day, 90-day average
MOVERS_SHOWN = 8

# A week of calendar days. The exchange trades Sunday to Thursday, so the
# session nearest this far back is used rather than a fixed session count,
# which would drift across holidays.
WINDOW_DAYS = 7


def _sessions(db, limit: int = 400) -> list[date]:
    return [d for (d,) in db.execute(
        select(Price.d).where(Price.source.notin_(NON_TRADED_SOURCES))
        .distinct().order_by(Price.d.desc()).limit(limit))]


def _closest_session(sessions: list[date], target: date):
    """The session nearest the target date, from the sessions we hold."""
    return min(sessions, key=lambda d: abs((d - target).days)) if sessions else None


def build(db) -> dict:
    """The week's summary, or a clear statement of why there isn't one."""
    sessions = _sessions(db)
    if len(sessions) < 2:
        return {"available": False,
                "reason": "We do not hold enough trading history to compare "
                          "one week with the last."}

    latest = sessions[0]
    start = _closest_session(sessions, latest - timedelta(days=WINDOW_DAYS))
    if start is None or start >= latest:
        return {"available": False,
                "reason": "We hold only one session in the last week, so there "
                          "is nothing to compare it against."}

    span_days = (latest - start).days

    rows = db.execute(
        select(Security.ticker, Security.name_en, Security.sector,
               Price.d, Price.close, Price.volume)
        .join(Price, Price.security_id == Security.id)
        .where(Security.asset_type == "equity",
               Security.listing_status == "listed",
               Price.d.in_([start, latest]),
               Price.source.notin_(NON_TRADED_SOURCES),
               Price.suspect.is_(None) | (Price.suspect == False))  # noqa: E712
    ).all()

    by_ticker: dict[str, dict] = {}
    for ticker, name, sector, d, close, volume in rows:
        if close is None or close <= 0:
            continue
        slot = by_ticker.setdefault(
            ticker, {"name": name, "sector": sector, "start": None, "end": None,
                     "volume": 0})
        slot["start" if d == start else "end"] = close
        slot["volume"] += volume or 0

    liquidity = dict(db.execute(
        select(Security.ticker, SecurityMetrics.adtv_90d)
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)).all())

    changes = []
    for ticker, slot in by_ticker.items():
        if not slot["start"] or not slot["end"]:
            continue
        slot["ticker"] = ticker
        slot["change_pct"] = (slot["end"] / slot["start"] - 1) * 100
        slot["adtv_90d"] = liquidity.get(ticker)
        changes.append(slot)

    if not changes:
        return {"available": False,
                "reason": "No company has a usable price at both ends of the "
                          "week, so nothing can be measured."}

    rose = sum(1 for c in changes if c["change_pct"] > 0)
    fell = sum(1 for c in changes if c["change_pct"] < 0)
    flat = len(changes) - rose - fell

    ordered = sorted(changes, key=lambda c: c["change_pct"])
    mid = len(ordered) // 2
    median = (ordered[mid]["change_pct"] if len(ordered) % 2
              else (ordered[mid - 1]["change_pct"] + ordered[mid]["change_pct"]) / 2)

    tradeable = [c for c in changes
                 if (c["adtv_90d"] or 0) >= MIN_ADTV_FOR_MOVERS]
    thin_excluded = len(changes) - len(tradeable)
    ranked = sorted(tradeable, key=lambda c: c["change_pct"], reverse=True)

    def trim(items):
        return [{"ticker": c["ticker"], "name": c["name"], "sector": c["sector"],
                 "change_pct": round(c["change_pct"], 2),
                 "price": round(c["end"], 4),
                 "adtv_90d": c["adtv_90d"]} for c in items]

    # Sectors, so a week that looks broad-based can be told from a week that
    # was one industry moving together.
    sectors: dict[str, list[float]] = {}
    for c in changes:
        if c["sector"]:
            sectors.setdefault(c["sector"], []).append(c["change_pct"])
    sector_moves = sorted(
        ({"sector": s,
          "median_change_pct": round(sorted(v)[len(v) // 2], 2),
          "companies": len(v)}
         for s, v in sectors.items() if len(v) >= 3),
        key=lambda x: x["median_change_pct"], reverse=True)

    # Dividends going ex in the coming fortnight: a date, not a suggestion.
    upcoming = [{
        "ticker": t, "name": n, "ex_date": ex.isoformat(),
        "amount_per_share": round(amt, 4), "currency": cur,
    } for t, n, ex, amt, cur in db.execute(
        select(Security.ticker, Security.name_en, Dividend.ex_date,
               Dividend.amount_per_share, Dividend.currency)
        .join(Dividend, Dividend.security_id == Security.id)
        .where(Dividend.ex_date >= latest,
               Dividend.ex_date <= latest + timedelta(days=14))
        .order_by(Dividend.ex_date)).all()]

    return {
        "available": True,
        "week_start": start.isoformat(),
        "week_end": latest.isoformat(),
        "span_days": span_days,
        "companies_measured": len(changes),
        "rose": rose, "fell": fell, "unchanged": flat,
        "median_change_pct": round(median, 2),
        "gainers": trim(ranked[:MOVERS_SHOWN]),
        "losers": trim(list(reversed(ranked))[:MOVERS_SHOWN]),
        "movers_min_adtv": MIN_ADTV_FOR_MOVERS,
        "thin_excluded": thin_excluded,
        "sector_moves": sector_moves,
        "dividends_upcoming": upcoming,
        "note": (
            "Measured between the closes of %s and %s -- the two sessions we "
            "hold nearest a week apart, so a public holiday shortens the "
            "window rather than silently shifting it. Risers and fallers are "
            "limited to companies trading at least EGP %s of value a day, "
            "because on a thin counter one small order moves the close by more "
            "than any news would; %d companies were excluded on that basis. "
            "Nothing here is a recommendation and no move is explained -- for "
            "most weekly moves on this exchange, nobody honestly knows why."
            % (start.isoformat(), latest.isoformat(),
               "{:,.0f}".format(MIN_ADTV_FOR_MOVERS), thin_excluded)),
    }


# --------------------------------------------------------------------------
def rss(d: dict, site_url: str, built_on: str) -> str:
    """
    The digest as an RSS feed.

    RSS costs nothing, needs no account, and asks the reader for no email
    address -- which is the only subscription this project can offer honestly.
    """
    import html as _html

    base = site_url.rstrip("/")
    items = []
    if d.get("available"):
        title = "EGX week to %s" % d["week_end"]
        if d["rose"] + d["fell"]:
            summary = ("%d companies rose, %d fell, median move %+.2f%%."
                       % (d["rose"], d["fell"], d["median_change_pct"]))
        else:
            summary = "No measurable movement."
        items.append((title, summary, base + "/weekly", d["week_end"]))

    def esc(x):
        return _html.escape(str(x), quote=True)

    body = "".join(
        "<item><title>%s</title><link>%s</link><guid isPermaLink=\"false\">%s</guid>"
        "<description>%s</description></item>"
        % (esc(t), esc(link), esc(link + "#" + key), esc(s))
        for t, s, link, key in items)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        "<title>EGX Research — the week on the Egyptian Exchange</title>"
        "<link>%s/weekly</link>"
        "<description>How the Egyptian Exchange moved this week: breadth, "
        "measured movers and upcoming ex-dividend dates. Not investment "
        "advice.</description>"
        "<language>en</language><lastBuildDate>%s</lastBuildDate>"
        "%s</channel></rss>\n" % (esc(base), esc(_rfc822(built_on)), body))


def _rfc822(day: str) -> str:
    """Feed readers expect RFC 822 dates, not ISO ones."""
    from datetime import datetime, timezone
    from email.utils import format_datetime
    try:
        d = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return day
    return format_datetime(d)
