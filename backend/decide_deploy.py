"""
Decide whether the freshly built site is worth publishing.

The nightly job is scheduled to run several times shortly after the EGX close,
because there is no way to know in advance exactly when the free data source
publishes a given day's closing prices. The first attempt fires 15 minutes after
the bell; if the close has not landed yet, later attempts pick it up.

That only works if something prevents the early attempts from republishing
yesterday's data over and over. This script is that something. It compares what
was just built against what is already live and exits:

    0  -> publish (we have something genuinely newer)
    2  -> skip    (nothing new; leave the live site alone)
    1  -> error   (something is wrong; do not publish)

Exit code 2 is treated as success-but-skip by the workflow, so a holiday or a
slow source is not reported as a failure.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILT = os.path.join(ROOT, "site", "data", "status.json")

LIVE_URL = os.environ.get("LIVE_STATUS_URL",
                          "https://egx-research.pages.dev/data/status.json")

PUBLISH, SKIP, ERROR = 0, 2, 1

# The Egyptian Exchange closes at 14:30 Cairo. A short settle window after that
# guards against publishing a partial session as though it were the close.
MARKET_CLOSE_MINUTES = 14 * 60 + 30
SETTLE_MINUTES = 10


def cairo_now() -> datetime:
    """
    Current time in Cairo.

    Egypt runs DST (UTC+3 in summer, UTC+2 in winter), and GitHub's scheduler
    only speaks UTC. Rather than hard-code an offset that silently breaks twice
    a year, the offset is derived from the date.
    """
    now = datetime.now(timezone.utc)
    # Egypt observes DST from the last Friday of April to the last Thursday of
    # October. Month boundaries are close enough for deciding whether the
    # market has shut, and the workflow schedules both possibilities anyway.
    offset = 3 if 5 <= now.month <= 10 else 2
    return now + timedelta(hours=offset)


def fetch_live_date() -> str | None:
    """The market date the currently published site is showing."""
    try:
        from curl_cffi import requests as cr
        r = cr.Session(impersonate="chrome").get(LIVE_URL, timeout=25)
        if r.status_code != 200:
            return None
        return r.json().get("latest_market_date")
    except Exception as e:
        print("  could not read the live site (%s: %s)" % (type(e).__name__, e))
        return None


def main() -> int:
    if not os.path.isfile(BUILT):
        print("FAIL  no built site found at site/data/status.json")
        return ERROR

    built = json.load(open(BUILT, encoding="utf-8"))
    built_date = built.get("latest_market_date")
    if not built_date:
        print("FAIL  the built site has no market date")
        return ERROR

    now = cairo_now()
    today = now.date().isoformat()
    print("  Cairo time now      : %s" % now.strftime("%Y-%m-%d %H:%M"))
    print("  built site data date: %s" % built_date)

    live_date = fetch_live_date()
    print("  live site data date : %s" % (live_date or "unknown"))

    # Nothing newer than what is already public.
    if live_date and built_date <= live_date:
        if built_date == today:
            print("\nSKIP  today's close is already published. Nothing to do.")
        else:
            print("\nSKIP  no newer session available yet "
                  "(the market may be closed today, or the source has not "
                  "published the close). A later run will pick it up.")
        return SKIP

    # We have something new -- but if it is dated today, make sure the market
    # has actually shut. Because both daylight-saving offsets are scheduled,
    # some attempts land mid-session; a bar fetched then would be a partial
    # day's trading, and publishing it as "the close" would be wrong.
    if built_date == today:
        minutes = now.hour * 60 + now.minute
        if minutes < MARKET_CLOSE_MINUTES + SETTLE_MINUTES:
            print("\nSKIP  the data is dated today, but Cairo time is %s and the "
                  "exchange does not close until %02d:%02d. This could be a "
                  "partial session rather than the close, so it is not "
                  "published. A later attempt will handle it."
                  % (now.strftime("%H:%M"),
                     MARKET_CLOSE_MINUTES // 60, MARKET_CLOSE_MINUTES % 60))
            return SKIP
        print("\nPUBLISH  today's closing prices have arrived.")
    else:
        print("\nPUBLISH  newer data than what is live (%s -> %s)."
              % (live_date or "unknown", built_date))
    return PUBLISH


if __name__ == "__main__":
    sys.exit(main())
