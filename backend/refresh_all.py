"""
Full data refresh, in dependency order.

Order matters:
  universe -> prices/statements -> quotes -> integrity -> metrics ->
  valuations -> coverage
Metrics need clean prices; valuations need the metrics snapshot (sector median
multiples come from it); coverage reports on the finished state.

Modes
-----
  --daily    Prices only, short lookback. Fast (~5 min). For the nightly job.
  --weekly   Adds the universe roster and financial statements. Slow (~60 min).
  (default)  Everything, with a 10-year price backfill. For a first build.

The daily job deliberately does NOT refetch ten years of history or company
accounts. Prices change every day; annual statements do not, and the roster
rarely does. Refetching everything nightly would take an hour, hammer the free
source, and change almost nothing.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal
from app.models import init_db
from app.ingest.loader import (sync_universe, sync_prices, sync_fundamentals,
                               sync_quotes, resolve_isins, sync_funds,
                               ensure_retirement_reasons,
                               assess_coverage)
from app.engine.integrity import scan_universe, mark_bad_prints
from app.engine.trading_days import purge_phantom_dates
from app.engine.metrics import refresh_metrics
from app.engine.liquidity import refresh as refresh_liquidity
from app.engine import inflation as inflation_mod
from app.engine.valuation_batch import refresh_valuations


def main(mode: str = "full") -> None:
    init_db()

    do_universe = mode in ("full", "weekly")
    do_statements = mode in ("full", "weekly")
    # A short lookback still catches anything the source revised recently,
    # while keeping the nightly run quick.
    period = {"daily": "3mo", "weekly": "1y", "full": "10y"}[mode]

    print("=== MODE: %s (price lookback %s) ===" % (mode, period), flush=True)

    if do_universe:
        print("=== UNIVERSE ===", flush=True)
        print(sync_universe(verbose=False), flush=True)

    # Sectors, on every mode and not just a full rebuild.
    #
    # The database is cached between runs, so a company classified under an
    # older version of the rules keeps that label until the next full refresh
    # -- which is how a poultry farm stayed filed under Real Estate and a
    # cinema producer under Financial Services. This costs nothing (no network,
    # no queries beyond one pass over the companies) and makes a correction to
    # the rules take effect the next time anything runs at all.
    # Retirement reasons, on every mode for the same reason as sectors: the
    # database is cached between runs, and a row retired under older code
    # keeps its empty reason until something goes looking for it.
    print("=== RETIREMENT REASONS ===", flush=True)
    _rr_db = SessionLocal()
    try:
        n = ensure_retirement_reasons(_rr_db)
        print("  %d filled" % n, flush=True)
    finally:
        _rr_db.close()

    print("=== SECTORS ===", flush=True)
    from app.ingest.reclassify_sectors import reclassify
    _sec_db = SessionLocal()
    try:
        r = reclassify(_sec_db, verbose=False)
        print("  %d reclassified, %d unclassified, %d unchanged"
              % (r["reclassified"], r["cleared"], r["unchanged"]), flush=True)
    finally:
        _sec_db.close()

    # Funds, on every run.
    #
    # This step did not exist: sync_funds was written and then never called by
    # anything, so the forty Egyptian funds were loaded once by hand and never
    # again. On a machine with that old database they were simply there; on a
    # cold rebuild they were not, which is how the live site came to publish an
    # empty Funds section without a single error.
    #
    # A failure here is survivable -- sync_funds leaves the funds already
    # stored untouched and reports the error -- so it must not stop a price
    # refresh. verify_build is what refuses to publish a site with no funds.
    print("=== FUNDS ===", flush=True)
    try:
        fr = sync_funds(verbose=False)
        if fr.get("error"):
            print("  fund source failed: %s (keeping what we already hold)"
                  % fr["error"], flush=True)
        else:
            print("  %d funds: %d new, %d updated, %d closed"
                  % (fr.get("total", 0), fr.get("added", 0),
                     fr.get("updated", 0), fr.get("closed", 0)), flush=True)
    except Exception as _e:                                     # noqa: BLE001
        print("  fund step failed: %s (keeping what we already hold)" % _e,
              flush=True)

    print("=== PRICES & DIVIDENDS ===", flush=True)
    print(sync_prices(period=period, verbose=False), flush=True)

    # About a fifth of the exchange exists on the price source only under an
    # ISIN-form symbol, which carries a live quote but no history. Without this
    # step those companies -- Ezz Steel and Telecom Egypt among them -- show no
    # price at all. The quote is stored under its own source label so nothing
    # mistakes one bar for a series.
    if do_universe:
        print("=== RESOLVING ISIN SYMBOLS ===", flush=True)
        print(resolve_isins(verbose=False), flush=True)
    print("=== QUOTES (companies without history) ===", flush=True)
    print(sync_quotes(verbose=False), flush=True)

    if do_statements:
        print("=== FINANCIAL STATEMENTS ===", flush=True)
        print(sync_fundamentals(verbose=False), flush=True)

    db = SessionLocal()

    # Statements from the second source, for the companies the first skips.
    #
    # Only on a full refresh: it is one page-load per company per statement,
    # and the companies it serves are precisely those whose accounts the
    # primary source has never carried, so a day's delay costs nothing. It
    # never touches a company that already has statements, so it cannot alter
    # a figure that was already being published.
    if mode == "full":
        print("=== SECOND-SOURCE STATEMENTS ===", flush=True)
        from app.ingest.financials_sa import sync_financials_second_source
        _f_db = SessionLocal()
        try:
            fr = sync_financials_second_source(_f_db, only_missing=True,
                                               verbose=False)
            print("  %d companies filled, %d facts, %d without usable data"
                  % (fr["companies_filled"], fr["facts_written"],
                     fr["skipped"]), flush=True)
        except Exception as _e:                                 # noqa: BLE001
            print("  second-source statements failed: %s" % str(_e)[:120],
                  flush=True)
        finally:
            _f_db.close()

    # Consumer prices, so every multi-year return can also be shown in what the
    # money actually buys. Refreshed weekly -- the series is annual, so a daily
    # call would be pointless traffic. A failure here is not fatal: the stored
    # series stays and real figures keep working.
    if do_universe:
        print("=== CONSUMER PRICES ===", flush=True)
        print(inflation_mod.refresh(db, verbose=True), flush=True)

    # The source emits carried-forward, zero-volume bars on Egyptian public
    # holidays. Left in, they make the site claim the market traded on a day it
    # was closed. Removed before anything is calculated from them.
    # A second source for the current price.
    #
    # The primary source went silent after 26 August 2026 -- every Egyptian
    # company at once -- and the whole site froze on that date with no way for
    # a reader to tell the market from the plumbing. This only fills the price
    # at the top of a page, and only for companies whose history has fallen
    # behind; it writes no volume and creates no session, so nothing measured
    # from history is touched by it.
    print("=== SECOND-SOURCE PRICES ===", flush=True)
    from app.ingest.quote_chain import sync_chain_quotes
    _q_db = SessionLocal()
    try:
        sync_chain_quotes(_q_db, verbose=True)
    except Exception as _e:                                     # noqa: BLE001
        print("  price chain failed: %s" % str(_e)[:120], flush=True)
    finally:
        _q_db.close()

    print("=== TRADING DAYS ===", flush=True)
    purge_phantom_dates(db, verbose=True)

    print("=== PRICE INTEGRITY ===", flush=True)
    # Bad prints first: a bar that leaps and returns is a source error, and if
    # it is left in the series the corporate-action scan mistakes it for a split
    # and suppresses perfectly good return figures on either side of it.
    mark_bad_prints(db, verbose=True)
    r = scan_universe(db, verbose=False)
    print("  clean %d, flagged %d" % (r["clean"], r["flagged"]), flush=True)

    print("=== METRICS ===", flush=True)
    refresh_metrics(db, verbose=False)

    # Liquidity depends on nothing but prices, but is stored on the metrics row,
    # so it runs straight after them.
    # An independent witness on our prices, weekly. It never overwrites
    # anything -- two sources disagreeing means a person should look, and
    # silently picking one would hide exactly that signal.
    if do_universe:
        print("=== PRICE CROSS-CHECK ===", flush=True)
        try:
            from app.ingest.crosscheck import refresh as _cross
            _cross(db, verbose=True)
        except Exception as _e:
            print("  cross-check failed: %s" % _e, flush=True)

    print("=== LIQUIDITY ===", flush=True)
    refresh_liquidity(db, verbose=True)

    print("=== VALUATIONS ===", flush=True)
    refresh_valuations(db, verbose=True)
    db.close()

    print("=== COVERAGE ===", flush=True)
    print(assess_coverage(verbose=True), flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group()
    g.add_argument("--daily", action="store_true", help="prices only (fast)")
    g.add_argument("--weekly", action="store_true", help="prices + roster + statements")
    args = p.parse_args()
    main("daily" if args.daily else "weekly" if args.weekly else "full")
