"""
Real HTML pages, one per route.

The problem this solves
-----------------------
The site was a single-page app on hash routes. Everything after a "#" is, to a
search engine, the same page -- so all 269 company pages shared one URL, one
title and one description. Searching for "CIB share price" could never find
this site, and a link pasted into WhatsApp or LinkedIn rendered with no title
card. For a platform whose whole purpose is to be found and shared, that is not
a detail.

What is generated
-----------------
A real file for every route: `/stock/COMI/index.html`, `/markets/index.html`,
and so on. Each carries its own title, description, canonical link, social
preview tags and structured data, plus enough readable content that a crawler
which never runs JavaScript still learns what the page is about.

The application then boots exactly as before and replaces that content with the
live interface. The pre-rendered block is a floor, not a mirror -- it holds the
handful of facts worth indexing, not a copy of the whole page.

Why not server-side rendering
-----------------------------
Because the site has no server, and adding one would break the zero-cost
constraint that makes the project possible. A build-time file per route gets
the indexing benefit for nothing.
"""
from __future__ import annotations

import html
import json
import os
import re

SITE_NAME = "EGX Research"
DEFAULT_DESC = ("Free research, valuation, historical scenarios and financial "
                "education for the Egyptian Exchange. Real data, calculated "
                "from company filings. Not investment advice.")


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)


def _money(x, currency="EGP") -> str:
    if x is None:
        return "not available"
    return "%s %s" % (currency, ("%,.2f" % x).replace(",", ",")
                      if False else "{:,.2f}".format(x))


def _pct(x) -> str:
    return "not available" if x is None else "{:+.1f}%".format(x)


def _big(x, currency="EGP") -> str:
    if x is None:
        return "not available"
    for cut, suffix in ((1e12, "tn"), (1e9, "bn"), (1e6, "m"), (1e3, "k")):
        if abs(x) >= cut:
            return "%s %.2f%s" % (currency, x / cut, suffix)
    return "%s %.2f" % (currency, x)


# --------------------------------------------------------------------------
def render_shell(base_html: str, *, path: str, title: str, description: str,
                 site_url: str, body: str = "", jsonld: list | None = None,
                 noindex: bool = False, alternates: list | None = None,
                 lang: str = "en") -> str:
    """
    Take the app shell and give this route its own head and pre-rendered body.

    The shell is edited rather than rebuilt so there is exactly one copy of the
    markup: a second template would drift from the first within a week.
    """
    canonical = site_url.rstrip("/") + path
    out = base_html

    out = re.sub(r"<title>.*?</title>",
                 "<title>%s</title>" % esc(title), out, count=1, flags=re.S)
    out = re.sub(r'<meta name="description" content="[^"]*">',
                 '<meta name="description" content="%s">' % esc(description),
                 out, count=1)

    head_extra = [
        '<link rel="canonical" href="%s">' % esc(canonical),
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="%s">' % esc(SITE_NAME),
        '<meta property="og:title" content="%s">' % esc(title),
        '<meta property="og:description" content="%s">' % esc(description),
        '<meta property="og:url" content="%s">' % esc(canonical),
        '<meta property="og:locale" content="en_EG">',
        # A shared link with no image is a grey box in WhatsApp and LinkedIn,
        # which is most of how this site will actually travel.
        '<meta property="og:image" content="%s">' % esc(
            site_url.rstrip("/") + "/og.png"),
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="%s">' % esc(
            "EGX Research — free analysis, valuation and financial "
            "education for the Egyptian Exchange."),
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:image" content="%s">' % esc(
            site_url.rstrip("/") + "/og.png"),
        '<meta name="twitter:title" content="%s">' % esc(title),
        '<meta name="twitter:description" content="%s">' % esc(description),
    ]
    head_extra.extend(alternates or [])
    if noindex:
        head_extra.append('<meta name="robots" content="noindex,follow">')
    for block in (jsonld or []):
        head_extra.append('<script type="application/ld+json">%s</script>'
                          % json.dumps(block, ensure_ascii=False))

    out = out.replace("</head>", "\n".join(head_extra) + "\n</head>", 1)

    # An Arabic page has to arrive right-to-left. Leaving it to JavaScript
    # means the first paint is left-to-right and the whole layout visibly
    # jumps -- and a crawler that runs no script never sees Arabic at all.
    if lang == "ar":
        out = re.sub(r"<html[^>]*>", '<html lang="ar" dir="rtl">', out, count=1)
        out = out.replace("<body", '<body data-lang="ar"', 1)

    if body:
        # Sits inside the mount point and is replaced the moment the app runs.
        # A crawler that never executes JavaScript still reads it.
        # The mount point is <main id="view">, not a div. Match on the id so
        # this keeps working if the element ever changes, and fail loudly if it
        # is not found -- silently dropping the crawlable content would undo
        # the whole point of generating these pages.
        out, n = re.subn(r'(<[a-zA-Z]+[^>]*\bid="view"[^>]*>)',
                         lambda m: m.group(1) + "\n" + body, out, count=1)
        if not n:
            raise RuntimeError(
                "could not find the #view mount point in the app shell; "
                "pre-rendered content would have been dropped silently")
    return out


