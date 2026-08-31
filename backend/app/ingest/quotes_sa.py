"""
A second source for the current price, for when the first one stops.

Why this exists
---------------
Yahoo Finance stopped publishing Egyptian closes after 26 August 2026. Not for
one company -- for all of them, CIB and Fawry and Elsewedy alike. The site was
not broken and the exchange had not closed; the only source of prices simply
went quiet, and every page on the platform froze on the same day with no way to
tell a reader whether that was the market or the plumbing.

A research site resting on one free source has that failure available to it
every single day. This is the second leg.

What it does and does not provide
---------------------------------
One request returns the current price for the whole exchange, from the same
listing page already fetched to build the ticker roster. That is all it
returns: no open, no high, no low, and above all **no volume**.

So these rows are quotes, not sessions. They are written under a source name
listed in NON_TRADED_SOURCES, which keeps them out of:

  * the trading-day calendar, so a quote can never invent a session;
  * liquidity, which is measured in traded value and would read a volume of
    zero as a dead stock;
  * returns and volatility, which must run on real closes.

The effect is deliberately narrow: the price at the top of a company page
becomes current again, while everything computed from history still comes from
history, and still stops where the history stops. A reader is told both dates
rather than being handed one number that quietly means two different things.

Why not simply replace Yahoo
----------------------------
Because a quote is not a close. It is whatever the page said at the moment it
was read, which during Cairo trading hours is an intraday figure. Building
history from it would produce a series of arbitrary daily snapshots dressed up
as closing prices -- worse than the gap it fills, because the gap is at least
honest.
"""
from __future__ import annotations

import html
import re
from datetime import date

from curl_cffi import requests as cr

SOURCE_NAME = "stockanalysis-quote"
# The same figure read while the exchange is still trading is not a closing
# price, it is wherever the share happened to be at that moment. Both are
# useful and they are not the same claim, so they are stored apart and the
# page says which it is showing.
SOURCE_NAME_INTRADAY = "stockanalysis-intraday"
SOURCE_URL = "https://stockanalysis.com/list/egyptian-stock-exchange/"

# The Egyptian Exchange trades Sunday to Thursday, 10:00 to 14:30 Cairo.
SESSION_OPEN_HOUR = 10.0
SESSION_CLOSE_HOUR = 14.5
TRADING_WEEKDAYS = (6, 0, 1, 2, 3)          # Sun-Thu, Python numbering

# The listing carries about 300 rows. Anything far below that is a broken or
# partial response, and acting on it would spray wrong prices across the site.
MIN_ROWS = 150

# A price outside this range is a parsing accident, not an Egyptian share.
SANE_PRICE = (0.01, 100_000.0)



def cairo_now():
    """Cairo wall-clock. Egypt keeps DST: UTC+3 in summer, UTC+2 in winter."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    return now + timedelta(hours=3 if 5 <= now.month <= 10 else 2)


def market_is_open(when=None) -> bool:
    """Whether the exchange is trading at this moment."""
    when = when or cairo_now()
    if when.weekday() not in TRADING_WEEKDAYS:
        return False
    hour = when.hour + when.minute / 60.0
    return SESSION_OPEN_HOUR <= hour < SESSION_CLOSE_HOUR


def _session():
    return cr.Session(impersonate="chrome")


def fetch_quotes(verbose: bool = True) -> dict[str, float]:
    """
    Current price for every company on the exchange listing, by ticker.

    Raises rather than returning a short dictionary: a half-read page must not
    be mistaken for "these are the only companies that have a price".
    """
    r = _session().get(SOURCE_URL, timeout=45)
    r.raise_for_status()
    text = r.text

    # The page is server-rendered Svelte, so the markup is littered with
    # <!--[--> comment markers between cells. Anchoring on the quote link and
    # then reading the following table cells survives that, and survives the
    # column order changing around it far better than a fixed-position regex.
    out: dict[str, float] = {}
    for m in re.finditer(r'href="/quote/egx/([A-Z0-9]{2,8})/"', text):
        ticker = m.group(1)
        if ticker in out:
            continue
        window = text[m.end():m.end() + 1600]
        cells = [html.unescape(c).strip()
                 for c in re.findall(r"<td[^>]*>([^<]*)</td>", window)]
        # name, market cap, price, % change, revenue
        if len(cells) < 3:
            continue
        price = _to_number(cells[2])
        if price is not None and SANE_PRICE[0] <= price <= SANE_PRICE[1]:
            out[ticker] = price

    if len(out) < MIN_ROWS:
        raise RuntimeError(
            "EGX listing returned only %d usable prices; the page layout has "
            "probably changed. Refusing to publish a partial price set."
            % len(out))

    if verbose:
        print("  second-source quotes: %d companies" % len(out))
    return out


def _to_number(cell: str) -> float | None:
    cell = cell.replace(",", "").strip()
    if not cell or cell in {"-", "n/a", "N/A"}:
        return None
    try:
        return float(cell)
    except ValueError:
        return None


# --------------------------------------------------------------------------
def sync_quotes_second_source(db, verbose: bool = True) -> dict:
    """
    Store a current price for any company whose history has fallen behind.

    Only companies that need it are touched. Where the primary source is
    publishing normally its close is already the newest row, and adding a quote
    beside it would gain nothing and risk overwriting a real close with an
    intraday figure.
    """
    from sqlalchemy import select, func
    from ..models import Price, Security, NON_TRADED_SOURCES

    try:
        quotes = fetch_quotes(verbose=verbose)
    except Exception as e:                                      # noqa: BLE001
        if verbose:
            print("  second source unavailable: %s" % str(e)[:120])
        return {"available": False, "reason": str(e), "written": 0}

    now = cairo_now()
    today = now.date()
    intraday = market_is_open(now)
    source = SOURCE_NAME_INTRADAY if intraday else SOURCE_NAME
    if verbose and intraday:
        print("  the exchange is open; these are intraday prices, not closes")

    # The newest genuine close we hold per security.
    newest = dict(db.execute(
        select(Price.security_id, func.max(Price.d))
        .where(Price.source.notin_(NON_TRADED_SOURCES))
        .group_by(Price.security_id)).all())

    secs = db.scalars(select(Security).where(
        Security.asset_type == "equity",
        Security.listing_status == "listed")).all()

    written = skipped = 0
    for sec in secs:
        price = quotes.get(sec.ticker)
        if price is None:
            continue
        # A real close from today beats any quote.
        if newest.get(sec.id) == today:
            skipped += 1
            continue
        row = db.scalar(select(Price).where(
            Price.security_id == sec.id, Price.d == today,
            Price.source.in_((SOURCE_NAME, SOURCE_NAME_INTRADAY))))
        if row is None:
            db.add(Price(security_id=sec.id, d=today,
                         open=None, high=None, low=None,
                         close=price, adj_close=price,
                         volume=0, currency=sec.currency or "EGP",
                         source=source))
        else:
            row.close = price
            row.adj_close = price
            # A run after the close upgrades the morning's intraday row.
            row.source = source
        written += 1

    db.commit()
    if verbose:
        print("  second-source prices: %d written, %d already current"
              % (written, skipped))
    return {"available": True, "written": written, "skipped": skipped,
            "as_of": today.isoformat(), "source": source,
            "intraday": intraday, "quotes": len(quotes)}
