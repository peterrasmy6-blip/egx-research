"""
How a company or a portfolio behaved through Egypt's actual currency shocks.

Why this and not a hypothetical
-------------------------------
Every forward-looking tool on this site says the same thing in different
words: the future is uncertain, here is a range. That is true and it is easy to
read past. What is much harder to read past is "this share fell 43% the last
time the pound was devalued, and took two years to recover".

Egypt has devalued sharply five times in a decade. That is not a tail risk
being imagined for the sake of a stress test — it is the single most important
thing that has happened to Egyptian investors in living memory, and it is
already in the price history this platform holds.

So rather than shock a model by an invented percentage, this replays what
actually happened. No assumptions, no distribution, no simulation: just the
measured drawdown through each episode and how long the recovery took.

What it cannot tell you
-----------------------
That the next one will look like the last. The 2016 float and the 2024
devaluation had very different effects, because the market entered them at
different valuations with different foreign ownership. The value here is in
showing the spread of outcomes a real shock produced, not in predicting the
next.

Companies also change. A business that earned in dollars in 2016 may not today,
which is exactly why the per-episode detail is shown rather than an average.
"""
from __future__ import annotations

from datetime import date

from .analytics import price_series

# Egypt's currency events, with a window wide enough to capture the fall and
# the immediate aftermath. Dates are the widely reported ones; the windows are
# deliberately generous because a devaluation is a process, not a day.
EPISODES = [
    {"id": "float-2016", "name": "The 2016 float",
     "start": date(2016, 10, 15), "end": date(2017, 6, 30),
     "note": "The pound was floated on 3 November 2016 and roughly halved "
             "against the dollar within days."},
    {"id": "devaluation-2022-03", "name": "March 2022",
     "start": date(2022, 2, 15), "end": date(2022, 9, 30),
     "note": "The first of the post-pandemic devaluations, as the war in "
             "Ukraine hit Egypt's wheat imports and tourism."},
    {"id": "devaluation-2022-10", "name": "October 2022",
     "start": date(2022, 9, 15), "end": date(2023, 2, 28),
     "note": "A further sharp fall as the currency shortage deepened."},
    {"id": "devaluation-2024-03", "name": "March 2024",
     "start": date(2024, 2, 15), "end": date(2024, 9, 30),
     "note": "The pound was allowed to fall again alongside the Ras El Hekma "
             "investment and a new IMF programme."},
]

MIN_BARS = 15


def _episode_stats(prices, ep) -> dict | None:
    """Worst fall and recovery within one episode window, from real bars."""
    window = [p for p in prices if ep["start"] <= p.d <= ep["end"]]
    if len(window) < MIN_BARS:
        return None

    start_px = window[0].adj_close
    if not start_px or start_px <= 0:
        return None

    peak = start_px
    trough_at = window[0].d
    peak_at_trough = start_px
    max_fall = 0.0
    for p in window:
        v = p.adj_close
        if not v or v <= 0:
            continue
        peak = max(peak, v)
        fall = v / peak - 1.0
        if fall < max_fall:
            max_fall = fall
            trough_at = p.d
            peak_at_trough = peak

    end_px = window[-1].adj_close

    # Recovery means getting back to the level it fell *from*, not to wherever
    # the window happened to open. Measuring against the opening price produced
    # "recovered in 1 day" for a share that had fallen 25% from a peak it never
    # regained -- technically true, and useless to a reader asking how long it
    # took to get back.
    recovered_at = None
    seen_trough = False
    for p in window:
        if p.d == trough_at:
            seen_trough = True
            continue
        if seen_trough and p.adj_close and p.adj_close >= peak_at_trough:
            recovered_at = p.d
            break

    return {
        "episode": ep["id"],
        "name": ep["name"],
        "note": ep["note"],
        "from": window[0].d.isoformat(),
        "to": window[-1].d.isoformat(),
        "worst_fall_pct": round(max_fall * 100, 1),
        "trough_on": trough_at.isoformat(),
        "fell_from": round(peak_at_trough, 4),
        "change_over_window_pct": round((end_px / start_px - 1.0) * 100, 1)
        if end_px and start_px else None,
        "recovered_on": recovered_at.isoformat() if recovered_at else None,
        "days_to_recover": ((recovered_at - trough_at).days
                            if recovered_at else None),
        "bars": len(window),
    }


def for_security(db, security_id: int) -> dict:
    """Replay every episode this company has price history for."""
    prices = price_series(db, security_id)
    if not prices:
        return {"available": False,
                "reason": "We hold no price history for this company."}

    episodes = []
    for ep in EPISODES:
        stat = _episode_stats(prices, ep)
        if stat:
            episodes.append(stat)

    if not episodes:
        return {"available": False,
                "reason": "This company's price history does not reach back to "
                          "any of Egypt's currency devaluations, so there is "
                          "nothing to replay."}

    falls = [e["worst_fall_pct"] for e in episodes]
    recovered = [e for e in episodes if e["days_to_recover"] is not None]

    return {
        "available": True,
        "episodes": episodes,
        "worst_fall_pct": min(falls),
        "average_fall_pct": round(sum(falls) / len(falls), 1),
        "episodes_covered": len(episodes),
        "episodes_total": len(EPISODES),
        "typical_recovery_days": (
            round(sum(e["days_to_recover"] for e in recovered) / len(recovered))
            if recovered else None),
        "never_recovered": [e["name"] for e in episodes
                            if e["days_to_recover"] is None],
        "note": (
            "These are measured falls from real price history, not a modelled "
            "shock. Each window covers the devaluation and the months after "
            "it. A company that has changed since — or that now earns in "
            "foreign currency when it did not before — may behave quite "
            "differently next time."),
    }


def market_summary(db, composite_points: list[dict]) -> dict:
    """The same replay for the market as a whole, as a reference line."""
    if not composite_points:
        return {"available": False}

    class _P:
        __slots__ = ("d", "adj_close")

        def __init__(self, d, v):
            self.d = d
            self.adj_close = v

    series = []
    for p in composite_points:
        raw = p.get("d") or p.get("date")
        val = p.get("v")
        if not raw or val is None:
            continue
        series.append(_P(date.fromisoformat(str(raw)[:10]), float(val)))
    series.sort(key=lambda x: x.d)

    episodes = [s for s in (_episode_stats(series, ep) for ep in EPISODES) if s]
    if not episodes:
        return {"available": False}
    falls = [e["worst_fall_pct"] for e in episodes]
    return {"available": True, "episodes": episodes,
            "worst_fall_pct": min(falls),
            "average_fall_pct": round(sum(falls) / len(falls), 1)}
