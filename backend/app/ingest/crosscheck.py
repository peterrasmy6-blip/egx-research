"""
Checking our prices against an independent source.

Why
---
Everything on this platform — every price, every dividend, every financial
statement — comes from a single free provider. In the last few weeks alone that
provider served nothing at all for several major listings under their short
tickers, emitted zero-volume bars on a public holiday, carried unadjusted share
splits for 34 companies, and printed prices that leapt and returned within
days. Each was caught, but only because a check existed for that specific
fault. A concentration this complete deserves a general check as well.

What this does, and what it does not
------------------------------------
It fetches the latest published price for every EGX company from a second,
independent site and compares it against ours. Where the two disagree by more
than a small margin, it says so.

It does **not** overwrite anything. A second source is not more authoritative
than the first; it is a witness. Two sources agreeing raises confidence, two
disagreeing means something is wrong and a person should look. Silently
replacing one number with another would hide exactly the signal this exists to
produce.

Limits, stated plainly
----------------------
Only the latest price is comparable — the second source publishes no history.
Prices legitimately differ by small amounts because the two sites capture at
different moments and round differently, which is why the threshold is not
zero. And a company absent from the second source is not evidence of anything.
"""
from __future__ import annotations

import html
import re
from datetime import date

from sqlalchemy import select

from ..models import Security, SecurityMetrics

SOURCE_NAME = "african-markets"
SOURCE_URL = ("https://www.african-markets.com/en/stock-markets/egx/"
              "listed-companies")

# Below this the two sites are simply rounding or capturing at different
# moments. Above it, one of them is wrong about something.
TOLERANCE_PCT = 2.0

# A gap this large is not a rounding difference; it usually means a share split
# one source applied and the other did not.
SEVERE_PCT = 15.0


def fetch_prices(verbose: bool = True) -> dict[str, float]:
    """Latest published price per ticker, from the second source."""
    from curl_cffi import requests as cr

    s = cr.Session(impersonate="chrome")
    r = s.get(SOURCE_URL, timeout=45)
    r.raise_for_status()

    out: dict[str, float] = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S):
        m = re.search(r"code=([A-Z0-9]{2,8})'", row)
        if not m:
            continue
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        # The page lists every company twice, in two different table layouts:
        # a full one (name, sector, price, day change, year change, market
        # value, date) and a shorter one where the third cell is the market
        # value rather than the price. Reading the short layout positionally
        # produced "differences" of 371,538,641,884% -- which is the sort of
        # number that tells you the parser is broken, not the data.
        if len(cells) < 6:
            continue
        if m.group(1) in out:
            continue          # first occurrence is the full table
        raw = cells[2].replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if value > 0:
            out[m.group(1)] = value

    if len(out) < 100:
        raise RuntimeError(
            "Cross-check source returned only %d prices; the page layout has "
            "probably changed. Treating that as a failed check rather than as "
            "agreement." % len(out))
    if verbose:
        print("  cross-check source: %d prices" % len(out))
    return out


def compare(db, verbose: bool = True) -> dict:
    """Compare our latest prices against the second source."""
    try:
        theirs = fetch_prices(verbose)
    except Exception as e:
        if verbose:
            print("  cross-check unavailable (%s)" % e)
        return {"available": False, "reason": str(e)}

    rows = db.execute(
        select(Security, SecurityMetrics)
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(Security.asset_type == "equity",
               Security.listing_status == "listed")).all()

    agree, disagree, missing = 0, [], 0
    for sec, m in rows:
        ours = m.price if m else None
        other = theirs.get(sec.ticker)
        if ours is None or other is None:
            missing += 1
            continue
        diff_pct = (other / ours - 1.0) * 100 if ours else None
        if diff_pct is None:
            missing += 1
            continue
        if abs(diff_pct) <= TOLERANCE_PCT:
            agree += 1
        else:
            disagree.append({
                "ticker": sec.ticker,
                "name": sec.name_en,
                "ours": round(ours, 4),
                "theirs": round(other, 4),
                "difference_pct": round(diff_pct, 1),
                "severe": abs(diff_pct) >= SEVERE_PCT,
            })

    disagree.sort(key=lambda d: -abs(d["difference_pct"]))
    checked = agree + len(disagree)
    result = {
        "available": True,
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "checked_on": date.today().isoformat(),
        "compared": checked,
        "agree": agree,
        "agree_pct": round(agree / checked * 100, 1) if checked else None,
        "not_in_second_source": missing,
        "tolerance_pct": TOLERANCE_PCT,
        "disagreements": disagree,
        "severe_count": sum(1 for d in disagree if d["severe"]),
        "note": (
            "Compares our latest price for each company against a second, "
            "independent site. Differences under %.0f%% are normal — the two "
            "capture at different moments and round differently. Larger gaps "
            "mean one of the two is wrong, and neither is assumed to be "
            "right: nothing here overwrites our data, it only flags where a "
            "person should look." % TOLERANCE_PCT),
    }

    if verbose:
        print("  cross-check: %d compared, %d agree (%.0f%%), %d differ, "
              "%d severe" % (checked, agree, result["agree_pct"] or 0,
                             len(disagree), result["severe_count"]))
        for d in disagree[:8]:
            print("     %-8s ours %.2f vs %.2f  (%+.1f%%)%s"
                  % (d["ticker"], d["ours"], d["theirs"], d["difference_pct"],
                     "  <-- severe" if d["severe"] else ""))
    return result


# --------------------------------------------------------------------------
# Caching
#
# The check makes a network call, which does not belong inside the site export:
# it made a build take nearly two minutes, put it at the mercy of another
# site's uptime, and ran the same request twice per pipeline. The refresh job
# runs it and writes the answer here; the export just reads it.
CACHE_NAME = "crosscheck.json"


def _cache_path() -> str:
    import os
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    return os.path.join(os.path.dirname(root), "data", CACHE_NAME)


def save(result: dict) -> None:
    import json
    import os
    path = _cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, default=str)


def load() -> dict:
    """The last stored comparison, or a clear 'not run' rather than silence."""
    import json
    import os
    path = _cache_path()
    if not os.path.isfile(path):
        return {"available": False,
                "reason": "The price cross-check has not run yet. It runs with "
                          "the weekly data refresh."}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"available": False, "reason": str(e)}


def refresh(db, verbose: bool = True) -> dict:
    """Run the comparison and store it for the next export."""
    result = compare(db, verbose=verbose)
    save(result)
    return result
