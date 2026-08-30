"""
Price-series integrity checks.

Why this module exists
----------------------
During development the platform's own homepage proudly reported that FERC had
returned +805% over one year. It had not. Its price series jumps from 9.22 to
97.57 overnight -- a 10.6x move. The Egyptian Exchange applies daily price
limits of roughly +/-10% (20% for some securities), so an overnight 10x is
arithmetically impossible as genuine trading. It is an unadjusted corporate
action: a share consolidation, bonus issue or split that the upstream source
recorded without restating the earlier history.

The same fault appeared in the opposite direction: GDWA fell 7.13 -> 1.14 in one
day (a split), producing a fake -88% "worst performer".

A return calculated across such a break is not merely imprecise -- it is
fabricated. This module finds those breaks so the platform can decline to
publish the affected figures rather than present fiction with a percentage sign
on it.

Approach
--------
Flag any single-day move larger than `JUMP_THRESHOLD` that a dividend cannot
explain. Dividends are checked because a large special dividend legitimately
drops the price on the ex-date.

The threshold is deliberately loose (60%). A genuine trading move that large is
essentially impossible under EGX price limits, so false positives are rare;
being conservative avoids flagging real volatility as corruption.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from ..models import Price, Dividend, Security

# A single-day move above this is treated as a corporate action, not trading.
# EGX daily limits are ~10-20%, so anything near this is structural.
JUMP_THRESHOLD = 0.60


def find_discontinuities(db, security_id: int) -> list[dict]:
    """
    Locate suspected unadjusted corporate actions in a price series.

    Returns one entry per break, with the implied ratio so the likely action
    (2-for-1 split, 10-for-1 consolidation) is legible.
    """
    # Bad prints are excluded here. Left in, a bar that leaps and returns looks
    # exactly like a split followed by a reverse split, and the scan then
    # suppresses genuine return figures on both sides of a break that never
    # happened.
    rows = db.scalars(select(Price)
                      .where(Price.security_id == security_id,
                             Price.suspect.is_(None) | (Price.suspect == False))  # noqa: E712
                      .order_by(Price.d)).all()
    if len(rows) < 3:
        return []

    divs = {d.ex_date: d.amount_per_share for d in db.scalars(
        select(Dividend).where(Dividend.security_id == security_id)).all()}

    breaks = []
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        if prev.close <= 0 or cur.close <= 0:
            continue
        ratio = cur.close / prev.close
        move = ratio - 1.0
        if abs(move) < JUMP_THRESHOLD:
            continue

        # A large dividend legitimately drops the price on the ex-date.
        div = divs.get(cur.d, 0.0)
        if div and move < 0 and abs(move) <= (div / prev.close) * 1.25:
            continue

        # A gap over a long suspension is suspicious but not impossible.
        gap_days = (cur.d - prev.d).days

        breaks.append({
            "date": cur.d.isoformat(),
            "previous_date": prev.d.isoformat(),
            "price_before": round(prev.close, 4),
            "price_after": round(cur.close, 4),
            "ratio": round(ratio, 4),
            "move_pct": round(move * 100, 1),
            "gap_days": gap_days,
            "likely": _describe(ratio),
        })
    return breaks


def _describe(ratio: float) -> str:
    """Name the corporate action a ratio suggests."""
    if ratio > 1:
        n = round(ratio)
        if n >= 2 and abs(ratio - n) / n < 0.18:
            return "likely a %d-for-1 share consolidation (reverse split)" % n
        return "likely a share consolidation"
    inv = 1 / ratio if ratio else 0
    n = round(inv)
    if n >= 2 and abs(inv - n) / n < 0.18:
        return "likely a 1-for-%d share split or bonus issue" % n
    return "likely a share split or bonus issue"


def assess_security(db, sec) -> dict:
    """
    Summarise price integrity for one security.

    `safe_from` is the date after the last break: returns measured entirely
    within that window are trustworthy, returns spanning a break are not.
    """
    breaks = find_discontinuities(db, sec.id)
    if not breaks:
        return {"clean": True, "breaks": [], "safe_from": None}

    last = max(b["date"] for b in breaks)
    return {
        "clean": False,
        "breaks": breaks,
        "safe_from": last,
        "note": (
            "This company's price history contains %d unexplained jump%s "
            "(most recently on %s, %s). The Egyptian Exchange limits daily "
            "moves to roughly 10-20%%, so a jump this large is a corporate "
            "action that our data source did not apply backwards. Returns "
            "measured across that date would be wrong, so we do not show them."
            % (len(breaks), "" if len(breaks) == 1 else "s", last,
               breaks[-1]["likely"])),
    }


def return_is_trustworthy(safe_from: str | None, window_start: date,
                          window_end: date) -> bool:
    """True when the measurement window does not span a known break."""
    if not safe_from:
        return True
    try:
        cut = date.fromisoformat(safe_from)
    except (TypeError, ValueError):
        return True
    return window_start >= cut


# --------------------------------------------------------------------------
# Bad prints
# --------------------------------------------------------------------------
# A separate fault from an unadjusted corporate action, and one the original
# scan quietly mislabelled. Reviewing all 36 flagged companies turned up three
# that were not corporate actions at all:
#
#   MCQE sits near 31, prints 18.89 for a single day, and resumes at 33.
#   ADPC sits at 3.02, prints 7.00 for four days, and resumes at 3.02.
#   ATQA sits near 1.00, prints 1.99 for one day, and resumes at 1.03.
#
# A real consolidation or split does not undo itself. Treating these as
# corporate actions had two costs: legitimate return figures were suppressed
# for spanning a "break" that never happened, and the wrong prices stayed in
# the series, where they inflated volatility and could set a false 52-week high
# or low.
SPIKE_THRESHOLD = 0.35     # a move this large that then reverses
SPIKE_MAX_RUN = 6          # ...within this many sessions
SPIKE_RETURN_TOLERANCE = 0.15   # ...to within this much of where it started


def find_bad_prints(db, security_id: int) -> list[dict]:
    """Bars that leap and return, which is a source error rather than trading."""
    rows = list(db.scalars(
        select(Price).where(Price.security_id == security_id)
        .order_by(Price.d)))
    if len(rows) < 20:
        return []

    out, i = [], 1
    while i < len(rows) - 1:
        prev = rows[i - 1].close
        if not prev or prev <= 0 or not rows[i].close:
            i += 1
            continue
        ratio = rows[i].close / prev
        if abs(ratio - 1.0) >= SPIKE_THRESHOLD:
            for j in range(i + 1, min(i + 1 + SPIKE_MAX_RUN, len(rows))):
                nxt = rows[j].close
                if nxt and abs(nxt / prev - 1.0) <= SPIKE_RETURN_TOLERANCE:
                    for k in range(i, j):
                        out.append({
                            "date": rows[k].d.isoformat(),
                            "price": rows[k].close,
                            "surrounding_price": round(prev, 4),
                            "reason": ("price moved %.0f%% and returned to where "
                                       "it started within %d session(s), which "
                                       "trading does not do"
                                       % ((ratio - 1) * 100, j - i)),
                        })
                    i = j
                    break
            else:
                i += 1
        else:
            i += 1
    return out


def mark_bad_prints(db, verbose: bool = True) -> dict:
    """Flag bad prints across the universe so no calculation can read them."""
    marked, affected = 0, {}
    for sec in db.scalars(select(Security)).all():
        bad = find_bad_prints(db, sec.id)
        if not bad:
            continue
        dates = {date.fromisoformat(b["date"]) for b in bad}
        for row in db.scalars(select(Price).where(
                Price.security_id == sec.id, Price.d.in_(dates))):
            row.suspect = True
            marked += 1
        affected[sec.ticker] = bad
        if verbose:
            print("  [print] %-8s %d bad bar(s): %s"
                  % (sec.ticker, len(bad), ", ".join(b["date"] for b in bad)))
    db.commit()
    if verbose:
        print("  bad prints: %d bars across %d securities"
              % (marked, len(affected)))
    return {"bars": marked, "securities": affected}


def scan_universe(db, verbose: bool = True) -> dict:
    """Check every security and record the result on the Security row."""
    flagged, clean = 0, 0
    details = {}
    for sec in db.scalars(select(Security)).all():
        a = assess_security(db, sec)
        if a["clean"]:
            sec.price_integrity = "clean"
            sec.price_safe_from = None
            clean += 1
        else:
            sec.price_integrity = "discontinuous"
            sec.price_safe_from = date.fromisoformat(a["safe_from"])
            existing = sec.data_note or ""
            if "unexplained jump" not in existing:
                sec.data_note = (existing + " " + a["note"]).strip()
            flagged += 1
            details[sec.ticker] = a["breaks"]
            if verbose:
                print("  [flag] %-8s %d break(s), latest %s (%s)"
                      % (sec.ticker, len(a["breaks"]), a["safe_from"],
                         a["breaks"][-1]["likely"]))
    db.commit()
    if verbose:
        print("  integrity: %d clean, %d flagged" % (clean, flagged))
    return {"clean": clean, "flagged": flagged, "details": details}
