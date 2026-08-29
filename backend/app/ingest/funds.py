"""
Egyptian investment fund discovery.

Funds were the largest gap in the platform: the equity side covered the whole
exchange while funds were absent entirely.

Why they are harder than shares
-------------------------------
Egyptian mutual funds are not exchange-traded in the way shares are, so none of
the share-price sources carry them. The official EGX funds pages sit behind an
F5/Shape bot-protection layer that returns a JavaScript challenge instead of
data, and defeating that is not something this project will do.

What is used instead: egxbot.com publishes a public funds table with each
fund's NAV, category, risk band and trailing returns. It is read for fund
identity and current NAV only.

The honest limitation
---------------------
This source publishes a *current* NAV and a few trailing return figures. It
does **not** publish a NAV history. So funds get a profile page and current
figures, but cannot be put through the backtester, the what-if calculator or
Monte Carlo, all of which need a price series. The platform says so on the page
rather than silently offering tools that would produce nothing.
"""
from __future__ import annotations

import html
import re

from curl_cffi import requests as cr

SOURCE_URL = "https://egxbot.com/en/funds"
SOURCE_NAME = "egxbot"


def _session():
    return cr.Session(impersonate="chrome")


def _text(fragment: str) -> str:
    """Strip tags and normalise whitespace inside a table cell."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _num(s: str):
    """Pull a number out of a display string like '1,967.94 EGP' or '13.54%'."""
    if not s:
        return None
    m = re.search(r"-?[\d,]+\.?\d*", s.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def fetch_funds(verbose: bool = True) -> list[dict]:
    """
    Every Egyptian fund the source lists, with its current NAV.

    Raises rather than returning a short list, so a source outage can never be
    mistaken for "the funds were delisted".
    """
    s = _session()
    r = s.get(SOURCE_URL, timeout=45)
    r.raise_for_status()
    # The page is UTF-8 but does not always say so.
    text = r.content.decode("utf-8", errors="replace")

    out: list[dict] = []
    for block in re.findall(r"<tr>(.*?)</tr>", text, re.S):
        m = re.search(r'<a class="md-name" href="(/en/funds/([^"]+))">(.*?)</a>',
                      block, re.S)
        if not m:
            continue
        slug = m.group(2)
        name = _text(m.group(3))

        cells = {}
        for label, body in re.findall(r'data-label="([^"]+)"[^>]*>(.*?)</td>',
                                      block, re.S):
            cells[label.strip()] = _text(body)

        out.append({
            "slug": slug,
            "name": name,
            "source_url": "https://egxbot.com" + m.group(1),
            "nav": _num(cells.get("NAV price")),
            "nav_display": cells.get("NAV price"),
            "ytd_pct": _num(cells.get("YTD")),
            "return_1y_pct": _num(cells.get("1Y")),
            "since_inception_pct": _num(cells.get("Since inception")),
            "category": cells.get("Category") or None,
            "fund_type": cells.get("Type") or None,
            "risk": cells.get("Risk") or None,
        })

    if len(out) < 10:
        raise RuntimeError(
            "Fund source returned only %d rows; the page layout has probably "
            "changed. Refusing to shrink the fund list." % len(out))

    if verbose:
        cats = {}
        for f in out:
            cats[f["category"] or "Unclassified"] = cats.get(f["category"] or "Unclassified", 0) + 1
        print("  funds found: %d" % len(out))
        for k, v in sorted(cats.items(), key=lambda x: -x[1]):
            print("     %-22s %d" % (k, v))
    return out


def ticker_for(slug: str) -> str:
    """
    A stable identifier for a fund.

    Funds have no exchange ticker, so the source's slug is turned into one.
    Prefixed with FUND- so it can never collide with a real EGX ticker.

    The separator is a hyphen, not a colon: a colon is illegal in Windows
    filenames (it opens an NTFS alternate data stream, so 39 of 40 fund files
    silently vanished on the first attempt) and needs escaping in URLs.
    """
    clean = re.sub(r"[^A-Za-z0-9]+", "-", slug).strip("-").upper()
    return ("FUND-" + clean)[:60]
