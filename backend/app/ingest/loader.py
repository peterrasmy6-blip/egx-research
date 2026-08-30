"""
Automated data ingestion: universe -> prices -> dividends -> financial statements.

Principles enforced here:
  * A security is only admitted if the source actually returns price history.
  * Existing good data is never destroyed by a failed refresh.
  * Every run is written to `ingest_runs` so failures are visible, not silent.
  * Nothing is fabricated. Missing means missing.
"""
from __future__ import annotations

import time
import warnings
from datetime import datetime, date

import pandas as pd
import yfinance as yf
from sqlalchemy import select, delete, func

from ..db import SessionLocal
from ..models import (Security, Price, Dividend, FinancialFact,
                      IngestRun, FundProfile)

warnings.filterwarnings("ignore")

SOURCE = "yahoo"

# Yahoo throttles bursty clients. These settings keep us to a polite pace;
# without them a full universe refresh gets blocked partway through and the
# database silently stops filling up.
THROTTLE_SECONDS = 1.5
MAX_ATTEMPTS = 4


# After this many consecutive empty responses a security is treated as simply
# not carried by the source, and gets a single quick attempt instead of the
# full retry ladder. Without this, ~120 EGX tickers the source does not cover
# were costing 21 seconds each in backoff on every single run -- 40 minutes of
# waiting to learn nothing new.
DEAD_AFTER_FAILURES = 3

# Fund values we record ourselves, labelled so they are never mistaken for a
# traded price. Liquidity and trading-day detection both exclude them.
NAV_SOURCE = "egx-research-nav"


def _retry(fn, what: str = "", attempts: int | None = None):
    """
    Call `fn` with exponential backoff.

    Returns (value, error). A rate-limited or flaky request is retried rather
    than being mistaken for 'this security has no data' -- that distinction
    matters, because treating a throttle as absence would quietly drop real
    companies out of the universe.
    """
    delay = 3.0
    last = None
    tries = attempts if attempts is not None else MAX_ATTEMPTS
    for attempt in range(tries):
        try:
            val = fn()
            empty = val is None or (hasattr(val, "empty") and val.empty)
            if not empty:
                return val, None
            last = "empty response"
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
        if attempt < tries - 1:
            time.sleep(delay)
            delay *= 2
    return None, "%s %s" % (what, last)


def _log(db, job, target, status, rows=0, message=None, started=None):
    db.add(IngestRun(job=job, target=target, status=status, rows_written=rows,
                     message=(message or "")[:2000],
                     started_at=started or datetime.utcnow(),
                     finished_at=datetime.utcnow()))
    db.commit()


def _to_date(x):
    """Coerce anything date-like to a plain date, or None."""
    try:
        return pd.Timestamp(x).date()
    except Exception:
        return None


def _f(x):
    """Coerce to a clean float, or None. NaN is never stored as a number."""
    try:
        if x is None:
            return None
        v = float(x)
        return None if pd.isna(v) else v
    except Exception:
        return None


def _px(x):
    """
    A price, rounded to four decimals.

    The upstream feed returns float32 values widened to float64, so a price of
    139.28 arrives as 139.27999877929688. Rounding removes that artifact and
    stores the price that was actually quoted. It also keeps the database and
    the static export bit-identical, so the browser engine and the Python
    engine compute from exactly the same numbers.
    """
    v = _f(x)
    return None if v is None else round(v, 4)


