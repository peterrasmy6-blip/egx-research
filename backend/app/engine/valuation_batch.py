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

    counts = {"valued": 0, "no_statements": 0, "no_method": 0, "no_price": 0}
    classes: dict[str, int] = {}

    rows = db.execute(
        select(Security, SecurityMetrics)
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(Security.asset_type == "equity")).all()

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
            r = valuation.value_security(db, sec, last.close, hist, dps, dgr, peer)
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
