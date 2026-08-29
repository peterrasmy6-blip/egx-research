"""
Static site export.

Turns the database into a folder of plain JSON files that any static host can
serve for free, forever, with no server and no cold starts.

The trade-off this creates: with no backend, every calculation has to run in
the visitor's browser. Pre-computed results (metrics, valuations, statements)
are baked into these files. Interactive tools (what-if, backtest, Monte Carlo)
are recomputed client-side from the price series exported here, by JavaScript
ported from the Python engine and checked against it.

Layout produced:

    site/
      index.html, static/...          the app
      data/status.json                platform totals and freshness
      data/securities.json            the universe list
      data/metrics.json               every metric, for screener and compare
      data/sectors.json
      data/composite.json             market reference series
      data/education.json             glossary, lessons, questionnaire
      data/company/<TICKER>.json      detail + prices + statements + dividends
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, func

from app.db import SessionLocal
from app.models import (Security, Price, Dividend, FinancialFact,
                        SecurityMetrics, IngestRun, FundProfile)
from app.engine import (analytics, fundamentals, valuation, metrics as metrics_mod,
                        composite as composite_mod)
from app.api.education import GLOSSARY, LESSONS, QUESTIONNAIRE, PROFILES
from app.api.main import DISCLAIMER, _quality_label

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_SRC = os.path.join(ROOT, "backend", "app", "web")
OUT = os.path.join(ROOT, "site")
DATA_OUT = os.path.join(OUT, "data")
COMPANY_OUT = os.path.join(DATA_OUT, "company")


def _w(path: str, obj) -> int:
    """Write compact JSON and return the byte size."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(obj, separators=(",", ":"), default=str)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return len(text.encode("utf-8"))


def _round(x, n=4):
    return None if x is None else round(x, n)


def _clean_output() -> None:
    """
    Empty the output folder without requiring the directories themselves to be
    removable.

    On Windows a directory can be briefly locked by an indexer or a file
    watcher, which makes `rmtree` fail and leave a half-deleted tree behind.
    Deleting only the files, and tolerating the odd locked one, is enough: every
    file is rewritten below, and a stale leftover would be overwritten anyway.
    """
    if not os.path.isdir(OUT):
        return
    for root, _dirs, files in os.walk(OUT):
        for name in files:
            try:
                os.remove(os.path.join(root, name))
            except OSError:
                pass