# --------------------------------------------------------------------------
# 1. Universe
# --------------------------------------------------------------------------
def sync_universe(verbose: bool = True, use_cache: bool = False) -> dict:
    """
    Refresh the roster of EGX securities.

    Every discovered company is stored, including ones whose data turns out to
    be thin. Dropping a real listing because a free source is missing its
    accounts would misrepresent the exchange; instead the company is kept and
    labelled with what is actually known about it.
    """
    from .discovery import build_universe

    db = SessionLocal()
    started = datetime.utcnow()
    universe = build_universe(verbose=verbose, use_cache=use_cache)

    added = updated = 0
    seen: set[str] = set()

    for ticker, rec in universe.items():
        seen.add(ticker)
        ysym = rec["yahoo_symbol"]
        sec = db.scalar(select(Security).where(Security.ticker == ticker))
        if sec is None:
            sec = Security(ticker=ticker, yahoo_symbol=ysym,
                           name_en=rec["name"], first_seen=date.today())
            db.add(sec)
            added += 1
        else:
            updated += 1

        sec.yahoo_symbol = ysym
        sec.name_en = rec["name"] or sec.name_en
        sec.asset_type = "equity"
        sec.listing_status = "listed"
        sec.is_active = True
        sec.source_url = rec.get("source_url")
        sec.sources_listing = rec.get("sources", 1)
        # Every survivor of the reference filter is a confirmed listing: it is
        # either on a broker's live instrument list or carries real recent
        # price history. The old two-roster vote is kept only as a data point.
        sec.listing_confirmed = True
        if rec.get("data_note"):
            sec.data_note = rec["data_note"]
        elif sec.data_note and sec.data_note.startswith("No longer appears"):
            sec.data_note = None
        if rec.get("isin"):
            sec.isin = rec["isin"]
        # The classifier is the single source of truth for sectors, and it
        # already prefers a curated label over a guess. Keeping an old value
        # here meant a correction to the classifier never reached companies
        # already in the database -- which is how a hotel stayed filed under
        # Financial Services through three rounds of fixes. A company the
        # classifier can no longer place is unclassified rather than left
        # showing a label we no longer stand behind.
        sec.sector = rec.get("sector")
        db.commit()

    # Anything previously known but absent from the current roster is marked
    # delisted -- not deleted, because its price history stays valid and users
    # may still want to research it.
    stale = db.scalars(select(Security).where(
        Security.asset_type == "equity",
        Security.listing_status == "listed",
        Security.ticker.notin_(seen) if seen else False)).all()
    from .reference_universe import EXCLUDED
    for sec in stale:
        sec.listing_status = "delisted"
        # Also stand them down from the price fetch: chasing 60 dead tickers
        # every run costs minutes of throttled requests for nothing.
        sec.is_active = False
        kind_reason = EXCLUDED.get(sec.ticker)
        if kind_reason:
            sec.data_note = kind_reason[1]
        else:
            sec.data_note = (
                "Not in the reference stock universe and carries no price "
                "history from any source. Retired from search; its records are "
                "kept in case it lists again.")
    if stale:
        db.commit()

    # Backfill reasons for anything already retired.
    #
    # The loop above only reaches rows that are LISTED right now, because it is
    # driven by "what disappeared from the roster this run". A row retired by an
    # older version of this code -- before reasons were written at all -- is
    # never visited again, so an empty reason stayed empty forever. That is
    # invisible on a machine whose database saw the transition and permanent on
    # one that did not, which is exactly how this passed here and failed on CI.
    filled = ensure_retirement_reasons(db)
    if filled and verbose:
        print("  backfilled %d retirement reason(s)" % filled)

    if verbose:
        print("  universe stored: %d new, %d updated, %d marked delisted"
              % (added, updated, len(stale)))

    _log(db, "sync_universe", None, "ok", added + updated,
         "added=%d updated=%d delisted=%d" % (added, updated, len(stale)), started)
    db.close()
    return {"added": added, "updated": updated,
            "delisted": [s.ticker for s in stale], "total": len(universe)}


