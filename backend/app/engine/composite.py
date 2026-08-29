"""
A platform-built EGX market benchmark.

Why this exists
---------------
Users need to answer "did my shares beat the market?", which requires a market
series. The official EGX30 history is not obtainable from any free source
(Yahoo serves only the current level; stooq and the EGX site do not provide it
in machine-readable form). See DATA_SOURCES.md.

Rather than leave users with no benchmark at all, this module builds one from
prices the platform already holds -- and labels it honestly as **our own
composite, not the official EGX30**.

The biases are real and are reported with every result
------------------------------------------------------
1. **Survivorship.** The composite contains companies listed *today*. Companies
   that collapsed and were delisted are absent, so historical returns are
   flattered. This is the single largest distortion and cannot be removed
   without a historical membership list we do not have.
2. **Equal weighting.** Each company counts the same, so small illiquid
   companies carry the same weight as CIB. The official EGX30 is weighted by
   free-float market value, so the two will not match.
3. **Entry bias.** A company only joins the composite once its price history
   begins, which is not the same as its listing date.

Because of these, the composite is presented as "a broad market reference built
from our own data", never as the EGX30, and never as an official figure.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from ..models import Security, Price
from .analytics import price_series, daily_returns, annualised_volatility, max_drawdown

# Only companies with enough history and no unadjusted corporate actions.
MIN_HISTORY_DAYS = 200
MIN_MEMBERS = 15


def build_composite(db, start: date | None = None, end: date | None = None,
                    top_n: int | None = 50) -> dict:
    """
    Equal-weighted daily total-return composite of EGX companies.

    Built from daily returns rather than price levels, so a company joining or
    leaving on a given day does not create an artificial step in the series.
    `top_n` restricts membership to the largest companies by current market
    value, which makes the composite less dominated by micro-caps.
    """
    q = (select(Security)
         .where(Security.listing_status == "listed",
                Security.asset_type == "equity",
                Security.price_integrity == "clean"))
    members = list(db.scalars(q))

    # Rank by market value where known; unknown goes last.
    members.sort(key=lambda s: -(s.market_cap or 0))
    if top_n:
        members = members[:top_n]

    series_by_sec = {}
    for sec in members:
        rows = price_series(db, sec.id, start, end)
        if len(rows) < MIN_HISTORY_DAYS:
            continue
        series_by_sec[sec.ticker] = {r.d: r.adj_close for r in rows}

    if len(series_by_sec) < MIN_MEMBERS:
        return {"available": False,
                "reason": "Not enough companies with continuous price history "
                          "to build a market reference."}

    all_days = sorted({d for m in series_by_sec.values() for d in m})
    if len(all_days) < 30:
        return {"available": False, "reason": "Not enough trading days."}

    level = 1000.0
    points = [{"d": all_days[0].isoformat(), "v": round(level, 3),
               "members": 0}]
    prev = {t: m.get(all_days[0]) for t, m in series_by_sec.items()}

    for d in all_days[1:]:
        rets = []
        for t, m in series_by_sec.items():
            cur = m.get(d)
            p = prev.get(t)
            if cur is not None and p is not None and p > 0:
                rets.append(cur / p - 1.0)
            if cur is not None:
                prev[t] = cur
        if rets:
            level *= (1.0 + sum(rets) / len(rets))
        points.append({"d": d.isoformat(), "v": round(level, 3),
                       "members": len(rets)})

    values = [p["v"] for p in points]
    rets = daily_returns(values)
    vol = annualised_volatility(rets)
    dd = max_drawdown(values)
    years = (all_days[-1] - all_days[0]).days / 365.25
    total = values[-1] / values[0] - 1.0
    cagr = ((values[-1] / values[0]) ** (1 / years) - 1) if years >= 1 else None

    # Trim the series for charting.
    step = max(1, len(points) // 500)

    return {
        "available": True,
        "name": "EGX Composite (built by this platform)",
        "is_official": False,
        "members": len(series_by_sec),
        "member_tickers": sorted(series_by_sec.keys()),
        "start_date": all_days[0].isoformat(),
        "end_date": all_days[-1].isoformat(),
        "years": round(years, 2),
        "start_level": 1000.0,
        "current_level": round(values[-1], 1),
        "total_return_pct": round(total * 100, 2),
        "cagr_pct": round(cagr * 100, 2) if cagr is not None else None,
        "volatility_pct": round(vol * 100, 2) if vol else None,
        "max_drawdown_pct": round(dd["max_drawdown"] * 100, 2) if dd else None,
        "points": points[::step],
        "method": (
            "Equal-weighted average of the daily total returns of the %d largest "
            "EGX companies for which we hold continuous, corporate-action-free "
            "price history. Starts at 1,000 on %s."
            % (len(series_by_sec), all_days[0].isoformat())),
        "warnings": [
            "This is NOT the EGX30. The official EGX index history is not "
            "available from any free source we could find, so this is our own "
            "reference series built from prices we hold.",
            "It contains only companies still listed today. Companies that "
            "failed and were delisted are missing, which flatters the "
            "historical return. This is the largest distortion here.",
            "Every company counts equally, so a small company moves it as much "
            "as CIB does. The official EGX30 weights by market value, so the "
            "two will differ.",
            "Use it as a rough sense of market direction, not as an official "
            "figure or a precise benchmark.",
        ],
    }
