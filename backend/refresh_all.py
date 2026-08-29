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
                               sync_quotes, resolve_isins,
                               assess_coverage)
from app.engine.integrity import scan_universe
from app.engine.trading_days import purge_phantom_dates
from app.engine.metrics import refresh_metrics
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

    # The source emits carried-forward, zero-volume bars on Egyptian public
    # holidays. Left in, they make the site claim the market traded on a day it
    # was closed. Removed before anything is calculated from them.
    print("=== TRADING DAYS ===", flush=True)
    purge_phantom_dates(db, verbose=True)

    print("=== PRICE INTEGRITY ===", flush=True)
    r = scan_universe(db, verbose=False)
    print("  clean %d, flagged %d" % (r["clean"], r["flagged"]), flush=True)

    print("=== METRICS ===", flush=True)
    refresh_metrics(db, verbose=False)

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