# --------------------------------------------------------------------------
def company_page(s, m, val, site_url: str) -> tuple[str, str, str, list]:
    """Title, description, crawlable body and structured data for one company."""
    name, ticker = s.name_en, s.ticker
    cur = s.currency or "EGP"

    title = "%s (%s) share price, valuation and financials | %s" % (
        name, ticker, SITE_NAME)

    bits = ["%s (%s) on the Egyptian Exchange." % (name, ticker)]
    if m and m.price is not None:
        bits.append("Share price %s." % _money(m.price, cur))
    if m and m.pe is not None:
        bits.append("P/E %.2f." % m.pe)
    if m and m.dividend_yield_pct is not None:
        bits.append("Dividend yield %.2f%%." % m.dividend_yield_pct)
    bits.append("Free analysis, historical returns and fair-value range.")
    description = " ".join(bits)[:300]

    rows = []
    def row(k, v):
        rows.append("<tr><th scope=\"row\">%s</th><td>%s</td></tr>"
                    % (esc(k), esc(v)))

    if m:
        row("Share price", _money(m.price, cur))
        row("Market value", _big(m.market_cap, cur))
        row("Price / earnings", "not available" if m.pe is None else "%.2f" % m.pe)
        row("Price / book", "not available" if m.pb is None else "%.2f" % m.pb)
        row("Dividend yield", "not available" if m.dividend_yield_pct is None
            else "%.2f%%" % m.dividend_yield_pct)
        row("Return on equity", "not available" if m.roe_pct is None
            else "%.1f%%" % m.roe_pct)
        row("1-year return", _pct(m.ret_1y))
        if m.real_ret_1y is not None:
            row("1-year return after inflation", _pct(m.real_ret_1y))
        row("5-year return", _pct(m.ret_5y))
        if m.real_ret_5y is not None:
            row("5-year return after inflation", _pct(m.real_ret_5y))
        if m.liquidity_band:
            row("How easily it trades", m.liquidity_band)
    if s.sector:
        row("Sector", s.sector)
    if s.isin:
        row("ISIN", s.isin)

    val_para = ""
    if val and val.get("available"):
        val_para = (
            "<p>A model estimate puts the value of a %s share between %s and %s, "
            "against a market price of %s. This is a range produced from stated "
            "assumptions, not a price target and not advice.</p>"
            % (esc(ticker), esc(_money(val.get("bear"), cur)),
               esc(_money(val.get("bull"), cur)),
               esc(_money(val.get("price"), cur))))

    body = """
<div class="prerender">
  <h1>%s (%s)</h1>
  <p>%s is listed on the Egyptian Exchange. The figures below are calculated
     from its own filings and from market prices, and are updated after each
     trading day.</p>
  <table><caption>Key figures for %s</caption><tbody>%s</tbody></table>
  %s
  <p>This page is part of a free research tool for Egyptian investors. It does
     not provide personalised investment advice.</p>
</div>""" % (esc(name), esc(ticker), esc(name), esc(ticker),
             "".join(rows), val_para)

    jsonld = [{
        "@context": "https://schema.org",
        "@type": "Corporation",
        "name": name,
        "tickerSymbol": ticker,
        "url": site_url.rstrip("/") + "/stock/" + ticker,
        **({"identifier": s.isin} if s.isin else {}),
        **({"industry": s.sector} if s.sector else {}),
    }, {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Companies",
             "item": site_url.rstrip("/") + "/markets"},
            {"@type": "ListItem", "position": 2, "name": "%s (%s)" % (name, ticker),
             "item": site_url.rstrip("/") + "/stock/" + ticker},
        ],
    }]
    return title, description, body, jsonld