def sync_funds(verbose: bool = True) -> dict:
    """
    Load Egyptian investment funds.

    Funds are stored as securities with asset_type="fund" so search, comparison
    and the universe browser treat them uniformly, with the fund-only fields in
    `fund_profiles`.

    They deliberately get `data_quality="nav_only"`: the free source publishes a
    current NAV and trailing returns but no NAV history, so the backtester,
    what-if calculator and Monte Carlo cannot run on them. Saying that plainly
    is better than offering a tool that would silently produce nothing.
    """
    from .funds import fetch_funds, ticker_for, SOURCE_NAME

    db = SessionLocal()
    started = datetime.utcnow()
    try:
        rows = fetch_funds(verbose=verbose)
    except Exception as e:
        _log(db, "sync_funds", None, "failed", 0, str(e), started)
        if verbose:
            print("  fund source failed: %s" % e)
        db.close()
        return {"added": 0, "updated": 0, "error": str(e)}

    added = updated = 0
    seen = set()
    for f in rows:
        ticker = ticker_for(f["slug"])
        seen.add(ticker)
        sec = db.scalar(select(Security).where(Security.ticker == ticker))
        if sec is None:
            sec = Security(ticker=ticker, yahoo_symbol=ticker,
                           name_en=f["name"], first_seen=date.today())
            db.add(sec)
            added += 1
        else:
            updated += 1

        sec.name_en = f["name"]
        sec.asset_type = "fund"
        sec.listing_status = "listed"
        sec.is_active = True
        sec.currency = "EGP"
        sec.sector = f.get("category") or "Fund"
        sec.source = SOURCE_NAME
        sec.source_url = f.get("source_url")
        sec.data_quality = "nav_only"
        sec.data_note = ("This is an investment fund. Its current value (NAV) "
                         "and recent returns are available, but the free source "
                         "does not publish a history of daily NAVs. Tools that "
                         "need a price history - the what-if calculator, "
                         "backtesting and Monte Carlo - cannot be run on it.")
        sec.last_refreshed = datetime.utcnow()
        db.flush()

        prof = db.scalar(select(FundProfile)
                         .where(FundProfile.security_id == sec.id))
        if prof is None:
            prof = FundProfile(security_id=sec.id, slug=f["slug"])
            db.add(prof)
        prof.slug = f["slug"]
        prof.nav = f.get("nav")
        prof.ytd_pct = f.get("ytd_pct")
        prof.return_1y_pct = f.get("return_1y_pct")
        prof.since_inception_pct = f.get("since_inception_pct")
        prof.category = f.get("category")
        prof.fund_type = f.get("fund_type")
        prof.risk = f.get("risk")
        prof.has_nav_history = False
        prof.source = SOURCE_NAME
        # Record today's value as a price bar.
        #
        # No free source publishes a NAV history for Egyptian funds, which is
        # why funds cannot be charted or backtested here. But nothing stops us
        # keeping our own: every refresh stores the value it saw, so in a year
        # this platform will hold a series that does not exist anywhere else.
        # It costs one row per fund per day.
        if f.get("nav") and f["nav"] > 0:
            today = date.today()
            seen = db.scalar(select(Price).where(Price.security_id == sec.id,
                                                 Price.d == today))
            if seen is None:
                db.add(Price(security_id=sec.id, d=today,
                             open=None, high=None, low=None,
                             close=_px(f["nav"]), adj_close=_px(f["nav"]),
                             volume=0, currency="EGP", source=NAV_SOURCE))
        prof.source_url = f.get("source_url")
        prof.updated_at = datetime.utcnow()
        db.commit()

    # A fund that disappears from the source is marked, not deleted.
    stale = db.scalars(select(Security).where(
        Security.asset_type == "fund",
        Security.listing_status == "listed",
        Security.ticker.notin_(seen) if seen else False)).all()
    for sec in stale:
        sec.listing_status = "closed"
        sec.data_note = "This fund no longer appears in our source."
    if stale:
        db.commit()

    if verbose:
        print("  funds stored: %d new, %d updated, %d closed"
              % (added, updated, len(stale)))
    _log(db, "sync_funds", None, "ok", added + updated,
         "added=%d updated=%d closed=%d" % (added, updated, len(stale)), started)
    db.close()
    return {"added": added, "updated": updated, "closed": len(stale),
            "total": len(rows)}


