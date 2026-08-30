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
        # Assets must now be root-absolute, which is the opposite of the old
        # rule. Pages live at real paths like /stock/COMI, so a relative
        # "static/app.js" would resolve to /stock/COMI/static/app.js and 404.
        # The trade-off is that the site must be served from a domain root,
        # which it is.
        if 'src="static/' in html or 'href="static/' in html:
            fail("index.html uses relative asset paths; they would 404 on any "
                 "page below the root, such as /stock/COMI")
        # No executable code from anywhere but this origin. A third-party CDN is
        # both a supply-chain risk and a single point of failure -- this project
        # has already had one host turn out to be unreachable from Egypt.
        import re as _re
        ext = [m for m in _re.findall(r'<script[^>]+src="([^"]+)"', html)
               if m.startswith(("http://", "https://", "//"))]
        if ext:
            fail("index.html loads script from another origin: %s" % ext)
        if not os.path.isfile(os.path.join(SITE, "static", "chart.umd.min.js")):
            fail("the charting library is not bundled; charts would not draw")

        # Stylesheets and fonts too. Google Fonts told a third party who was
        # reading an Egyptian investing site on every page view, and put
        # another company's server in front of the first paint. Now that the
        # CSP forbids outside hosts entirely, a reintroduced <link> would not
        # merely leak -- it would silently fail to load and the page would
        # render in a fallback font nobody chose.
        ext_css = [m for m in _re.findall(r'<link[^>]+href="([^"]+)"', html)
                   if m.startswith(("http://", "https://", "//"))
                   and "egx-research" not in m]
        if ext_css:
            fail("index.html loads a stylesheet or font from another origin, "
                 "which the Content-Security-Policy now blocks: %s" % ext_css)
        for weight in (400, 500, 600, 700):
            f = os.path.join(SITE, "static", "fonts",
                             "inter-latin-%d.woff2" % weight)
            if not os.path.isfile(f):
                fail("the %d-weight font is missing; text would fall back to "
                     "a system font" % weight)

        # Returning visitors must not run yesterday's JavaScript against
        # today's data files.
        if "?v=" not in html:
            fail("index.html does not version its assets; a cached script "
                 "would be served against fresh data")
        for page in ("views5.js",):
            if page not in html:
                fail("index.html does not load %s" % page)

    # ---- real pages, one per route ----
    #
    # Hash routing made all 269 company pages share one URL, one title and one
    # description. If that regressed, the site would silently become
    # unfindable again.
    for rel in ("sitemap.xml", "robots.txt", "404.html",
                os.path.join("stock", "COMI", "index.html"),
                os.path.join("markets", "index.html")):
        if not os.path.isfile(os.path.join(SITE, rel)):
            fail("missing generated page: %s" % rel)

    sm = os.path.join(SITE, "sitemap.xml")
    if os.path.isfile(sm):
        body = open(sm, encoding="utf-8").read()
        n_urls = body.count("<loc>")
        if n_urls < 200:
            fail("sitemap lists only %d pages" % n_urls)
        print("  sitemap: %d pages" % n_urls)

    comi = os.path.join(SITE, "stock", "COMI", "index.html")
    root = os.path.join(SITE, "index.html")
    if os.path.isfile(comi) and os.path.isfile(root):
        a = open(comi, encoding="utf-8").read()
        b = open(root, encoding="utf-8").read()
        import re as _re2
        ta = _re2.search(r"<title>(.*?)</title>", a, _re2.S)
        tb = _re2.search(r"<title>(.*?)</title>", b, _re2.S)
        if ta and tb and ta.group(1).strip() == tb.group(1).strip():
            fail("every page shares one title; search engines cannot tell "
                 "them apart")
        if "COMI" not in (ta.group(1) if ta else ""):
            fail("the company page title does not name the company")
        if 'rel="canonical"' not in a:
            fail("generated pages have no canonical link")
        if 'property="og:title"' not in a:
            fail("generated pages have no social preview tags")
        if 'class="prerender"' not in a:
            fail("generated pages carry no content a crawler can read")

    # ---- Arabic ----
    #
    # A client-side language toggle earns nothing from search: a crawler sees
    # only the language it was served. These pages are the Arabic interface's
    # own indexable surface.
    ar_home = os.path.join(SITE, "ar", "index.html")
    if not os.path.isfile(ar_home):
        fail("the Arabic landing pages were not generated")
    else:
        a = open(ar_home, encoding="utf-8").read()
        if 'lang="ar"' not in a or 'dir="rtl"' not in a:
            fail("the Arabic page is not served right-to-left; the layout would "
                 "flip on first paint and a crawler would never see Arabic")
        if 'hreflang="ar"' not in a or 'hreflang="en"' not in a:
            fail("the Arabic page has no hreflang pair, so it would compete "
                 "with the English one instead of complementing it")
        en_home = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
        if 'hreflang="ar"' not in en_home:
            fail("the English pages do not point at their Arabic equivalents")
        import re as _re3
        _t = _re3.search(r"<title>(.*?)</title>", a, _re3.S)
        if _t and not any("؀" <= ch <= "ۿ" for ch in _t.group(1)):
            fail("the Arabic page title is not in Arabic")
        n_ar = len([1 for root, _d, fs in os.walk(os.path.join(SITE, "ar"))
                    for f in fs if f == "index.html"])
        print("  Arabic: %d landing pages, served RTL with hreflang" % n_ar)

    hdr = os.path.join(SITE, "_headers")
    if not os.path.isfile(hdr):
        fail("_headers is missing; the site would ship with no security headers")
    else:
        h = open(hdr, encoding="utf-8").read()
        for needed in ("Content-Security-Policy", "X-Content-Type-Options",
                       "Referrer-Policy", "frame-ancestors"):
            if needed not in h:
                fail("_headers does not set %s" % needed)

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

        # The published universe must contain companies and nothing else. A
        # rights issue or a second share class leaking back in would put a
        # non-business on the screener and double-count a real one.
        sys.path.insert(0, os.path.join(ROOT, "backend"))
        from app.ingest.reference_universe import EXCLUDED, ORDINARY
        equities = {s["ticker"] for s in secs
                    if s.get("asset_type", "equity") == "equity"}
        leaked = sorted(equities & set(EXCLUDED))
        if leaked:
            fail("non-company instruments published as companies: %s"
                 % leaked[:10])
        missing = sorted(set(ORDINARY) - equities)
        if missing:
            fail("companies missing from the published universe: %s"
                 % missing[:10])
        stray = sorted(equities - set(ORDINARY))
        if stray:
            fail("companies published that are not in the reference "
                 "universe: %s" % stray[:10])
        print("  universe: %d companies, matches the reference list"
              % len(equities))

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

        # The platform reports what a model measured; it does not pronounce a
        # security over- or undervalued. That is a claim about a specific
        # investment, it is what gets screenshotted out of context, and it is
        # the line between research and advice. Labels must stay observational.
        VERDICT_WORDS = ("overvalued", "undervalued", "buy", "sell",
                         "recommend", "target price", "price target")
        verdicts = sorted({
            m["valuation_class"] for m in met.values()
            if m.get("valuation_class")
            and any(w in m["valuation_class"].lower() for w in VERDICT_WORDS)})
        if verdicts:
            fail("valuation labels state a verdict rather than an observation: "
                 "%s" % verdicts)

        # Liquidity must never be invented. A company with no reported volume
        # gets no band -- reporting one would tell a reader that a major
        # listing is barely traded, which is worse than saying nothing.
        false_thin = [t for t, m in met.items()
                      if m.get("liquidity_band") and not m.get("adtv_90d")]
        if false_thin:
            fail("liquidity band published without any traded value: %s"
                 % false_thin[:10])
        banded = sum(1 for m in met.values() if m.get("liquidity_band"))
        thin = sum(1 for m in met.values()
                   if m.get("liquidity_band") in ("Thin", "Very thin"))
        print("  liquidity: %d companies measured, %d flagged thin" % (banded, thin))

        classes = sorted({m.get("valuation_class") for m in met.values()
                          if m.get("valuation_class")})
        if classes:
            print("  valuation labels: %s" % ", ".join(classes))

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
