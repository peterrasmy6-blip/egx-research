"""
How a company compares with the companies most like it.

Why a percentile rather than a number
-------------------------------------
"Return on equity 35%" is only meaningful next to something. Against Egyptian
banks it is excellent; against a market where several companies clear 50% it is
ordinary. A rank says which, and it says it without the reader needing to hold
the whole exchange in their head.

The peer-group problem, stated rather than hidden
-------------------------------------------------
Sector groups on this exchange are small, and much smaller once a metric is
required: Industrials has twenty listed companies and three that report a
usable price-to-earnings ratio. Ranking one company against two others produces
a percentile that looks precise and means almost nothing.

So the group is chosen per metric. Where the sector has enough companies
reporting that measure, the sector is used. Where it does not, the whole market
is, and the page says which — because "third-cheapest bank" and "third-cheapest
company on the exchange" are very different claims.

What is deliberately not done
-----------------------------
No composite score. Adding a value rank to a quality rank to a growth rank
produces a single number that looks authoritative, ranks companies against each
other, and hides every trade-off inside it. That is a recommendation list with
extra steps.
"""
from __future__ import annotations

from sqlalchemy import select

from ..models import Security, SecurityMetrics

# Below this a sector rank is noise dressed up as precision.
MIN_SECTOR_PEERS = 5

# The measures worth ranking, and which direction is conventionally "better".
# `higher_better` is used only to phrase the sentence, never to score.
METRICS = [
    ("pe", "Price / earnings", False, "x"),
    ("pb", "Price / book", False, "x"),
    ("dividend_yield_pct", "Dividend yield", True, "%"),
    ("roe_pct", "Return on equity", True, "%"),
    ("net_margin_pct", "Net margin", True, "%"),
    ("revenue_growth_pct", "Revenue growth", True, "%"),
    ("debt_to_equity", "Debt / equity", False, "x"),
    ("volatility_pct", "Volatility", False, "%"),
    ("adtv_90d", "Daily value traded", True, "EGP"),
]

# A metric outside this range is a data fault, not a valuation, and would drag
# every rank around it.
SANE = {
    "pe": (0, 200), "pb": (0, 50), "dividend_yield_pct": (0, 100),
    "roe_pct": (-200, 200), "net_margin_pct": (-500, 200),
    "revenue_growth_pct": (-100, 500), "debt_to_equity": (0, 50),
    "volatility_pct": (0, 300), "adtv_90d": (0, 1e12),
}


def _clean(key, value):
    lo, hi = SANE.get(key, (float("-inf"), float("inf")))
    if value is None:
        return None
    return value if lo <= value <= hi else None


def _percentile(value: float, pool: list[float]) -> float:
    """Share of the pool at or below this value, 0-100."""
    if not pool:
        return None
    below = sum(1 for x in pool if x <= value)
    return round(below / len(pool) * 100)


def _describe(label, pct_rank, higher_better, group_label):
    """One sentence, phrased so the direction is not left to the reader."""
    if pct_rank is None:
        return None
    strong = pct_rank >= 80 if higher_better else pct_rank <= 20
    weak = pct_rank <= 20 if higher_better else pct_rank >= 80
    if strong:
        where = "among the strongest"
    elif weak:
        where = "among the weakest"
    elif 40 <= pct_rank <= 60:
        where = "about typical"
    else:
        where = "somewhat above average" if pct_rank > 60 else "somewhat below average"
    return "%s is %s of %s." % (label, where, group_label)


def compare(db, sec, metrics) -> dict:
    """Rank one company against its peers, metric by metric."""
    if metrics is None:
        return {"available": False,
                "reason": "We hold no calculated metrics for this company."}

    rows = db.execute(
        select(Security, SecurityMetrics)
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(Security.asset_type == "equity",
               Security.listing_status == "listed")).all()

    sector_rows = [(s, m) for s, m in rows
                   if sec.sector and s.sector == sec.sector]

    out = []
    for key, label, higher_better, unit in METRICS:
        value = _clean(key, getattr(metrics, key, None))
        if value is None:
            continue

        sector_pool = [v for v in (_clean(key, getattr(m, key, None))
                                   for _s, m in sector_rows) if v is not None]
        market_pool = [v for v in (_clean(key, getattr(m, key, None))
                                   for _s, m in rows) if v is not None]

        if len(sector_pool) >= MIN_SECTOR_PEERS:
            pool, basis = sector_pool, "sector"
            group_label = "Egyptian %s companies" % (sec.sector or "").lower()
        elif len(market_pool) >= MIN_SECTOR_PEERS:
            pool, basis = market_pool, "market"
            group_label = "the exchange"
        else:
            continue

        rank = _percentile(value, pool)
        pool_sorted = sorted(pool)
        n = len(pool_sorted)
        median = (pool_sorted[n // 2] if n % 2
                  else (pool_sorted[n // 2 - 1] + pool_sorted[n // 2]) / 2)

        out.append({
            "key": key, "label": label, "unit": unit,
            "value": round(value, 4),
            "percentile": rank,
            "median": round(median, 4),
            "peers": n,
            "basis": basis,
            "higher_better": higher_better,
            "sentence": _describe(label, rank, higher_better, group_label),
        })

    if not out:
        return {"available": False,
                "reason": "There are not enough comparable companies reporting "
                          "these measures to rank this one against."}

    # What actually stands out, in either direction.
    standout_good = [o for o in out
                     if (o["percentile"] >= 80) == o["higher_better"]
                     and (o["percentile"] >= 80 or o["percentile"] <= 20)]
    standout_bad = [o for o in out
                    if (o["percentile"] <= 20) == o["higher_better"]
                    and (o["percentile"] >= 80 or o["percentile"] <= 20)]

    sector_used = sum(1 for o in out if o["basis"] == "sector")
    return {
        "available": True,
        "sector": sec.sector,
        "metrics": out,
        "stands_out": [o["label"] for o in standout_good],
        "lags": [o["label"] for o in standout_bad],
        "sector_ranks": sector_used,
        "market_ranks": len(out) - sector_used,
        "note": (
            "Each measure is ranked against the companies that report it. "
            "Where this company's sector has at least %d of them the sector is "
            "used; otherwise the whole exchange is, and the row says which. "
            "There is no combined score: adding a value rank to a quality rank "
            "produces one authoritative-looking number with every trade-off "
            "hidden inside it." % MIN_SECTOR_PEERS),
    }


def nearest(db, sec, metrics, limit: int = 6) -> list[dict]:
    """
    The companies most worth putting beside this one.

    Same sector, closest in size. Size matters because a company twenty times
    larger faces different costs of capital, different liquidity and different
    scrutiny, and comparing ratios across that gap tells you less than it
    appears to.
    """
    if not sec.sector or not metrics or not metrics.market_cap:
        return []

    rows = db.execute(
        select(Security, SecurityMetrics)
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(Security.asset_type == "equity",
               Security.listing_status == "listed",
               Security.sector == sec.sector,
               Security.id != sec.id,
               SecurityMetrics.market_cap.isnot(None))).all()

    scored = sorted(
        rows, key=lambda r: abs((r[1].market_cap or 0) - metrics.market_cap))
    return [{
        "ticker": s.ticker, "name": s.name_en,
        "market_cap": m.market_cap, "price": m.price,
        "pe": _clean("pe", m.pe), "pb": _clean("pb", m.pb),
        "roe_pct": _clean("roe_pct", m.roe_pct),
        "dividend_yield_pct": _clean("dividend_yield_pct", m.dividend_yield_pct),
        "ret_1y": m.ret_1y,
        "liquidity_band": m.liquidity_band,
    } for s, m in scored[:limit]]