def ensure_retirement_reasons(db, verbose: bool = False) -> int:
    """
    Give every retired security a stated reason, and never overwrite a good one.

    Nothing may be dropped from the universe silently: a ticker that vanishes
    from search with no explanation is indistinguishable from a bug. This is
    idempotent by design, so it can run on every refresh and repair a database
    retired under older code.
    """
    from .reference_universe import EXCLUDED, RENAMES

    fixed = 0
    rows = db.scalars(select(Security).where(
        Security.asset_type == "equity",
        Security.listing_status != "listed")).all()

    for sec in rows:
        # Where the reference list states why a ticker is excluded, that reason
        # is authoritative and replaces whatever is there. It is not enough to
        # fill only the empty ones: CCAPP read "no financial statements were
        # found", which is true, is not why it was retired, and looked like a
        # perfectly good note. A wrong explanation hides better than a missing
        # one.
        kind_reason = EXCLUDED.get(sec.ticker)
        if kind_reason:
            want = kind_reason[1]
        elif sec.ticker in RENAMES:
            want = ("Renamed. The company is covered once, as %s."
                    % RENAMES[sec.ticker])
        elif sec.data_note:
            # No authoritative reason for this one, and something is already
            # recorded. Leave it: it is the best we have.
            continue
        else:
            want = ("Not in the reference stock universe and carries no price "
                    "history from any source. Retired from search; its records "
                    "are kept in case it lists again.")
        if sec.data_note != want:
            sec.data_note = want
            fixed += 1

    if fixed:
        db.commit()
        if verbose:
            print("  filled %d missing retirement reason(s)" % fixed)
    return fixed


def assess_coverage(verbose: bool = True) -> dict:
    """
    Record what data each security actually has.

    Runs after ingestion and drives the "Data quality" badge shown on every
    company page. Measured, never assumed.
    """
    db = SessionLocal()
    counts = {"full": 0, "partial": 0, "price_only": 0, "none": 0}

    for sec in db.scalars(select(Security)).all():
        if sec.asset_type == "fund":
            # Funds are scored on their own terms; they have no price series.
            counts["nav_only"] = counts.get("nav_only", 0) + 1
            continue
        n_px = db.scalar(select(func.count(Price.id))
                         .where(Price.security_id == sec.id)) or 0
        n_fa = db.scalar(select(func.count(FinancialFact.id))
                         .where(FinancialFact.security_id == sec.id)) or 0
        n_dv = db.scalar(select(func.count(Dividend.id))
                         .where(Dividend.security_id == sec.id)) or 0
        rng = db.execute(select(func.min(Price.d), func.max(Price.d))
                         .where(Price.security_id == sec.id)).first()

        sec.price_start, sec.price_end = (rng[0], rng[1]) if rng else (None, None)
        sec.has_statements = n_fa > 0

        # A retired security already carries the reason it was retired, and
        # that matters more to a reader than how complete its data happens to
        # be. Overwriting it here silently erased the audit trail -- FAITA lost
        # "the dollar-quoted class of Faisal Islamic Bank" and was left with
        # nothing at all.
        keep_note = sec.listing_status != "listed"

        if n_px == 0:
            sec.data_quality = "none"
            if not keep_note:
                sec.data_note = ("No price history is available from our free "
                                 "sources for this security.")
        elif n_fa == 0:
            sec.data_quality = "price_only"
            if not keep_note:
                sec.data_note = ("Prices are available, but no financial "
                                 "statements were found from free sources, so "
                                 "profitability and valuation measures cannot "
                                 "be calculated.")
        elif n_px < 250 or n_fa < 200:
            sec.data_quality = "partial"
            if not keep_note:
                sec.data_note = ("Some information is unavailable from reliable "
                                 "free sources. Figures shown are based on what "
                                 "we hold.")
        else:
            sec.data_quality = "full"
            if not keep_note:
                sec.data_note = None

        counts[sec.data_quality] += 1
    db.commit()
    if verbose:
        print("  coverage:", counts)
    db.close()
    return counts


