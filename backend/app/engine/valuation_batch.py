"""
Batch valuation: run the fair-value engine across the universe and store the
summary on each security's metric row.

Kept separate from `metrics.py` because it must run *after* metrics: relative
valuation needs sector median multiples, which are computed from the metrics
snapshot. Running it first would value every company against empty benchmarks.

Storing the result lets the screener filter on model upside without
recalculating dozens of models per request.
"""
from __future__ import annotations

from sqlalchemy import select

from ..models import Security, SecurityMetrics
from . import valuation, metrics as metrics_mod
from .analytics import latest_price
from .fundamentals import statement_history


def refresh_valuations(db, verbose: bool = True) -> dict:
    medians = metrics_mod.sector_medians(db)
    # Sectors with fewer than three priced members cannot form a benchmark of
    # their own; those companies fall back to the market-wide multiple.
    market = medians.get("__market__", {})

    rows = db.execute(
        select(Security, SecurityMetrics)
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(Security.asset_type == "equity")).all()

    counts = {"valued": 0, "no_statements": 0, "no_method": 0, "no_price": 0}
    classes: dict[str, int] = {}

    # Two passes. The first measures how far this model sits from market prices
    # across the whole exchange; the second uses that figure to strip the
    # common part out of each company's result.
    #
    # It is not a fudge factor. Every model that discounts cash flow at a rate
    # built from ~20% Egyptian government yields puts the typical company below
    # its market price, because shares are a claim on earnings that inflate
    # while a treasury bill's coupon does not. Reporting that shared gap as a
    # verdict on each company in turn would have the platform declaring most of
    # the exchange overvalued -- a claim it cannot support.
    calibration = None
    market_upside = _market_median_upside(db, rows, medians, market)
    if market_upside is not None:
        calibration = {"market_median_upside_pct": market_upside}
        if verbose:
            print("  model calibration: the typical company values %.1f%% "
                  "against its market price" % market_upside)


    for sec, m in rows:
        last = latest_price(db, sec.id)
        if last is None:
            counts["no_price"] += 1
            continue

        hist = statement_history(db, sec.id, "annual")
        if not hist:
            counts["no_statements"] += 1
            continue

        # A price and statements in different currencies cannot be valued
        # together. Without this guard the engine reported FAITA -- the dollar
        # share class of an Egyptian bank -- as undervalued by 2,934%.
        if m.units_suspect:
            counts["units_mismatch"] = counts.get("units_mismatch", 0) + 1
            m.fair_value_base = m.fair_value_bear = m.fair_value_bull = None
            m.upside_pct = None
            m.valuation_class = "Insufficient reliable data"
            m.valuation_confidence = None
            continue

        dps = m.dividend_ttm
        dgr = (m.dividend_growth_pct / 100.0) if m.dividend_growth_pct else None
        peer = medians.get(sec.sector or "", {})

        try:
            r = valuation.value_security(db, sec, last.close, hist, dps, dgr,
                                         peer, assumptions=calibration,
                                         market_multiples=market)
        except Exception:
            counts["no_method"] += 1
            continue

        if not r.get("available"):
            counts["no_method"] += 1
            m.fair_value_base = m.fair_value_bear = m.fair_value_bull = None
            m.upside_pct = None
            m.valuation_class = None
            m.valuation_confidence = None
            continue

        m.fair_value_base = r["base"]
        m.fair_value_bear = r["bear"]
        m.fair_value_bull = r["bull"]
        m.valuation_class = r["classification"]
        m.valuation_confidence = r["confidence"]

        # Only store an upside figure we are prepared to stand behind. Where
        # the methods disagreed too much to classify the company, the number is
        # withheld so the screener cannot rank an unreliable estimate at the
        # top of a "most undervalued" list. The company's own page still shows
        # the full range and says why confidence is low.
        m.upside_pct = (None if r["classification"] == "Insufficient reliable data"
                        else r["upside_pct"])
        counts["valued"] += 1
        classes[r["classification"]] = classes.get(r["classification"], 0) + 1

    db.commit()
    if verbose:
        print("  valuations:", counts)
        for k, v in sorted(classes.items(), key=lambda x: -x[1]):
            print("    %-32s %d" % (k, v))
    return {"counts": counts, "classifications": classes}


def _market_median_upside(db, rows, medians, market) -> float | None:
    """
    The median gap between modelled value and market price across the exchange.

    Run before any company is classified, using exactly the same engine, so the
    figure describes the model rather than a subset of it.
    """
    ups = []
    for sec, m in rows:
        if sec.listing_status != "listed" or m.units_suspect:
            continue
        last = latest_price(db, sec.id)
        if last is None or not last.close:
            continue
        hist = statement_history(db, sec.id, "annual")
        if not hist:
            continue
        try:
            r = valuation.value_security(
                db, sec, last.close, hist, m.dividend_ttm,
                (m.dividend_growth_pct / 100.0) if m.dividend_growth_pct else None,
                medians.get(sec.sector or "", {}), market_multiples=market)
        except Exception:
            continue
        if r.get("available") and r.get("upside_pct") is not None:
            ups.append(r["upside_pct"])
    if len(ups) < 20:
        return None            # too few to calibrate against honestly
    ups.sort()
    n = len(ups)
    return ups[n // 2] if n % 2 else (ups[n // 2 - 1] + ups[n // 2]) / 2
