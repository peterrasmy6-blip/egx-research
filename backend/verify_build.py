"""
Pre-deploy gate for the automated pipeline.

Nobody is watching the nightly job. If the data source returns garbage, or a
refresh half-fails, the automation would happily publish it. This script is the
thing standing in the way: it inspects the built `site/` folder and exits
non-zero if anything looks wrong, which aborts the deploy and leaves the
previous good site online.

The checks are deliberately about *plausibility*, not exact values -- the data
is supposed to change every day. What must not change is its shape.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
DATA = os.path.join(SITE, "data")

# Floors, not targets. Set below current reality so ordinary drift is fine,
# but a collapse in coverage is caught.
MIN_LISTED = 180
MIN_WITH_PRICES = 150
MIN_WITH_STATEMENTS = 60
MIN_PRICE_ROWS = 350_000
MIN_COMPANY_FILES = 180
MAX_DATA_AGE_DAYS = 12          # EGX closes Fri/Sat; allow holidays too

failures: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def load(name: str):
    path = os.path.join(DATA, name)
    if not os.path.isfile(path):
        fail("missing file: data/%s" % name)
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        fail("data/%s is not valid JSON: %s" % (name, e))
        return None


def main() -> int:
    # ---- the shell must exist ----
    for rel in ("index.html", "static/app.js", "static/engine.js",
                "static/api.js", "static/views.js", "static/views2.js",
                "static/views3.js", "static/app.css"):
        if not os.path.isfile(os.path.join(SITE, rel)):
            fail("missing file: %s" % rel)

    idx = os.path.join(SITE, "index.html")
    if os.path.isfile(idx):
        html = open(idx, encoding="utf-8").read()
        if "engine.js" not in html or "api.js" not in html:
            fail("index.html does not load the engine and data layer")
        if 'src="/' in html or 'href="/' in html:
            fail("index.html uses absolute paths; it would break on a subfolder host")

    # ---- status ----
    st = load("status.json")
    if st:
        if st.get("securities_listed", 0) < MIN_LISTED:
            fail("only %s listed securities (expected >= %d)"
                 % (st.get("securities_listed"), MIN_LISTED))
        if st.get("securities_with_prices", 0) < MIN_WITH_PRICES:
            fail("only %s securities have prices (expected >= %d)"
                 % (st.get("securities_with_prices"), MIN_WITH_PRICES))
        if st.get("securities_with_statements", 0) < MIN_WITH_STATEMENTS:
            fail("only %s securities have statements (expected >= %d)"
                 % (st.get("securities_with_statements"), MIN_WITH_STATEMENTS))
        if st.get("price_rows", 0) < MIN_PRICE_ROWS:
            fail("only %s price rows (expected >= %d)"
                 % (st.get("price_rows"), MIN_PRICE_ROWS))

        latest = st.get("latest_market_date")
        if not latest:
            fail("status.json has no latest_market_date")
        else:
            age = (date.today() - date.fromisoformat(latest)).days
            print("  market data date: %s (%d days old)" % (latest, age))
            if age > MAX_DATA_AGE_DAYS:
                fail("market data is %d days old (limit %d) - the source is "
                     "probably failing" % (age, MAX_DATA_AGE_DAYS))
            elif age > 5:
                warn("market data is %d days old" % age)

    # ---- universe ----
    secs = load("securities.json")
    if secs is not None:
        if len(secs) < MIN_LISTED:
            fail("securities.json holds only %d companies" % len(secs))
        priced = [s for s in secs if s.get("price")]
        if len(priced) < MIN_WITH_PRICES:
            fail("only %d companies carry a price" % len(priced))
        # A price of zero or a negative is never real.
        bad = [s["ticker"] for s in secs
               if s.get("price") is not None and s["price"] <= 0]
        if bad:
            fail("non-positive prices: %s" % bad[:10])

    # ---- metrics sanity: the guards must still be holding ----
    met = load("metrics.json")
    if met:
        bad_pe = [t for t, m in met.items()
                  if m.get("pe") is not None and m["pe"] < 1]
        if bad_pe:
            fail("companies published with a P/E below 1 (currency mismatch "
                 "guard failed): %s" % bad_pe[:10])
        bad_pb = [t for t, m in met.items()
                  if m.get("pb") is not None and m["pb"] < 0.10]
        if bad_pb:
            fail("companies published with a P/B below 0.10: %s" % bad_pb[:10])
        unreliable = [t for t, m in met.items()
                      if m.get("valuation_class") == "Insufficient reliable data"
                      and m.get("upside_pct") is not None]
        if unreliable:
            fail("upside published for companies we refuse to classify: %s"
                 % unreliable[:10])

    # ---- company files ----
    cdir = os.path.join(DATA, "company")
    if not os.path.isdir(cdir):
        fail("missing data/company/ folder")
    else:
        files = [f for f in os.listdir(cdir) if f.endswith(".json")]
        print("  company files: %d" % len(files))
        if len(files) < MIN_COMPANY_FILES:
            fail("only %d company files (expected >= %d)"
                 % (len(files), MIN_COMPANY_FILES))
        # Spot-check the most liquid names actually carry data.
        for tk in ("COMI", "SWDY", "ETEL"):
            p = os.path.join(cdir, "%s.json" % tk)
            if not os.path.isfile(p):
                fail("missing company file for %s" % tk)
                continue
            co = json.load(open(p, encoding="utf-8"))
            n = len((co.get("prices") or {}).get("d") or [])
            if n < 500:
                fail("%s has only %d price points" % (tk, n))
            if not co.get("price") or co["price"] <= 0:
                fail("%s has no usable price" % tk)

    # ---- report ----
    print()
    for w in warnings:
        print("  WARN  %s" % w)
    if failures:
        print()
        for f in failures:
            print("  FAIL  %s" % f)
        print("\n%d check(s) failed - refusing to deploy. The previously "
              "published site stays online." % len(failures))
        return 1

    print("\nAll checks passed - safe to deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