# --------------------------------------------------------------------------
# 2. Prices + dividends
# --------------------------------------------------------------------------
def sync_prices(ticker=None, period: str = "10y", verbose: bool = True) -> dict:
    db = SessionLocal()
    # Funds are excluded: they have no exchange symbol, so every fetch would
    # fail after the full retry ladder -- 40 funds x 21 seconds of backoff for
    # nothing. Their NAV comes from `sync_funds` instead.
    q = select(Security).where(Security.is_active == True,       # noqa: E712
                               Security.asset_type != "fund")
    if ticker:
        q = q.where(Security.ticker == ticker.upper())
    secs = list(db.scalars(q))
    total_px = total_dv = 0

    for sec in secs:
        started = datetime.utcnow()
        try:
            time.sleep(THROTTLE_SECONDS)
            o = yf.Ticker(sec.yahoo_symbol)
            # Securities the source has repeatedly not carried get one quick
            # look rather than the full retry ladder.
            tries = 1 if (sec.fetch_failures or 0) >= DEAD_AFTER_FAILURES else None
            hist, err = _retry(lambda: o.history(period=period, auto_adjust=False),
                               "history", attempts=tries)
            if hist is None:
                # Keep whatever we already had; a failed refresh must not erase data.
                sec.fetch_failures = (sec.fetch_failures or 0) + 1
                db.commit()
                _log(db, "sync_prices", sec.ticker, "failed", 0, err, started)
                if verbose:
                    print("  %-8s no new data (%s)" % (sec.ticker, err))
                continue
            sec.fetch_failures = 0
            sec.last_fetch_ok = date.today()

            existing = set(d for (d,) in db.execute(
                select(Price.d).where(Price.security_id == sec.id)))

            rows = []
            for idx, r in hist.iterrows():
                d = _to_date(idx)
                if d is None or d in existing:
                    continue
                close = _px(r.get("Close"))
                if close is None:
                    continue          # never invent a price
                adj = _px(r.get("Adj Close"))
                rows.append(Price(
                    security_id=sec.id, d=d,
                    open=_px(r.get("Open")), high=_px(r.get("High")),
                    low=_px(r.get("Low")),
                    close=close, adj_close=adj if adj is not None else close,
                    volume=_f(r.get("Volume")),
                    currency=sec.currency, source=SOURCE))
            if rows:
                db.add_all(rows)
                db.commit()
            total_px += len(rows)

            # dividends
            dv_rows = []
            try:
                divs = o.dividends
                have = set(d for (d,) in db.execute(
                    select(Dividend.ex_date).where(Dividend.security_id == sec.id)))
                for idx, val in divs.items():
                    d = _to_date(idx)
                    amt = _f(val)
                    if d is None or amt is None or amt <= 0 or d in have:
                        continue
                    dv_rows.append(Dividend(security_id=sec.id, ex_date=d,
                                            amount_per_share=round(amt, 6),
                                            currency=sec.currency, source=SOURCE))
                if dv_rows:
                    db.add_all(dv_rows)
                    db.commit()
                total_dv += len(dv_rows)
            except Exception:
                db.rollback()

            _log(db, "sync_prices", sec.ticker, "ok", len(rows),
                 "%d prices, %d dividends" % (len(rows), len(dv_rows)), started)
            if verbose:
                print("  %-8s +%5d prices  +%3d divs" % (sec.ticker, len(rows), len(dv_rows)))
        except Exception as e:
            db.rollback()
            _log(db, "sync_prices", sec.ticker, "failed", 0, str(e), started)
            if verbose:
                print("  %-8s FAILED %s" % (sec.ticker, type(e).__name__))

    db.close()
    return {"prices": total_px, "dividends": total_dv}