# --------------------------------------------------------------------------
# Static routes. Each needs a title people would actually search for and a
# description that reads as a sentence rather than a keyword list.
STATIC_ROUTES = {
    "/": (
        "%s — Egyptian Exchange analysis, valuation and education" % SITE_NAME,
        DEFAULT_DESC,
        "<h1>Understand the Egyptian stock market before you invest in it</h1>"
        "<p>Free research covering every ordinary company listed on the Egyptian "
        "Exchange: share prices, financial statements, valuation ranges, "
        "historical returns after inflation, and how easily each share trades. "
        "Every figure is calculated from real filings and market data.</p>"),
    "/today": (
        "The Egyptian market today — risers, fallers and breadth | " + SITE_NAME,
        "How many EGX companies traded today, how many rose and fell, the "
        "biggest movers, and which sectors led. An index level cannot tell you "
        "how broad a move was.",
        "<h1>The Egyptian market today</h1>"
        "<p>How many companies actually traded, how many rose, and where the "
        "money went. An index can rise on a day when most shares fall.</p>"),
    "/markets": (
        "All Egyptian Exchange companies — prices and financials | " + SITE_NAME,
        "Browse every ordinary company listed on the EGX with share price, "
        "market value, returns after inflation and how easily each one trades.",
        "<h1>All Egyptian Exchange companies</h1>"
        "<p>Every ordinary listed company on the EGX, with prices, returns and "
        "data-quality labels. Companies with incomplete data are kept in the "
        "list and marked, not hidden.</p>"),
    "/screener": (
        "Egyptian stock screener — filter the EGX by value, quality and risk | " + SITE_NAME,
        "Filter Egyptian Exchange companies by P/E, dividend yield, return on "
        "equity, growth, debt, volatility and how easily they trade.",
        "<h1>Egyptian stock screener</h1>"
        "<p>Filter the whole exchange on the measures that matter, including "
        "how easily a share actually trades. Missing data excludes a company "
        "rather than counting as zero.</p>"),
    "/compare": (
        "Compare Egyptian companies side by side | " + SITE_NAME,
        "Put several Egyptian Exchange companies side by side on the same "
        "measures: valuation, profitability, growth, risk and liquidity.",
        "<h1>Compare Egyptian companies</h1>"
        "<p>Up to six companies on the same measures, calculated the same way.</p>"),
    "/scenario": (
        "What if I had invested? Egyptian stock calculator | " + SITE_NAME,
        "See what an investment in any Egyptian company would actually have "
        "been worth, including dividends, dealing costs and inflation.",
        "<h1>What if I had invested?</h1>"
        "<p>Pick a company and a date and see what really would have happened "
        "to the money — with dividends reinvested, costs deducted and the "
        "result restated in today's purchasing power.</p>"),
    "/backtest": (
        "Backtest a portfolio of Egyptian shares | " + SITE_NAME,
        "Test how a mix of Egyptian shares would have performed, with "
        "rebalancing and dealing costs, using real daily prices.",
        "<h1>Backtest a portfolio</h1>"
        "<p>Day-by-day, using real prices and real dividends, with no "
        "look-ahead.</p>"),
    "/forecast": (
        "Future scenarios for Egyptian shares | " + SITE_NAME,
        "Projections and Monte Carlo simulations for Egyptian investments — "
        "ranges and probabilities, never predictions.",
        "<h1>Future scenarios</h1>"
        "<p>What a set of stated assumptions implies, shown as a range. Not a "
        "forecast and not advice.</p>"),
    "/plan": (
        "Forecast a portfolio of Egyptian shares | " + SITE_NAME,
        "Build a portfolio today and model how it might behave over one, three "
        "or five years, using each holding's own figures.",
        "<h1>Forecast a portfolio</h1>"
        "<p>Each holding gets its own expected return, built from what the "
        "company actually reports, with risk measured from real prices.</p>"),
    "/weekly": (
        "This week on the Egyptian Exchange | " + SITE_NAME,
        "How the Egyptian Exchange moved this week: how many companies rose "
        "and fell, the largest moves among shares that actually trade, and "
        "upcoming ex-dividend dates. Not investment advice.",
        "<h1>This week on the Egyptian Exchange</h1>"
        "<p>What the market did over the past week, and how many companies "
        "took part in it. Nothing here is a recommendation, and no move is "
        "explained — for most weekly moves on this exchange, nobody honestly "
        "knows why. Subscribe by RSS at "
        "<a href=\"/feed.xml\">/feed.xml</a>; there is no mailing list.</p>"),
    "/paper": (
        "Paper portfolio — track picks against the Egyptian market | " + SITE_NAME,
        "Record what you would have bought and see how it did against the "
        "Egyptian Exchange and against inflation. No money, no account, no "
        "recommendations.",
        "<h1>Paper portfolios</h1>"
        "<p>Write down what you would have bought and let the market judge it. "
        "The comparison against the exchange as a whole is the point: making "
        "25% means nothing until you know the market made 40%.</p>"),
    "/portfolio": (
        "Analyse an Egyptian share portfolio | " + SITE_NAME,
        "Check the concentration, sector exposure and risk of a portfolio of "
        "Egyptian shares.",
        "<h1>Analyse a portfolio</h1>"
        "<p>Concentration, sector exposure and how much diversification you "
        "are actually getting.</p>"),
    "/funds": (
        "Egyptian investment funds — values, types and returns | " + SITE_NAME,
        "Every Egyptian investment fund we can cover, with the value of one "
        "unit today, what it invests in, its risk level and its returns.",
        "<h1>Egyptian investment funds</h1>"
        "<p>Money market, equity, balanced and fixed income funds available in "
        "Egypt, with current unit values and published returns. A fund spreads "
        "money across many holdings, which is usually where a first-time "
        "investor should look before picking individual shares.</p>"),
    "/learn": (
        "Learn investing — plain English, Egyptian examples | " + SITE_NAME,
        "What P/E, dividends, valuation and risk actually mean, explained "
        "plainly and using Egyptian companies as the examples.",
        "<h1>Learn investing</h1>"
        "<p>Every term used on this site, explained in plain English with "
        "Egyptian examples.</p>"),
    "/data-quality": (
        "What is wrong with our data | " + SITE_NAME,
        "Every known fault in this platform's data, counted from the database: "
        "unadjusted share splits, bad prices, currency mismatches and the "
        "companies we hold nothing for.",
        "<h1>What is wrong with our data</h1>"
        "<p>Every known fault, counted from the database each time the site is "
        "rebuilt rather than written down once. Where a fault cannot be fixed, "
        "we say what it is and which companies it touches.</p>"),
    "/methodology": (
        "How these numbers are worked out | " + SITE_NAME,
        "Every data source, every assumption and every known limitation behind "
        "the figures on this site.",
        "<h1>How this site works out its numbers</h1>"
        "<p>Sources, assumptions, and what this site refuses to do.</p>"),
    "/terms": (
        "Terms of use and disclaimer | " + SITE_NAME,
        "This is a free research and education tool, not investment advice. "
        "What that means, and what the data can and cannot be relied on for.",
        "<h1>Terms of use and disclaimer</h1>"
        "<p>This site is research and education. It is not investment advice "
        "and the operator is not licensed to give any.</p>"),
}


