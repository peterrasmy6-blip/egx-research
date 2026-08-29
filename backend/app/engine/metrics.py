"""
Per-security metric snapshots.

Computing ratios and risk statistics on every page load would be slow across a
224-company universe, so results are computed once and stored in
`security_metrics`. The snapshot records when it was built, and the UI shows
that date -- a cached number that pretends to be live is a data-quality bug.

Every metric here is derived from raw data we hold. None is copied from a
vendor's pre-computed field.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from sqlalchemy import select, func

from ..models import Security, Price, Dividend, SecurityMetrics
from .analytics import (
    latest_price, price_on_or_before, price_series, daily_returns,
    annualised_volatility, max_drawdown, dividends_between, TRADING_DAYS,
)
from .fundamentals import statement_history


def _pct_change(a, b):
    if a is None or b is None or b == 0:
        return None
    return (a / b - 1.0) * 100


def _perf(db, sec_id, last, days, safe_from=None):
    """
    Trailing return, or None if it cannot be computed honestly.

    Returns None when the measurement window spans a known price
    discontinuity. A return calculated across an unadjusted share split is not
    approximate -- it is fabricated. Reporting nothing is correct; reporting
    "+805%" because a 6-for-1 consolidation was never applied backwards is not.
    """
    start = last.d - timedelta(days=days)
    ref = price_on_or_before(db, sec_id, start)
    if ref is None or ref.adj_close <= 0 or ref.d == last.d:
        return None
    if safe_from is not None and ref.d < safe_from:
        return None
    return round((last.adj_close / ref.adj_close - 1.0) * 100, 2)


def compute_metrics(db, sec) -> dict:
    """Build a full metric snapshot for one security."""
    last = latest_price(db, sec.id)
    out = {"ticker": sec.ticker, "as_of": None}
    if last is None:
        return out

    out["as_of"] = last.d
    out["price"] = last.close

    # Only measure returns over a window free of unadjusted corporate actions.
    safe_from = sec.price_safe_from
    out["price_integrity"] = sec.price_integrity or "unknown"

    prev = price_on_or_before(db, sec.id, last.d - timedelta(days=1))
    out["day_change_pct"] = (round((last.close / prev.close - 1) * 100, 2)
                             if prev and prev.close else None)

    for label, days in (("1w", 7), ("1m", 30), ("3m", 91), ("6m", 182),
                        ("1y", 365), ("3y", 1095), ("5y", 1826)):
        out["ret_" + label] = _perf(db, sec.id, last, days, safe_from)

    series = price_series(db, sec.id)
    out["history_days"] = len(series)
    out["price_start"] = series[0].d if series else None

    # Risk statistics are computed only on the continuous part of the series;
    # a split-induced jump would otherwise register as enormous volatility.
    clean_series = ([p for p in series if p.d >= safe_from] if safe_from
                    else series)
    adj = [p.adj_close for p in clean_series]
    if len(adj) > 40:
        out["volatility_pct"] = round(
            (annualised_volatility(daily_returns(adj[-TRADING_DAYS * 3:])) or 0) * 100, 2) or None
        dd = max_drawdown([p.close for p in clean_series])
        out["max_drawdown_pct"] = round(dd["max_drawdown"] * 100, 2) if dd else None

    # 52-week range. A company we hold only a current quote for has a single
    # bar, which would otherwise report itself as both its own 52-week high and
    # low and sit at "0% from high" -- true, and completely uninformative.
    yr = [p for p in series if p.d >= last.d - timedelta(days=365)]
    if len(yr) > 5:
        hi = max(p.close for p in yr)
        lo = min(p.close for p in yr)
        out["high_52w"], out["low_52w"] = hi, lo
        out["pct_from_high"] = round((last.close / hi - 1) * 100, 2) if hi else None

    # dividends
    ttm = dividends_between(db, sec.id, last.d - timedelta(days=365), last.d)
    dps = sum(d.amount_per_share for d in ttm)
    out["dividend_ttm"] = dps or None
    out["dividend_yield_pct"] = round(dps / last.close * 100, 2) if dps and last.close else None

    prev_ttm = dividends_between(db, sec.id, last.d - timedelta(days=730),
                                 last.d - timedelta(days=365))
    prev_dps = sum(d.amount_per_share for d in prev_ttm)
    out["dividend_growth_pct"] = (round((dps / prev_dps - 1) * 100, 2)
                                  if dps and prev_dps > 0 else None)

    # --- fundamentals ---
    hist = statement_history(db, sec.id, "annual")
    out["statement_periods"] = len(hist)
    if hist:
        h = hist[0]
        v = h["values"]
        out["latest_period"] = h["period_end"]
        shares = v.get("shares") or sec.shares_outstanding
        out["shares"] = shares
        out["revenue"] = v.get("revenue")
        out["net_income"] = v.get("net_income")
        out["total_equity"] = v.get("total_equity")
        out["total_debt"] = v.get("total_debt")
        out["free_cash_flow"] = v.get("free_cash_flow")

        out["net_margin_pct"] = (round(h["margins"]["net_margin"] * 100, 2)
                                 if h["margins"]["net_margin"] is not None else None)
        out["operating_margin_pct"] = (round(h["margins"]["operating_margin"] * 100, 2)
                                       if h["margins"]["operating_margin"] is not None else None)
        out["roe_pct"] = (round(h["returns"]["roe"] * 100, 2)
                          if h["returns"]["roe"] is not None else None)
        out["roa_pct"] = (round(h["returns"]["roa"] * 100, 2)
                          if h["returns"]["roa"] is not None else None)
        out["debt_to_equity"] = (round(h["leverage"]["debt_to_equity"], 2)
                                 if h["leverage"]["debt_to_equity"] is not None else None)
        out["eps"] = h.get("eps")

        g = h.get("growth") or {}
        out["revenue_growth_pct"] = round(g["revenue"] * 100, 2) if g.get("revenue") is not None else None
        out["earnings_growth_pct"] = round(g["net_income"] * 100, 2) if g.get("net_income") is not None else None

        if out.get("eps") and out["eps"] > 0:
            out["pe"] = round(last.close / out["eps"], 2)
        if out.get("total_equity") and shares:
            bvps = out["total_equity"] / shares
            if bvps > 0:
                out["pb"] = round(last.close / bvps, 2)
                out["book_value_per_share"] = round(bvps, 3)
        if out.get("revenue") and shares:
            sps = out["revenue"] / shares
            if sps > 0:
                out["ps"] = round(last.close / sps, 2)

        # ------------------------------------------------------------------
        # Units / currency consistency check.
        #
        # Several EGX companies have a second share class quoted in US dollars
        # (FAITA alongside FAIT, for example). The financial statements are
        # filed once, in Egyptian pounds, so dividing a dollar price by
        # pound-denominated earnings produces nonsense: FAITA came out at a P/E
        # of 0.15 and "undervalued by 2,934%".
        #
        # Every sound company in this universe sits between roughly 0.7 and 6
        # times book value. A price below a tenth of book value alongside a P/E
        # under 1 is not a bargain -- it means the two figures are not in the
        # same money. Per-share measures are then withheld rather than
        # published as a spectacular discount.
        pe_val, pb_val = out.get("pe"), out.get("pb")
        suspect = (pb_val is not None and pe_val is not None
                   and pb_val < 0.10 and pe_val < 1.0)
        out["units_suspect"] = bool(suspect)
        if suspect:
            for k in ("pe", "pb", "ps", "eps", "book_value_per_share"):
                out[k] = None

        # Market cap from our own share count where possible.
        if shares and not suspect:
            out["market_cap"] = last.close * shares
        elif sec.market_cap:
            out["market_cap"] = sec.market_cap

        # Enterprise value and EV/EBITDA
        ebitda = v.get("ebitda")
        if out.get("market_cap") and out.get("total_debt") is not None:
            ev = out["market_cap"] + out["total_debt"] - (v.get("cash") or 0)
            out["enterprise_value"] = ev
            if ebitda and ebitda > 0:
                out["ev_ebitda"] = round(ev / ebitda, 2)

        # ROIC: operating profit after tax over invested capital.
        op = v.get("operating_income")
        if op and out.get("total_equity") and out.get("total_debt") is not None:
            invested = out["total_equity"] + out["total_debt"]
            if invested > 0:
                out["roic_pct"] = round(op * (1 - 0.225) / invested * 100, 2)

        # 3-year compound revenue growth
        if len(hist) >= 4:
            new = hist[0]["values"].get("revenue")
            old = hist[3]["values"].get("revenue")
            if new and old and old > 0:
                out["revenue_cagr_3y_pct"] = round(((new / old) ** (1 / 3) - 1) * 100, 2)
    else:
        out["market_cap"] = sec.market_cap

    return out


def refresh_metrics(db, verbose: bool = True) -> int:
    """Rebuild the snapshot for every security."""
    n = 0
    for sec in db.scalars(select(Security)).all():
        m = compute_metrics(db, sec)
        row = db.scalar(select(SecurityMetrics)
                        .where(SecurityMetrics.security_id == sec.id))
        if row is None:
            row = SecurityMetrics(security_id=sec.id)
            db.add(row)
        for k, val in m.items():
            if k == "ticker":
                continue
            if hasattr(row, k):
                setattr(row, k, val)
        row.computed_at = datetime.utcnow()
        n += 1
        if n % 50 == 0:
            db.commit()
            if verbose:
                print("  metrics: %d" % n)
    db.commit()
    if verbose:
        print("  metrics computed for %d securities" % n)
    return n


def sector_medians(db) -> dict:
    """
    Median valuation multiples per sector.

    Used as the benchmark in relative valuation. Egyptian equities trade at
    multiples far below developed markets, so importing a foreign benchmark
    would make almost every EGX company look cheap.
    """
    rows = db.execute(
        select(Security.sector, SecurityMetrics.pe, SecurityMetrics.pb,
               SecurityMetrics.ps)
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(Security.sector.isnot(None))).all()

    buckets: dict[str, dict[str, list]] = {}
    for sector, pe, pb, ps in rows:
        b = buckets.setdefault(sector, {"pe": [], "pb": [], "ps": []})
        # Discard implausible multiples rather than let them drag the median.
        if pe and 0 < pe < 100:
            b["pe"].append(pe)
        if pb and 0 < pb < 20:
            b["pb"].append(pb)
        if ps and 0 < ps < 50:
            b["ps"].append(ps)

    def med(xs):
        xs = sorted(xs)
        if len(xs) < 3:
            return None          # too few peers to call it a benchmark
        n = len(xs)
        return round(xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2, 2)

    return {s: {k: med(v) for k, v in b.items()} for s, b in buckets.items()}