# --------------------------------------------------------------------------
# 3. Financial statements
# --------------------------------------------------------------------------
def sync_fundamentals(ticker=None, verbose: bool = True) -> dict:
    db = SessionLocal()
    q = select(Security).where(Security.is_active == True,          # noqa: E712
                               Security.asset_type == "equity")
    if ticker:
        q = q.where(Security.ticker == ticker.upper())
    secs = list(db.scalars(q))
    written = 0

    for sec in secs:
        started = datetime.utcnow()
        n = 0
        try:
            time.sleep(THROTTLE_SECONDS)
            o = yf.Ticker(sec.yahoo_symbol)
            sets = [
                ("income",   "annual",    o.income_stmt),
                ("balance",  "annual",    o.balance_sheet),
                ("cashflow", "annual",    o.cashflow),
                ("income",   "quarterly", o.quarterly_income_stmt),
                ("balance",  "quarterly", o.quarterly_balance_sheet),
                ("cashflow", "quarterly", o.quarterly_cashflow),
            ]
            for stmt, freq, df in sets:
                if df is None or getattr(df, "empty", True):
                    continue
                # Replace this statement/frequency wholesale for the periods covered:
                # restatements are real, so the newest pull is authoritative.
                periods = [p for p in (_to_date(c) for c in df.columns) if p]
                if periods:
                    db.execute(delete(FinancialFact).where(
                        FinancialFact.security_id == sec.id,
                        FinancialFact.statement == stmt,
                        FinancialFact.frequency == freq,
                        FinancialFact.period_end.in_(periods)))
                facts = []
                for col in df.columns:
                    pe = _to_date(col)
                    if pe is None:
                        continue
                    for item in df.index:
                        v = _f(df.loc[item, col])
                        if v is None:
                            continue   # missing stays missing
                        facts.append(FinancialFact(
                            security_id=sec.id, statement=stmt, frequency=freq,
                            period_end=pe, item=str(item), value=v,
                            currency=sec.currency, source=SOURCE))
                if facts:
                    db.add_all(facts)
                    n += len(facts)
                db.commit()
            written += n
            _log(db, "sync_fundamentals", sec.ticker, "ok" if n else "partial", n, None, started)
            if verbose:
                print("  %-8s +%5d statement facts" % (sec.ticker, n))
        except Exception as e:
            db.rollback()
            _log(db, "sync_fundamentals", sec.ticker, "failed", 0, str(e), started)
            if verbose:
                print("  %-8s FAILED %s" % (sec.ticker, type(e).__name__))

    db.close()
    return {"facts": written}


# --------------------------------------------------------------------------
QUOTE_SOURCE = "yahoo-isin-quote"


def _isin_symbol(sec) -> str | None:
    """The Yahoo symbol that carries a quote for a company with no history."""
    if not sec.isin:
        return None
    return sec.isin if sec.isin.endswith(".CA") else sec.isin + ".CA"


