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
import re
import shutil
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, func

from app.db import SessionLocal
from app.models import (Security, Price, Dividend, FinancialFact,
                        SecurityMetrics, IngestRun, FundProfile)
from app.engine import liquidity as liquidity_mod
from app.engine import inflation as inflation_mod
from app.engine import integrity as integrity_mod
from app.engine import valuation_bands as bands_mod
from app.engine import statements as statements_mod
from app.engine import stress as stress_mod
from app.engine import breadth as breadth_mod
from app.engine import peers as peers_mod
from app.engine import digest as digest_mod
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
    # Stamp every local asset with the build version.
    #
    # Without this a returning visitor runs yesterday's JavaScript against
    # today's data files for as long as their browser cache lasts -- which the
    # _headers file sets to an hour. That mismatch is exactly how a page ends
    # up asking for a field the old code does not know about, and it is silent.
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M")
    shell = open(os.path.join(WEB_SRC, "index.html"), encoding="utf-8").read()
    # Root-absolute, because a page now lives at /stock/COMI and a relative
    # "static/app.js" would resolve to /stock/COMI/static/app.js.
    shell = re.sub(r'((?:src|href)=")(static/[^"?]+)(")',
                   lambda m: "%s/%s?v=%s%s" % (m.group(1), m.group(2), stamp,
                                               m.group(3)),
                   shell)
    # Cloudflare Pages reads these from the root of the published folder.
    for extra in ("_headers",):
        src = os.path.join(WEB_SRC, extra)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(OUT, extra))

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
        # Needed by the markets list for both the thin-trading badge and the
        # "readily tradeable" filter, so it belongs in the universe file rather
        # than only in the per-company metrics.
        "liquidity_band": (m.liquidity_band if m else None),
        "real_ret_1y": (m.real_ret_1y if m else None),
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
            "adtv_90d": m.adtv_90d,
            "adtv_30d": m.adtv_30d,
            "days_traded_90d": m.days_traded_90d,
            "liquidity_band": m.liquidity_band,
            "ret_1w": m.ret_1w, "ret_1m": m.ret_1m, "ret_3m": m.ret_3m,
            "ret_6m": m.ret_6m, "ret_1y": m.ret_1y, "ret_3y": m.ret_3y,
            "ret_5y": m.ret_5y,
            "real_ret_1y": m.real_ret_1y, "real_ret_3y": m.real_ret_3y,
            "real_ret_5y": m.real_ret_5y,
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

    # Coverage on this exchange is very uneven, and the headline has to say so.
    # "269 companies" sets an expectation the data cannot meet for two thirds of
    # them; a visitor who searches a mid-cap and finds a row of dashes blames
    # the platform, not the free source it depends on.
    _eq = (Security.asset_type == "equity", Security.listing_status == "listed")
    equities_with_prices = db.scalar(
        select(func.count(func.distinct(Security.id)))
        .join(Price, Price.security_id == Security.id).where(*_eq))
    equities_with_statements = db.scalar(
        select(func.count(func.distinct(Security.id)))
        .join(FinancialFact, FinancialFact.security_id == Security.id).where(*_eq))
    equities_valued = db.scalar(
        select(func.count(Security.id))
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(*_eq, SecurityMetrics.fair_value_base.isnot(None)))
    equities_thin = db.scalar(
        select(func.count(Security.id))
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(*_eq, SecurityMetrics.liquidity_band.in_(("Thin", "Very thin"))))

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
        "equities_with_prices": equities_with_prices,
        "equities_with_statements": equities_with_statements,
        "equities_valued": equities_valued,
        "equities_thinly_traded": equities_thin,
        # Carried in status because the company page needs it and status is
        # already loaded on every page; repeating the wording in 371 company
        # files would be wasteful.
        "inflation": inflation_mod.describe(db),
        # How much fund NAV history we have accumulated ourselves. No free
        # source publishes it, so this grows one day at a time.
        "funds_nav_days": db.scalar(
            select(func.count(func.distinct(Price.d)))
            .where(Price.source == "egx-research-nav")),
        "funds_nav_first": (lambda d: d.isoformat() if d else None)(
            db.scalar(select(func.min(Price.d))
                      .where(Price.source == "egx-research-nav"))),
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

    # Fault detail, computed once for the companies that actually have a fault
    # rather than re-scanning every price series for all 371.
    #
    # Both scans read a company's whole history from the database, and together
    # they were taking about 70 seconds of a 110-second export -- to describe
    # breaks in 34 companies and bad prints in 8. The flags themselves are
    # already stored by the refresh job; only the detail needed rebuilding.
    breaks_by_sec: dict[int, list] = {}
    for _s in db.scalars(select(Security).where(
            Security.price_integrity == "discontinuous")):
        breaks_by_sec[_s.id] = [
            {"date": b["date"], "move_pct": b["move_pct"], "likely": b["likely"]}
            for b in integrity_mod.find_discontinuities(db, _s.id)]

    prints_by_sec: dict[int, list] = {}
    _suspect_ids = [r[0] for r in db.execute(
        select(Price.security_id).where(Price.suspect == True).distinct())]  # noqa: E712
    for _sid in _suspect_ids:
        prints_by_sec[_sid] = [
            {"date": b["date"], "price": b["price"], "reason": b["reason"]}
            for b in integrity_mod.find_bad_prints(db, _sid)]

    # ---- data quality ----------------------------------------------------
    #
    # Every known fault, counted from the database rather than written down.
    # Publishing your own faults is the strongest trust signal available to a
    # platform with no institution behind it, and almost nobody does it --
    # which is exactly why it works.
    _eq_listed = (Security.asset_type == "equity",
                  Security.listing_status == "listed")

    def _count(*where):
        return db.scalar(select(func.count(Security.id)).where(*where))

    flagged = db.scalars(select(Security).where(
        *_eq_listed, Security.price_integrity == "discontinuous")).all()
    suspect_bars = db.scalar(select(func.count(Price.id))
                             .where(Price.suspect == True))          # noqa: E712
    suspect_secs = db.scalar(select(func.count(func.distinct(Price.security_id)))
                             .where(Price.suspect == True))          # noqa: E712
    units = db.scalars(select(Security).join(
        SecurityMetrics, SecurityMetrics.security_id == Security.id).where(
        *_eq_listed, SecurityMetrics.units_suspect == True)).all()   # noqa: E712
    no_price = db.scalars(select(Security).where(
        *_eq_listed,
        ~Security.id.in_(select(Price.security_id).distinct()))).all()
    no_vol = _count(*_eq_listed,
                    Security.id.in_(
                        select(SecurityMetrics.security_id)
                        .where(SecurityMetrics.liquidity_band.is_(None),
                               SecurityMetrics.price.isnot(None))))

    from app.ingest.reference_universe import EXCLUDED as _EXCL

    # An independent witness on our prices, read from the last refresh rather
    # than fetched here. Making the network call inside the export pushed a
    # build to nearly two minutes, tied it to another site's uptime, and ran
    # the same request twice per pipeline.
    from app.ingest import crosscheck as _cc
    cross = _cc.load()

    sizes["quality"] = _w(os.path.join(DATA_OUT, "quality.json"), {
        "built_on": built.isoformat(),
        "universe": {
            "companies": confirmed,
            "retired": retired,
            "excluded_instruments": [
                {"ticker": t, "kind": v[0], "reason": v[1]}
                for t, v in sorted(_EXCL.items())],
        },
        "coverage": {
            "with_prices": equities_with_prices,
            "with_statements": equities_with_statements,
            "with_valuation": equities_valued,
            "with_liquidity": db.scalar(
                select(func.count(SecurityMetrics.id))
                .where(SecurityMetrics.liquidity_band.isnot(None))),
            "no_price_at_all": [
                {"ticker": s_.ticker, "name": s_.name_en} for s_ in no_price],
            "prices_but_no_volume": no_vol,
        },
        "faults": {
            "unadjusted_corporate_actions": [
                {"ticker": s_.ticker, "name": s_.name_en,
                 "safe_from": (s_.price_safe_from.isoformat()
                               if s_.price_safe_from else None),
                 "breaks": breaks_by_sec.get(s_.id, [])}
                for s_ in flagged],
            "bad_prints": {"bars": suspect_bars, "securities": suspect_secs},
            "currency_mismatches": [
                {"ticker": s_.ticker, "name": s_.name_en} for s_ in units],
        },
        "cross_check": cross,
        "sources": [
            {"name": "Yahoo Finance",
             "used_for": "Daily prices, dividends, annual financial statements",
             "limits": "About ten years of history. Statements for %d of %d "
                       "companies. Some corporate actions arrive unadjusted."
                       % (equities_with_statements, confirmed)},
            {"name": "stockanalysis.com", "used_for": "EGX ticker roster",
             "limits": "Disagrees with our second roster."},
            {"name": "african-markets.com", "used_for": "Second ticker roster",
             "limits": "Carries tickers renamed or delisted years ago."},
            {"name": "egxbot.com", "used_for": "Fund names and current NAV",
             "limits": "40 funds, and no NAV history at all."},
            {"name": "World Bank", "used_for": "Egyptian consumer prices",
             "limits": "Annual only; values between years are interpolated."},
        ],
    })

    # ---- market breadth --------------------------------------------------
    #
    # An index can rise while most shares fall, and on an exchange this
    # concentrated that happens often. Breadth answers the question the index
    # cannot: how many companies actually took part.
    sizes["breadth"] = _w(os.path.join(DATA_OUT, "breadth.json"), {
        "daily": breadth_mod.daily(db),
        "participation": breadth_mod.participation(db, 60),
    })

    # ---- the week --------------------------------------------------------
    #
    # A page for the reader who checks in occasionally rather than daily, and
    # an RSS feed so they can subscribe without handing over an email address
    # we have nowhere to store.
    week = digest_mod.build(db)
    sizes["digest"] = _w(os.path.join(DATA_OUT, "digest.json"), week)

    # ---- market reference ------------------------------------------------
    comp = composite_mod.build_composite(
        db, start=date.today() - timedelta(days=365 * 7 + 30))
    sizes["composite"] = _w(os.path.join(DATA_OUT, "composite.json"), comp)

    # ---- education -------------------------------------------------------
    sizes["education"] = _w(os.path.join(DATA_OUT, "education.json"), {
        "glossary": GLOSSARY, "lessons": LESSONS, "questionnaire": QUESTIONNAIRE,
        "profiles": PROFILES})

    # Static reference content the browser needs but that has no data behind it.
    from app.engine.screener import FILTERABLE, WITHHELD_FROM_SCREENER
    from app.engine.valuation import DEFAULTS as VAL_DEFAULTS, RATE_SOURCE_NOTE
    sizes["reference"] = _w(os.path.join(DATA_OUT, "reference.json"), {
        "screener_fields": [{"field": k, "label": v[1], "unit": v[2]}
                            for k, v in FILTERABLE.items()],
        "screener_withheld": [{"field": k, "reason": v}
                              for k, v in WITHHELD_FROM_SCREENER.items()],
        "inflation": inflation_mod.describe(db),
        # How much fund NAV history we have accumulated ourselves. No free
        # source publishes it, so this grows one day at a time.
        "funds_nav_days": db.scalar(
            select(func.count(func.distinct(Price.d)))
            .where(Price.source == "egx-research-nav")),
        "funds_nav_first": (lambda d: d.isoformat() if d else None)(
            db.scalar(select(func.min(Price.d))
                      .where(Price.source == "egx-research-nav"))),
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
    company_valuations: dict[str, dict | None] = {}
    medians = metrics_mod.sector_medians(db)
    market_medians = medians.get("__market__", {})
    # The published company pages must agree with the stored screener figures,
    # so they are valued with exactly the same calibration rather than each
    # being recomputed in isolation.
    from app.engine.valuation_batch import _market_median_upside
    _vrows = db.execute(
        select(Security, SecurityMetrics)
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(Security.asset_type == "equity")).all()
    _mu = _market_median_upside(db, _vrows, medians, market_medians)
    val_calibration = {"market_median_upside_pct": _mu} if _mu is not None else None
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
                    medians.get(s.sector or "", {}),
                    assumptions=val_calibration,
                    market_multiples=market_medians)
            except Exception:
                val = None
        # Kept so the pre-rendered page can quote the same range the app shows,
        # rather than recomputing it and risking a different answer.
        company_valuations[s.ticker] = val

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
            "performance_real": ({"1Y": m.real_ret_1y, "3Y": m.real_ret_3y,
                                  "5Y": m.real_ret_5y} if m else {}),
            "risk": {"volatility_pct": m.volatility_pct,
                     "max_drawdown_pct": m.max_drawdown_pct} if m else {},
            "liquidity": ({
                "adtv_90d": m.adtv_90d, "adtv_30d": m.adtv_30d,
                "days_traded_90d": m.days_traded_90d,
                "sessions_in_window": m.sessions_in_window,
                "band": m.liquidity_band,
                "band_note": liquidity_mod.band_for(m.adtv_90d)[1],
                "no_volume_note": (liquidity_mod.NO_VOLUME_NOTE
                                   if m.liquidity_band is None else None),
                "days_to_exit_100k": _round(
                    liquidity_mod.days_to_trade(100_000, m.adtv_90d), 1),
                "participation_pct": liquidity_mod.PARTICIPATION * 100,
            } if m else {}),
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
                # The actual dates, so a reader can see where the history breaks
                # rather than only being told that it does.
                "price_breaks": breaks_by_sec.get(s.id, []),
                "bad_prints": prints_by_sec.get(s.id, []),
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
            # The same statements expressed as a share of revenue (or of total
            # assets on the balance sheet), so the shape of the business is
            # comparable across years and across companies of any size.
            "statements_common_sized": statements_mod.common_sized(hist_a),
            # What actually happened to this share through Egypt's currency
            # devaluations. Measured, not modelled.
            "devaluation_stress": stress_mod.for_security(db, s.id),
            # How this company ranks against the companies most like it, and
            # the handful worth putting beside it.
            "peers": peers_mod.compare(db, s, m),
            "nearest_peers": peers_mod.nearest(db, s, m, 6),
            "valuation": val,
            # What the market has actually paid for this company over the years
            # we hold -- a measurement rather than a model, and the honest
            # counterweight to the fair-value engine.
            # Fair value at a range of required returns, so a reader who
            # disagrees with ours can read their own row.
            "valuation_sensitivity": (
                valuation.sensitivity(
                    db, s, last.close, hist_a, m.dividend_ttm,
                    (m.dividend_growth_pct / 100.0) if m.dividend_growth_pct else None,
                    medians.get(s.sector or "", {}), market_medians, _mu)
                if (val and val.get("available")) else {"available": False}),
            "valuation_history": bands_mod.bands_for(
                db, s, last.close if last else None),
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

    # ---- real pages, one per route --------------------------------------
    #
    # Until now every route was a hash fragment, which a search engine treats
    # as the same page. 269 company pages shared one URL, one title and one
    # description, so none of them could be found.
    from app.web import pages as P

    site_url = os.environ.get("EGX_SITE_URL", "https://egx-research.pages.dev")
    today = date.today().isoformat()
    urls: list[tuple[str, str, str]] = []
    n_pages = 0

    def write_page(path, title, description, body="", jsonld=None,
                   changefreq="weekly", index=True, alternates=None,
                   lang="en"):
        nonlocal n_pages
        out_dir = OUT if path == "/" else os.path.join(OUT, path.strip("/"))
        os.makedirs(out_dir, exist_ok=True)
        html_out = P.render_shell(shell, path=path, title=title,
                                  description=description, site_url=site_url,
                                  body=body, jsonld=jsonld,
                                  noindex=not index, alternates=alternates,
                                  lang=lang)
        with open(os.path.join(out_dir, "index.html"), "w",
                  encoding="utf-8") as f:
            f.write(html_out)
        if index:
            urls.append((path, today, changefreq))
        n_pages += 1

    for path, (title, desc, body) in P.STATIC_ROUTES.items():
        write_page(path, title, desc,
                   '<div class="prerender">%s</div>' % body,
                   changefreq="daily" if path in ("/", "/markets") else "weekly",
                   alternates=P.alternate_links(path, site_url, "en")
                   if path in P.AR_ROUTES else None)

    # Arabic landing pages. Real, indexable pages rather than a client-side
    # toggle, which a crawler never sees.
    for path, (title, desc, body) in P.AR_ROUTES.items():
        write_page("/ar" + ("" if path == "/" else path), title, desc,
                   '<div class="prerender">%s</div>' % body,
                   changefreq="weekly",
                   alternates=P.alternate_links(path, site_url, "ar"),
                   lang="ar")

    for s_, m_ in rows:
        if s_.listing_status != "listed" or s_.asset_type == "index":
            continue
        v_ = company_valuations.get(s_.ticker)
        t, d, b, j = P.company_page(s_, m_, v_, site_url)
        write_page("/stock/" + s_.ticker, t, d, b, j, changefreq="daily")

    by_sector: dict[str, list] = {}
    for s_, m_ in rows:
        if s_.listing_status == "listed" and s_.asset_type == "equity" and s_.sector:
            by_sector.setdefault(s_.sector, []).append(
                {"ticker": s_.ticker, "name": s_.name_en,
                 "price": m_.price if m_ else None})
    for sector, members in sorted(by_sector.items()):
        members.sort(key=lambda c: c["name"])
        t, d, b, j = P.sector_page(sector, members, site_url)
        write_page("/sector/" + P.sector_slug(sector), t, d, b, j)

    # A visitor who lands on a path we did not generate still gets the app,
    # which then renders whatever the route resolves to.
    nf = P.render_shell(shell, path="/", title=P.STATIC_ROUTES["/"][0],
                        description=P.DEFAULT_DESC, site_url=site_url,
                        noindex=True)
    with open(os.path.join(OUT, "404.html"), "w", encoding="utf-8") as f:
        f.write(nf)

    with open(os.path.join(OUT, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(digest_mod.rss(week, site_url, date.today().isoformat()))

    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(P.sitemap(urls, site_url))
    with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(P.robots(site_url))

    if verbose:
        print("  pages: %d generated, %d in the sitemap (%d sectors)"
              % (n_pages, len(urls), len(by_sector)))

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
