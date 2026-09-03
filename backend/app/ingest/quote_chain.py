"""
A chain of price sources, tried in order, with the winner recorded.

Why a chain rather than a source
--------------------------------
Yahoo stopped publishing Egyptian closes on 26 August 2026 and every page on
this platform froze on that date. A second source was added and the site
recovered -- and then rested on that second source exactly as completely as it
had rested on the first. The lesson of an outage is not "use a different
source"; it is that any single source is a single point of failure and the
next outage is somebody else's turn.

So the sources are a list, tried in order, and the first that returns a
credible set wins. Adding a fourth is adding an entry.

Agreement is checked, not assumed
---------------------------------
Where two sources both carry a company, their prices are compared. Agreement
is the normal case and is worth confirming; disagreement is the interesting
case and is worth reporting, because on a scraped page it usually means a
layout change has shifted a column rather than that a share is worth two
different amounts.

A company the sources disagree about beyond the tolerance is left to the
existing price rather than being overwritten by a figure we cannot corroborate.
"""
from __future__ import annotations

from datetime import date

# Two sources agreeing this closely are reporting the same thing. Beyond it,
# one of them is reading the wrong column.
AGREE_TOLERANCE_PCT = 3.0

# Below this a response is broken rather than short, and acting on it would
# spray wrong prices across the site.
MIN_CREDIBLE = 120


def _sa_fetch(verbose: bool):
    from .quotes_sa import fetch_quotes
    return fetch_quotes(verbose=verbose)


def _am_fetch(verbose: bool):
    from .crosscheck import fetch_prices
    return {k: v for k, v in fetch_prices(verbose=verbose).items()
            if v is not None}


# In order of preference. stockanalysis leads because its figure is the one
# already cross-checked against the primary source's closes; african-markets
# follows and reaches rather more companies, so it is both a fallback and a
# way to fill the ones the leader misses.
SOURCES = [
    {"name": "stockanalysis-quote", "label": "stockanalysis.com",
     "fetch": _sa_fetch},
    {"name": "african-markets-quote", "label": "african-markets.com",
     "fetch": _am_fetch},
]


def gather(verbose: bool = True) -> dict:
    """
    Every source that answered, and what each returned.

    One source failing is survivable and is reported rather than raised: the
    point of a chain is that the next one is tried.
    """
    got, failed = {}, []
    for src in SOURCES:
        try:
            prices = src["fetch"](verbose)
        except Exception as e:                                  # noqa: BLE001
            failed.append((src["label"], str(e)[:90]))
            if verbose:
                print("  %s unavailable: %s" % (src["label"], str(e)[:80]))
            continue
        if len(prices) < MIN_CREDIBLE:
            failed.append((src["label"],
                           "only %d prices, treating as broken" % len(prices)))
            if verbose:
                print("  %s returned only %d prices; ignoring it"
                      % (src["label"], len(prices)))
            continue
        got[src["name"]] = prices
        if verbose:
            print("  %s: %d prices" % (src["label"], len(prices)))
    return {"sources": got, "failed": failed}


def reconcile(gathered: dict, verbose: bool = True) -> dict:
    """
    One price per ticker, plus what the sources said about each other.

    The first source in the chain that carries a ticker supplies its price.
    Where a later source also carries it, the two are compared: agreement is
    recorded as corroboration, and a disagreement past the tolerance withdraws
    the price entirely rather than picking a winner between two figures we
    have no way to referee.
    """
    order = [s["name"] for s in SOURCES if s["name"] in gathered["sources"]]
    prices: dict[str, dict] = {}
    disagreements = []

    for name in order:
        for ticker, value in gathered["sources"][name].items():
            if value is None or value <= 0:
                continue
            if ticker not in prices:
                prices[ticker] = {"price": value, "source": name,
                                  "corroborated_by": None}
                continue
            held = prices[ticker]
            diff = abs(value / held["price"] - 1) * 100
            if diff <= AGREE_TOLERANCE_PCT:
                held["corroborated_by"] = name
            else:
                disagreements.append({
                    "ticker": ticker, "held": round(held["price"], 4),
                    "held_source": held["source"],
                    "other": round(value, 4), "other_source": name,
                    "difference_pct": round(diff, 1)})

    for d in disagreements:
        prices.pop(d["ticker"], None)

    agreed = sum(1 for v in prices.values() if v["corroborated_by"])
    if verbose:
        print("  %d prices, %d corroborated by a second source, "
              "%d withdrawn over disagreement"
              % (len(prices), agreed, len(disagreements)))
    return {"prices": prices, "agreed": agreed,
            "disagreements": sorted(disagreements,
                                    key=lambda d: -d["difference_pct"])[:25],
            "sources_used": order,
            "failed": gathered.get("failed", [])}


def summary(result: dict) -> dict:
    """What the data-quality page needs to describe today's price sourcing."""
    by_source: dict[str, int] = {}
    for v in result["prices"].values():
        by_source[v["source"]] = by_source.get(v["source"], 0) + 1
    return {
        "as_of": date.today().isoformat(),
        "sources_used": result["sources_used"],
        "prices_by_source": by_source,
        "corroborated": result["agreed"],
        "total": len(result["prices"]),
        "withdrawn": len(result["disagreements"]),
        "disagreements": result["disagreements"],
        "failed": result["failed"],
    }


# --------------------------------------------------------------------------
def sync_chain_quotes(db, verbose: bool = True) -> dict:
    """
    Store one current price per company, from whichever source supplied it.

    Replaces the single-source version. The dating rules are unchanged and
    still matter: a quote read before the open belongs to the previous
    session, one read during trading is an intraday figure and is stored under
    its own source name, and a genuine close from the primary source always
    wins over any of this.
    """
    from sqlalchemy import select, func
    from ..models import Price, Security, NON_TRADED_SOURCES
    from .quotes_sa import cairo_now, market_is_open, quote_trading_date

    result = reconcile(gather(verbose=verbose), verbose=verbose)
    if not result["prices"]:
        return {"available": False, "written": 0,
                "reason": "no price source answered", **summary(result)}

    now = cairo_now()
    when = quote_trading_date(now)
    intraday = market_is_open(now)
    if verbose and intraday:
        print("  the exchange is open; these are intraday prices, not closes")
    if verbose and when != now.date():
        print("  before the open; filing these as the close of %s" % when)

    newest = dict(db.execute(
        select(Price.security_id, func.max(Price.d))
        .where(Price.source.notin_(NON_TRADED_SOURCES))
        .group_by(Price.security_id)).all())

    secs = db.scalars(select(Security).where(
        Security.asset_type == "equity",
        Security.listing_status == "listed")).all()

    written = skipped = 0
    for sec in secs:
        got = result["prices"].get(sec.ticker)
        if got is None:
            continue
        if newest.get(sec.id) == when:      # a real close beats any quote
            skipped += 1
            continue
        source = got["source"] + ("-intraday" if intraday else "")
        row = db.scalar(select(Price).where(
            Price.security_id == sec.id, Price.d == when,
            Price.source.like("%quote%")))
        if row is None:
            db.add(Price(security_id=sec.id, d=when,
                         open=None, high=None, low=None,
                         close=got["price"], adj_close=got["price"],
                         volume=0, currency=sec.currency or "EGP",
                         source=source))
        else:
            row.close = got["price"]
            row.adj_close = got["price"]
            row.source = source
        written += 1

    db.commit()
    if verbose:
        print("  %d prices written, %d already current" % (written, skipped))
    out = summary(result)
    out.update({"available": True, "written": written, "skipped": skipped,
                "intraday": intraday, "as_of": when.isoformat()})
    return out