def sector_page(sector: str, companies: list, site_url: str):
    """A destination for "Egyptian bank stocks" and the like."""
    n = len(companies)
    title = "%s on the Egyptian Exchange — share prices and valuation | %s" % (
        sector, SITE_NAME)
    description = ("All %d companies in the %s sector listed on the Egyptian "
                   "Exchange, with share prices, valuation ratios and returns "
                   "after inflation." % (n, sector.lower()))
    rows = "".join(
        '<tr><td><a href="/stock/%s">%s</a></td><td>%s</td><td>%s</td></tr>'
        % (esc(c["ticker"]), esc(c["ticker"]), esc(c["name"]),
           esc(_money(c.get("price"))))
        for c in companies)
    body = """
<div class="prerender">
  <h1>%s on the Egyptian Exchange</h1>
  <p>The %d companies in the %s sector that this site covers, with their
     latest share prices.</p>
  <table><tbody>%s</tbody></table>
</div>""" % (esc(sector), n, esc(sector.lower()), rows)
    jsonld = [{
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "%s on the Egyptian Exchange" % sector,
        "numberOfItems": n,
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1,
             "name": "%s (%s)" % (c["name"], c["ticker"]),
             "url": site_url.rstrip("/") + "/stock/" + c["ticker"]}
            for i, c in enumerate(companies[:50])],
    }]
    return title, description, body, jsonld


