"""
How easily a share can actually be bought and sold.

Why this exists
---------------
The platform had twenty-one screener filters and not one of them touched
trading volume. That is a serious omission on this exchange in particular.

A screen for "cheap and profitable" hands back a list that mixes Commercial
International Bank, which turns over roughly half a billion pounds a day, with
companies that trade forty thousand pounds a day -- and nothing on the page
distinguished them. The second kind cannot absorb an ordinary retail order
without moving several percent, and cannot be exited at all in a falling
market. On the EGX that is the most common way a small investor actually loses
money: not by picking the wrong company, but by buying something they cannot
sell.

What is measured
----------------
Average daily traded *value* in pounds, not share count. Share count is
meaningless across companies -- a million shares at EGP 0.40 and a thousand at
EGP 400 are the same trade.

Alongside it, how many of the recent sessions the share traded at all. A stock
can show a respectable average because of one large block and be untradeable
on most days, so the two figures are always shown together.

What is deliberately not counted
--------------------------------
Bars carrying only a quoted price -- companies the free source publishes a
level for but no history -- are excluded. Their volume field is not a day's
trading and treating it as one would invent liquidity that does not exist.
Those companies report no liquidity at all, which is the honest answer.
"""
from __future__ import annotations

from sqlalchemy import select, func, distinct

from ..models import Price, Security, SecurityMetrics, NON_TRADED_SOURCES

# The window. Ninety sessions is about four and a half months of EGX trading:
# long enough that one unusual block does not dominate, short enough to still
# describe the share as it trades now.
WINDOW_SESSIONS = 90
RECENT_SESSIONS = 30

# Rows that are a published value rather than a day's trading -- a live quote,
# or a fund NAV we recorded ourselves. Counting either as volume would invent
# liquidity that does not exist.
QUOTE_SOURCE = "yahoo-isin-quote"

# Bands, set from the exchange's own distribution rather than imported from a
# developed market. Across the 205 companies with tradeable history the median
# is about EGP 22m a day and the tenth percentile about EGP 0.9m, so these cuts
# fall near the deciles that matter.
BANDS = [
    (50_000_000, "Liquid",
     "Trades enough each day that an ordinary private order is unlikely to "
     "move the price."),
    (10_000_000, "Moderate",
     "Reasonably traded. A large order might still need to be spread over "
     "more than one day."),
    (1_000_000, "Thin",
     "Lightly traded. Buying or selling a meaningful amount may move the "
     "price against you."),
    (0, "Very thin",
     "Barely traded. You may not be able to sell when you want to, and the "
     "price you get could be far from the last one quoted."),
]

# The share of a day's turnover a single private investor could realistically
# take without pushing the price. Twenty percent is a common working figure and
# is generous for a market this size.
PARTICIPATION = 0.20


NO_VOLUME_NOTE = (
    "Our free source publishes prices for this company but no trading volume, "
    "so we cannot tell you how easily it trades. That is a gap in the data, "
    "not a sign that the share is untraded.")


def band_for(adtv: float | None) -> tuple[str | None, str | None]:
    """The band name and its plain-English meaning."""
    if adtv is None:
        return None, None
    for floor, name, note in BANDS:
        if adtv >= floor:
            return name, note
    return None, None


def days_to_trade(amount_egp: float, adtv: float | None) -> float | None:
    """
    Sessions needed to build or unwind a position of this size.

    Deliberately concrete. "Average daily value EGP 380,000" means little to
    most people; "an EGP 100,000 position would take about two days to sell"
    means something immediately.
    """
    if not adtv or adtv <= 0 or amount_egp <= 0:
        return None
    capacity = adtv * PARTICIPATION
    return amount_egp / capacity


def market_sessions(db, limit: int = WINDOW_SESSIONS) -> list:
    """The most recent real trading dates, newest first."""
    return [d for (d,) in db.execute(
        select(distinct(Price.d))
        .where(Price.source.notin_(NON_TRADED_SOURCES))
        .order_by(Price.d.desc()).limit(limit))]


def for_security(db, security_id: int, sessions: list) -> dict:
    """Liquidity figures for one security over the given sessions."""
    empty = {"adtv_30d": None, "adtv_90d": None, "days_traded_90d": None,
             "sessions_in_window": len(sessions), "liquidity_band": None}
    if not sessions:
        return empty

    cutoff = sessions[-1]
    rows = db.execute(
        select(Price.d, Price.close, Price.volume)
        .where(Price.security_id == security_id,
               Price.d >= cutoff,
               Price.source.notin_(NON_TRADED_SOURCES))).all()
    if not rows:
        return empty

    recent_cut = sessions[min(RECENT_SESSIONS, len(sessions)) - 1]

    def avg(vals):
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None

    all_values, recent_values, traded = [], [], 0
    for d, close, vol in rows:
        value = (close or 0) * (vol or 0)
        all_values.append(value)
        if d >= recent_cut:
            recent_values.append(value)
        if vol:
            traded += 1

    # Zero traded days across a window in which the company clearly had prices
    # means the source publishes no volume for it -- not that nobody traded it.
    # Orascom Construction has ninety price bars and a volume of exactly zero on
    # every one; labelling it "barely traded" would be a plainly false statement
    # about one of the largest companies on the exchange. Missing data is
    # reported as missing.
    if traded == 0:
        return {"adtv_30d": None, "adtv_90d": None, "days_traded_90d": 0,
                "sessions_in_window": len(sessions), "liquidity_band": None}

    adtv_90 = avg(all_values)
    band, _ = band_for(adtv_90)
    return {
        "adtv_30d": round(avg(recent_values), 2) if recent_values else None,
        "adtv_90d": round(adtv_90, 2) if adtv_90 is not None else None,
        "days_traded_90d": traded,
        "sessions_in_window": len(sessions),
        "liquidity_band": band,
    }


def refresh(db, verbose: bool = True) -> dict:
    """Compute liquidity for every security that has real traded history."""
    sessions = market_sessions(db)
    if not sessions:
        if verbose:
            print("  liquidity: no trading sessions found")
        return {}

    counts: dict[str, int] = {}
    rows = db.execute(
        select(Security.id, SecurityMetrics)
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(Security.asset_type == "equity")).all()

    for sid, m in rows:
        vals = for_security(db, sid, sessions)
        for k, v in vals.items():
            setattr(m, k, v)
        key = vals["liquidity_band"] or "no trading data"
        counts[key] = counts.get(key, 0) + 1
    db.commit()

    if verbose:
        print("  liquidity over %d sessions:" % len(sessions))
        for name in ["Liquid", "Moderate", "Thin", "Very thin",
                     "no trading data"]:
            if counts.get(name):
                print("     %-16s %d" % (name, counts[name]))
    return counts