def resolve_isins(verbose: bool = True) -> dict:
    """
    Find Yahoo's ISIN-form symbol for companies we have no price for.

    Yahoo carries most of the EGX twice: under the short ticker ("COMI.CA"),
    which has full history, and under an ISIN-form symbol
    ("EGS3C251C013-EGP.CA"), which does not. For roughly a fifth of the
    exchange -- including large names such as Ezz Steel and Telecom Egypt --
    only the ISIN form exists. Those companies were showing as "No data"
    despite a real, current price being available for free.

    This looks the missing ones up by company name and stores the ISIN so
    `sync_quotes` can fetch that price.
    """
    from curl_cffi import requests as cr

    db = SessionLocal()
    started = datetime.utcnow()
    s = cr.Session(impersonate="chrome")
    url = "https://query2.finance.yahoo.com/v1/finance/search"

    targets = [sec for sec in db.scalars(select(Security).where(
        Security.asset_type == "equity",
        Security.listing_status == "listed",
        Security.isin.is_(None)))
        if not db.scalar(select(func.count(Price.id))
                         .where(Price.security_id == sec.id))]

    found = 0
    for sec in targets:
        try:
            time.sleep(1.2)
            r = s.get(url, params={"q": sec.name_en, "quotesCount": 8,
                                   "newsCount": 0}, timeout=25)
            for q in r.json().get("quotes", []):
                sym = q.get("symbol", "")
                # Only an Egyptian ISIN-form symbol will do: a short ticker we
                # already tried, and a foreign listing would be a different
                # security in a different currency.
                if sym.endswith(".CA") and sym.upper().startswith("EGS"):
                    sec.isin = sym[:-3]
                    db.commit()
                    found += 1
                    if verbose:
                        print("  %-8s -> %s (%s)"
                              % (sec.ticker, sym, q.get("shortname") or ""))
                    break
        except Exception as e:
            if verbose:
                print("  %-8s lookup failed: %s" % (sec.ticker, e))

    if verbose:
        print("  ISIN resolution: %d of %d companies matched"
              % (found, len(targets)))
    _log(db, "resolve_isins", None, "ok", found,
         "found=%d of %d" % (found, len(targets)), started)
    db.close()
    return {"searched": len(targets), "found": found}


def sync_quotes(verbose: bool = True) -> dict:
    """
    Fetch a current price for companies that have no price history.

    This is deliberately narrow. The ISIN-form symbol returns exactly one bar,
    so it can give a company a price, a market capitalisation and a day change
    -- but never a return, a volatility or a drawdown, because there is no
    series to compute those from. Anything needing history keeps refusing, as
    it should.

    The row is written with its own source label so it is always distinguishable
    from real history, and companies that already have history are skipped
    entirely: a single quote must never be mixed into a proper series.
    """
    db = SessionLocal()
    started = datetime.utcnow()

    targets = []
    for sec in db.scalars(select(Security).where(
            Security.asset_type == "equity",
            Security.listing_status == "listed",
            Security.isin.isnot(None))):
        n = db.scalar(select(func.count(Price.id))
                      .where(Price.security_id == sec.id,
                             Price.source != QUOTE_SOURCE))
        if not n:
            targets.append(sec)

    stored = 0
    for sec in targets:
        sym = _isin_symbol(sec)
        try:
            time.sleep(THROTTLE_SECONDS)
            hist, err = _retry(
                lambda: yf.Ticker(sym).history(period="5d", auto_adjust=False),
                "quote", attempts=1)
            if hist is None or not len(hist):
                if verbose:
                    print("  %-8s no quote (%s)" % (sec.ticker, sym))
                continue
            for ts, r in hist.iterrows():
                d = ts.date()
                close = _px(r.get("Close"))
                if close is None or close <= 0:
                    continue
                existing = db.scalar(select(Price).where(
                    Price.security_id == sec.id, Price.d == d))
                if existing:
                    continue
                db.add(Price(security_id=sec.id, d=d,
                             open=_px(r.get("Open")), high=_px(r.get("High")),
                             low=_px(r.get("Low")), close=close,
                             adj_close=_px(r.get("Adj Close")) or close,
                             volume=int(r.get("Volume") or 0),
                             currency=sec.currency or "EGP",
                             source=QUOTE_SOURCE))
                stored += 1
            sec.data_note = (
                "Current price only. The free source publishes a live quote "
                "for this company but no price history, so returns, "
                "volatility and charts are not available for it.")
            db.commit()
            if verbose:
                print("  %-8s quote stored (%s)" % (sec.ticker, sym))
        except Exception as e:
            db.rollback()
            if verbose:
                print("  %-8s quote failed: %s" % (sec.ticker, e))

    if verbose:
        print("  quotes: %d rows for %d companies without history"
              % (stored, len(targets)))
    _log(db, "sync_quotes", None, "ok", stored,
         "companies=%d" % len(targets), started)
    db.close()
    return {"companies": len(targets), "rows": stored}