def sector_slug(sector: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", sector.lower()).strip("-")


# --------------------------------------------------------------------------
def sitemap(urls: list[tuple[str, str, str]], site_url: str) -> str:
    """urls: (path, lastmod, changefreq)"""
    base = site_url.rstrip("/")
    items = "\n".join(
        "  <url><loc>%s%s</loc><lastmod>%s</lastmod>"
        "<changefreq>%s</changefreq></url>" % (base, esc(p), esc(lm), esc(cf))
        for p, lm, cf in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + items + "\n</urlset>\n")


def robots(site_url: str) -> str:
    return ("User-agent: *\n"
            "Allow: /\n"
            "\n"
            "Sitemap: %s/sitemap.xml\n" % site_url.rstrip("/"))


# --------------------------------------------------------------------------
# Arabic landing pages
#
# The language switch is client-side, which earns nothing from search: a
# crawler sees only the English it was served. These give the Arabic interface
# real, indexable pages of its own for the searches Egyptians actually type —
# "افضل اسهم مصرية", "سعر السهم في البورصة المصرية" — and link to the English
# equivalent with hreflang so neither competes with the other.
#
# Company pages are deliberately not duplicated. Their content is a company
# name we can only publish in English plus a table of numbers, so an Arabic
# copy would be the same page with a translated heading, which is exactly the
# thin duplicate a search engine is right to ignore.
AR_ROUTES = {
    "/": (
        "‏EGX‏ للأبحاث — تحليل وتقييم البورصة المصرية",
        "أبحاث مجانية وتقييم وسيناريوهات تاريخية وتعليم مالي للبورصة المصرية. "
        "بيانات حقيقية محسوبة من القوائم المالية. ليست نصيحة استثمارية.",
        "<h1>افهم البورصة المصرية قبل أن تستثمر فيها</h1>"
        "<p>أبحاث مجانية تغطي كل شركة مقيدة في البورصة المصرية: أسعار الأسهم "
        "والقوائم المالية ونطاقات التقييم والعوائد بعد التضخم ومدى سهولة تداول "
        "كل سهم. كل رقم محسوب من بيانات حقيقية.</p>"
        "<p>أسماء الشركات معروضة بالإنجليزية كما تنشرها البورصة، لأن أسماءها "
        "العربية غير متاحة من أي مصدر مجاني.</p>"),
    "/markets": (
        "كل شركات البورصة المصرية — الأسعار والقوائم المالية | ‏EGX‏ للأبحاث",
        "تصفّح كل شركة مقيدة في البورصة المصرية مع سعر السهم والقيمة السوقية "
        "والعوائد بعد التضخم ومدى سهولة التداول.",
        "<h1>كل شركات البورصة المصرية</h1>"
        "<p>كل شركة مقيدة، مع الأسعار والعوائد ووسم لجودة البيانات. الشركات "
        "ناقصة البيانات تبقى في القائمة موسومة، لا مخفية.</p>"),
    "/today": (
        "البورصة المصرية اليوم — الأسهم الصاعدة والهابطة | ‏EGX‏ للأبحاث",
        "كم شركة تداولت اليوم في البورصة المصرية، وكم صعدت وكم هبطت، وأكبر "
        "الرابحين والخاسرين، وأداء القطاعات.",
        "<h1>البورصة المصرية اليوم</h1>"
        "<p>كم شركة تداولت فعلًا، وكم منها صعد، وأين ذهبت الأموال. مؤشر السوق "
        "قد يرتفع في يوم هبطت فيه أغلب الأسهم.</p>"),
    "/screener": (
        "فلترة الأسهم المصرية — حسب القيمة والجودة والمخاطر | ‏EGX‏ للأبحاث",
        "افلتر شركات البورصة المصرية حسب مكرر الربحية وعائد التوزيعات والعائد "
        "على حقوق الملكية والنمو والديون والتقلب وسهولة التداول.",
        "<h1>فلترة الأسهم المصرية</h1>"
        "<p>افلتر البورصة كلها على المقاييس التي تهم، ومنها مدى سهولة تداول "
        "السهم فعلًا. البيانات الناقصة تستبعد الشركة ولا تُحتسب صفرًا.</p>"),
    "/scenario": (
        "ماذا لو استثمرت؟ حاسبة الأسهم المصرية | ‏EGX‏ للأبحاث",
        "اعرف كم كان سيصبح استثمارك في أي شركة مصرية، شاملًا التوزيعات "
        "وتكاليف التداول والتضخم.",
        "<h1>ماذا لو استثمرت؟</h1>"
        "<p>اختر شركة وتاريخًا واعرف ما كان سيحدث لأموالك فعلًا — بالتوزيعات "
        "وبعد خصم التكاليف، والنتيجة معروضة بقوّتها الشرائية اليوم.</p>"),
    "/funds": (
        "صناديق الاستثمار المصرية — القيم والعوائد | ‏EGX‏ للأبحاث",
        "كل صناديق الاستثمار المصرية التي نغطيها، مع قيمة الوثيقة اليوم ونوع "
        "الصندوق ودرجة مخاطره وعوائده المنشورة.",
        "<h1>صناديق الاستثمار المصرية</h1>"
        "<p>صناديق أسواق النقد والأسهم والمتوازنة والدخل الثابت المتاحة في "
        "مصر، مع قيم الوثائق والعوائد المنشورة.</p>"),
    "/learn": (
        "تعلّم الاستثمار — بلغة بسيطة وأمثلة مصرية | ‏EGX‏ للأبحاث",
        "ما معنى مكرر الربحية والتوزيعات والتقييم والمخاطر، مشروحًا بلغة بسيطة "
        "وبأمثلة من الشركات المصرية.",
        "<h1>تعلّم الاستثمار</h1>"
        "<p>كل مصطلح مستخدم في هذا الموقع، مشروحًا بلغة بسيطة وبأمثلة "
        "مصرية.</p>"),
    "/methodology": (
        "كيف تُحسب هذه الأرقام | ‏EGX‏ للأبحاث",
        "كل مصدر بيانات وكل افتراض وكل قصور معروف خلف الأرقام في هذا الموقع.",
        "<h1>كيف يحسب هذا الموقع أرقامه</h1>"
        "<p>المصادر والافتراضات، وما يرفض هذا الموقع فعله.</p>"),
    "/terms": (
        "الشروط وإخلاء المسؤولية | ‏EGX‏ للأبحاث",
        "هذه أداة أبحاث وتعليم مجانية، وليست نصيحة استثمارية. ماذا يعني ذلك، "
        "وما الذي يمكن وما لا يمكن الاعتماد عليه في البيانات.",
        "<h1>الشروط وإخلاء المسؤولية</h1>"
        "<p>هذا الموقع للأبحاث والتعليم. وهو ليس نصيحة استثمارية، والقائم عليه "
        "غير مرخّص لتقديم أي نصيحة.</p>"),
}


def alternate_links(path: str, site_url: str, lang: str) -> list[str]:
    """hreflang pairs, so the two languages do not compete with each other."""
    base = site_url.rstrip("/")
    en = base + path
    ar = base + "/ar" + ("" if path == "/" else path)
    return [
        '<link rel="alternate" hreflang="en" href="%s">' % esc(en),
        '<link rel="alternate" hreflang="ar" href="%s">' % esc(ar),
        '<link rel="alternate" hreflang="x-default" href="%s">' % esc(en),
    ]