# --------------------------------------------------------------------------
def export_all(verbose: bool = True) -> dict:
    db = SessionLocal()
    _clean_output()
    os.makedirs(COMPANY_OUT, exist_ok=True)

    sizes = {}

    # ---- app shell -------------------------------------------------------
    shutil.copytree(os.path.join(WEB_SRC, "static"), os.path.join(OUT, "static"),
                    dirs_exist_ok=True)
    shutil.copy(os.path.join(WEB_SRC, "index.html"), os.path.join(OUT, "index.html"))

    rows = db.execute(
        select(Security, SecurityMetrics)
        .outerjoin(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .order_by(Security.ticker)).all()

    # Fund profiles, keyed by security id, so funds can carry their NAV and
    # risk band into the universe list alongside shares.
    funds_by_sec = {f.security_id: f for f in db.scalars(select(FundProfile)).all()}

    listed = [(s, m) for s, m in rows if s.listing_status == "listed"]

    # ---- universe --------------------------------------------------------
    sizes["securities"] = _w(os.path.join(DATA_OUT, "securities.json"), [{
        "ticker": s.ticker, "name": s.name_en, "sector": s.sector,
        "asset_type": s.asset_type, "listing_status": s.listing_status,
        "data_quality": s.data_quality,
        "listing_confirmed": bool(s.listing_confirmed) or s.asset_type != "equity",
        "sources_listing": s.sources_listing or 0,
        "market_cap": _round(m.market_cap, 0) if m else None,
        "price": (_round(funds_by_sec[s.id].nav, 4)
                  if s.asset_type == "fund" and s.id in funds_by_sec
                  else (_round(m.price, 4) if m else None)),
        "day_change_pct": m.day_change_pct if m else None,
        "ret_1y": (funds_by_sec[s.id].return_1y_pct
                   if s.asset_type == "fund" and s.id in funds_by_sec
                   else (m.ret_1y if m else None)),
        "fund": ({"category": funds_by_sec[s.id].category,
                  "fund_type": funds_by_sec[s.id].fund_type,
                  "risk": funds_by_sec[s.id].risk,
                  "ytd_pct": funds_by_sec[s.id].ytd_pct,
                  "nav": _round(funds_by_sec[s.id].nav, 4)}
                 if s.asset_type == "fund" and s.id in funds_by_sec else None),
        "currency": s.currency,
    } for s, m in listed])

    # ---- metrics (screener + comparison run entirely off this) -----------
    sizes["metrics"] = _w(os.path.join(DATA_OUT, "metrics.json"), {
        s.ticker: {
            "name": s.name_en, "sector": s.sector,
            "data_quality": s.data_quality,
            "price": _round(m.price, 4), "day_change_pct": m.day_change_pct,
            "market_cap": _round(m.market_cap, 0),
            "pe": m.pe, "pb": m.pb, "ps": m.ps, "ev_ebitda": m.ev_ebitda,
            "eps": _round(m.eps, 4),
            "dividend_yield_pct": m.dividend_yield_pct,
            "roe_pct": m.roe_pct, "roa_pct": m.roa_pct, "roic_pct": m.roic_pct,
            "net_margin_pct": m.net_margin_pct,
            "operating_margin_pct": m.operating_margin_pct,
            "revenue_growth_pct": m.revenue_growth_pct,
            "revenue_cagr_3y_pct": m.revenue_cagr_3y_pct,
            "earnings_growth_pct": m.earnings_growth_pct,
            "debt_to_equity": m.debt_to_equity,
            "volatility_pct": m.volatility_pct,
            "max_drawdown_pct": m.max_drawdown_pct,
            "ret_1w": m.ret_1w, "ret_1m": m.ret_1m, "ret_3m": m.ret_3m,
            "ret_6m": m.ret_6m, "ret_1y": m.ret_1y, "ret_3y": m.ret_3y,
            "ret_5y": m.ret_5y,
            "upside_pct": m.upside_pct,
            "valuation_class": m.valuation_class,
            "valuation_confidence": m.valuation_confidence,
            "units_suspect": bool(m.units_suspect),
            # Needed by the browser-side forecast model: how much evidence
            # stands behind a holding's own figures, and whether it is
            # loss-making (which disqualifies the growth block).
            "statement_periods": m.statement_periods,
            "net_income": _round(m.net_income, 0),
            "as_of": m.as_of.isoformat() if m.as_of else None,
        } for s, m in listed if m is not None})

    # ---- sectors ---------------------------------------------------------
    sec_counts = db.execute(
        select(Security.sector, func.count(Security.id))
        .where(Security.listing_status == "listed", Security.sector.isnot(None))
        .group_by(Security.sector).order_by(func.count(Security.id).desc())).all()
    sizes["sectors"] = _w(os.path.join(DATA_OUT, "sectors.json"),
                          [{"sector": s, "count": n} for s, n in sec_counts])

    # ---- status ----------------------------------------------------------
    # The last date the market genuinely traded -- not simply the newest row.
    # The source emits zero-volume bars on public holidays, and reporting one
    # as "latest market date" would tell visitors the exchange traded when it
    # was shut.
    from app.engine.trading_days import latest_session, purge_phantom_dates
    purge_phantom_dates(db, verbose=False)
    newest = latest_session(db) or db.scalar(select(func.max(Price.d)))
    quality = dict(db.execute(select(Security.data_quality, func.count(Security.id))
                              .group_by(Security.data_quality)).all())
    built = date.today()
    from app.ingest.reference_universe import KEEP_EXTRA, summary as ref_summary
    confirmed = db.scalar(select(func.count(Security.id)).where(
        Security.asset_type == "equity", Security.listing_status == "listed"))
    retired = db.scalar(select(func.count(Security.id)).where(
        Security.asset_type == "equity", Security.listing_status != "listed"))
    ref = ref_summary()
    n_funds = db.scalar(select(func.count(Security.id)).where(
        Security.asset_type == "fund"))

    sizes["status"] = _w(os.path.join(DATA_OUT, "status.json"), {
        "securities_listed": len(listed),
        # Every listed row is now an ordinary share of a company that either
        # appears on a broker's live instrument list or carries real recent
        # price history. Rights issues, ETFs, certificates, second share
        # classes and long-dead tickers are retired rather than counted.
        "companies_confirmed": confirmed,
        "companies_unconfirmed": 0,
        "companies_retired": retired,
        "companies_off_reference": len(KEEP_EXTRA),
        "universe_reference": ref,
        "funds": n_funds,
        "securities_with_prices": db.scalar(
            select(func.count(func.distinct(Price.security_id)))),
        "securities_with_statements": db.scalar(
            select(func.count(func.distinct(FinancialFact.security_id)))),
        "price_rows": db.scalar(select(func.count(Price.id))),
        "dividend_rows": db.scalar(select(func.count(Dividend.id))),
        "statement_facts": db.scalar(select(func.count(FinancialFact.id))),
        "latest_market_date": newest.isoformat() if newest else None,
        "data_quality_breakdown": quality,
        "built_on": built.isoformat(),
        "sources": ["Yahoo Finance (prices, dividends, financial statements)",
                    "stockanalysis.com (EGX listed-company index)"],
        "disclaimer": DISCLAIMER,
        # A static build is a snapshot. The app compares this against the
        # visitor's clock and warns when the snapshot has aged.
        "is_static_build": True,
    })

    # ---- market reference ------------------------------------------------
    comp = composite_mod.build_composite(
        db, start=date.today() - timedelta(days=365 * 7 + 30))
    sizes["composite"] = _w(os.path.join(DATA_OUT, "composite.json"), comp)

    # ---- education -------------------------------------------------------
    sizes["education"] = _w(os.path.join(DATA_OUT, "education.json"), {
        "glossary": GLOSSARY, "lessons": LESSONS, "questionnaire": QUESTIONNAIRE,
        "profiles": PROFILES})

    # Static reference content the browser needs but that has no data behind it.
    from app.engine.screener import FILTERABLE
    from app.engine.valuation import DEFAULTS as VAL_DEFAULTS, RATE_SOURCE_NOTE
    sizes["reference"] = _w(os.path.join(DATA_OUT, "reference.json"), {
        "screener_fields": [{"field": k, "label": v[1], "unit": v[2]}
                            for k, v in FILTERABLE.items()],
        "valuation_defaults": VAL_DEFAULTS,
        "sector_medians": metrics_mod.sector_medians(db),
        "rate_note": RATE_SOURCE_NOTE,
        "indices_note": {
            "official_indices_available": False,
            "explanation": (
                "The Egyptian Exchange publishes EGX30, EGX70 and EGX100, but "
                "their historical values are not available from any free, "
                "machine-readable source we could find. Yahoo Finance returns "
                "the current EGX30 level but refuses historical ranges for it. "
                "The EGX website publishes index pages without a public data "
                "feed, and other providers either charge for the data or "
                "prohibit automated access in their terms."),
            "what_we_did_instead": (
                "We build our own equal-weighted composite from the prices we "
                "hold, and label it clearly as ours. We do not reconstruct a "
                "series and call it the EGX30 - without the official historical "
                "constituents and weights, that would be a fabricated series "
                "wearing an official name."),
        },
    })

    # ---- per-company -----------------------------------------------------
    medians = metrics_mod.sector_medians(db)
    total_company_bytes = 0
    exported = 0

    for s, m in rows:
        prices = analytics.price_series(db, s.id)
        divs = db.scalars(select(Dividend).where(Dividend.security_id == s.id)
                          .order_by(Dividend.ex_date)).all()
        hist_a = fundamentals.statement_history(db, s.id, "annual")
        hist_q = fundamentals.statement_history(db, s.id, "quarterly")

        val = None
        if prices and hist_a and m and not m.units_suspect:
            try:
                val = valuation.value_security(
                    db, s, prices[-1].close, hist_a,
                    m.dividend_ttm,
                    (m.dividend_growth_pct / 100.0) if m.dividend_growth_pct else None,
                    medians.get(s.sector or "", {}))
            except Exception:
                val = None

        last = prices[-1] if prices else None
        fund_sum = fundamentals.summary(db, s.id)

        payload = {
            "ticker": s.ticker, "name": s.name_en, "name_ar": s.name_ar,
            "isin": s.isin, "sector": s.sector, "industry": s.industry,
            "asset_type": s.asset_type, "listing_status": s.listing_status,
            "currency": s.currency,
            "price": _round(m.price if m else (last.close if last else None), 4),
            "price_date": last.d.isoformat() if last else None,
            "day_change_pct": m.day_change_pct if m else None,
            "market_cap": _round(m.market_cap, 0) if m else None,
            "shares_outstanding": _round(m.shares, 0) if m else None,
            "high_52w": _round(m.high_52w, 4) if m else None,
            "low_52w": _round(m.low_52w, 4) if m else None,
            "performance": {
                "1W": m.ret_1w, "1M": m.ret_1m, "3M": m.ret_3m, "6M": m.ret_6m,
                "1Y": m.ret_1y, "3Y": m.ret_3y, "5Y": m.ret_5y,
            } if m else {},
            "risk": {"volatility_pct": m.volatility_pct,
                     "max_drawdown_pct": m.max_drawdown_pct} if m else {},
            "valuation_ratios": {
                "pe": m.pe, "pb": m.pb, "ps": m.ps, "ev_ebitda": m.ev_ebitda,
                "eps": _round(m.eps, 4),
                "book_value_per_share": _round(m.book_value_per_share, 4),
                "dividend_yield_pct": m.dividend_yield_pct,
                "dividend_ttm": _round(m.dividend_ttm, 4),
            } if m else {},
            "quality": {
                "roe_pct": m.roe_pct, "roa_pct": m.roa_pct, "roic_pct": m.roic_pct,
                "net_margin_pct": m.net_margin_pct,
                "operating_margin_pct": m.operating_margin_pct,
                "debt_to_equity": m.debt_to_equity,
                "revenue_growth_pct": m.revenue_growth_pct,
                "revenue_cagr_3y_pct": m.revenue_cagr_3y_pct,
                "earnings_growth_pct": m.earnings_growth_pct,
            } if m else {},
            "data_quality": {
                "status": s.data_quality, **_quality_label(s.data_quality),
                "note": s.data_note,
                "fundamentals_available": fund_sum.get("available", False),
                "fundamentals_coverage_pct": fund_sum.get("coverage_pct"),
                "latest_statement": fund_sum.get("latest_period"),
                "statement_periods": fund_sum.get("periods_available"),
                "missing": fund_sum.get("missing_concepts", []),
                "price_history_from": prices[0].d.isoformat() if prices else None,
                "price_history_days": len(prices),
                "source": s.source, "source_url": s.source_url,
                "price_integrity": s.price_integrity,
                "price_safe_from": (s.price_safe_from.isoformat()
                                    if s.price_safe_from else None),
                "units_suspect": bool(m.units_suspect) if m else False,
            },
            # Compact arrays rather than objects: this is the bulk of the file,
            # and the browser needs both raw close (for share counts) and
            # adjusted close (for total return).
            "prices": {
                "d": [p.d.isoformat() for p in prices],
                "c": [round(p.close, 4) for p in prices],
                "a": [round(p.adj_close, 4) for p in prices],
            },
            "dividends": [{"ex_date": d.ex_date.isoformat(),
                           "amount": round(d.amount_per_share, 6)} for d in divs],
            "fundamentals": {"annual": hist_a, "quarterly": hist_q},
            "valuation": val,
            "fund": ({"category": funds_by_sec[s.id].category,
                      "fund_type": funds_by_sec[s.id].fund_type,
                      "risk": funds_by_sec[s.id].risk,
                      "nav": _round(funds_by_sec[s.id].nav, 4),
                      "ytd_pct": funds_by_sec[s.id].ytd_pct,
                      "return_1y_pct": funds_by_sec[s.id].return_1y_pct,
                      "since_inception_pct": funds_by_sec[s.id].since_inception_pct,
                      "has_nav_history": False,
                      "source_url": funds_by_sec[s.id].source_url}
                     if s.asset_type == "fund" and s.id in funds_by_sec else None),
            "disclaimer": DISCLAIMER,
        }
        n = _w(os.path.join(COMPANY_OUT, "%s.json" % s.ticker), payload)
        total_company_bytes += n
        exported += 1
        if verbose and exported % 50 == 0:
            print("  companies exported: %d" % exported)

    db.close()

    total = sum(sizes.values()) + total_company_bytes
    if verbose:
        print("\n  shared files:")
        for k, v in sorted(sizes.items(), key=lambda x: -x[1]):
            print("    %-14s %8.1f KB" % (k, v / 1024))
        print("    %-14s %8.1f KB across %d files"
              % ("company/*", total_company_bytes / 1024, exported))
        print("  TOTAL %.1f MB" % (total / 1e6))

    return {"companies": exported, "total_bytes": total, "sizes": sizes}


if __name__ == "__main__":
    r = export_all()
    print("\nwrote", OUT)
