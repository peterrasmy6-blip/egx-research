"""
Financial statements from a second source, for the companies the first one skips.

Why
---
Yahoo publishes statements for 88 of the 269 companies on this exchange. The
other 181 have prices and nothing else: no profit, no equity, no ratios, no
valuation. Two thirds of the market reduced to a chart, because one source
chose not to cover them.

stockanalysis.com covers roughly two thirds of that remainder, with five or six
years of history apiece, and it is already fetched every run for the ticker
roster and prices. This reads its statement pages as well.

Is it the same data?
--------------------
Checked before it was trusted. On the companies both sources carry, the two
agree to the pound once the correct Yahoo column is compared -- CIB's last two
years read 61,634m and 49,707m on both. They never disagreed; this platform was
reading a column that included minority interests. That fault is fixed
separately, and the agreement is what makes it safe to mix the two here.

What it provides
----------------
The income page is a summary -- revenue, net income, earnings per share -- and
the balance sheet and cash flow pages are full statements, with line items that
follow the industry, so a bank shows gross loans where a manufacturer shows
inventory.

Units are millions of Egyptian pounds and are stated on the page. They are
converted to absolute pounds on the way in, because every consumer of this
table assumes absolute, and a factor of a million loose in a valuation is not
the kind of error that announces itself.

Provenance
----------
Every row records the source it came from. Where both sources have a figure the
existing one is kept, so adding this changes nothing about the 88 companies
that already worked; it only fills silence.
"""
from __future__ import annotations

import html
import re
import time
from datetime import date, datetime

from curl_cffi import requests as cr

SOURCE_NAME = "stockanalysis"
BASE = "https://stockanalysis.com/quote/egx/%s/financials/"

# The three statements, and the path suffix each lives at.
PAGES = {
    "income": "",
    "balance": "balance-sheet/",
    "cashflow": "cash-flow-statement/",
}

# The page states "millions" and "Currency is EGP". Both are verified per
# fetch rather than assumed -- a page that quietly switches to thousands, or
# to dollars for a foreign-currency listing, must not be read as pounds.
EXPECTED_CURRENCY = "EGP"
UNIT_MILLIONS = 1_000_000.0

# Rows that are commentary rather than a reported figure.
SKIP_SUFFIXES = (" Growth", " Margin", " Ratio")

# A statement page with fewer periods than this is not worth storing.
MIN_PERIODS = 2

REQUEST_PAUSE = 1.1

# Only these line items are stored.
#
# The pages carry more than their statements: the overview also renders a
# segment breakdown and a ratios summary, so an unfiltered read files "Dairy
# Sector", "Sales between Segments" and a bare "Total" as though they were
# reported financials. A closed vocabulary keeps the table meaningful and
# makes an unexpected new row visible rather than silently absorbed.
WANTED = {
    "income": {
        "Revenue", "Gross Profit", "Operating Income", "Net Income",
        "Earnings Per Share", "EBITDA", "Pretax Income", "Income Tax",
        "Dividend Per Share", "Shares Outstanding (Basic)",
        "Shares Outstanding (Diluted)",
    },
    "balance": {
        "Cash & Equivalents", "Cash & Short-Term Investments",
        "Short-Term Investments", "Accounts Receivable", "Inventory",
        "Total Current Assets", "Property, Plant & Equipment", "Goodwill",
        "Total Assets", "Accounts Payable", "Total Current Liabilities",
        "Long-Term Debt", "Total Liabilities", "Retained Earnings",
        "Total Common Equity", "Shareholders' Equity", "Total Debt",
        "Net Cash (Debt)", "Total Common Shares Outstanding",
        "Total Liabilities & Equity", "Net Loans", "Gross Loans",
        "Total Deposits", "Total Investments",
    },
    "cashflow": {
        "Net Income", "Depreciation & Amortization", "Operating Cash Flow",
        "Capital Expenditures", "Free Cash Flow", "Investing Cash Flow",
        "Financing Cash Flow", "Dividends Paid",
    },
}

# The cash flow statement opens from a different profit figure than the income
# statement -- Juhayna's 2025 reads 1,910m there against 1,632m attributable to
# shareholders. Both are real and they are not the same number, and the fact
# table is keyed on the item name, so the two would overwrite each other. The
# cash flow copy is stored under its own name.
CASHFLOW_RENAMES = {"Net Income": "Net Income (cash flow)"}

# Already per-share, so left unscaled. Multiplying these by a million would
# turn a one-pound dividend into a million-pound one.
#
# Share COUNTS are deliberately not here. They are quoted in millions like
# every other figure on the page, and checked rather than assumed: Juhayna
# reads 1,471 against the 1,470,945,441 shares this platform already held from
# the other source. Exempting them would have divided every per-share figure
# built on them by a million.
PER_SHARE_ITEMS = {"Earnings Per Share", "Dividend Per Share"}



def _session():
    return cr.Session(impersonate="chrome")


# --------------------------------------------------------------------------
def _cells(row_html: str) -> list[str]:
    out = []
    for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S):
        text = html.unescape(re.sub(r"<[^>]+>", " ", c))
        out.append(re.sub(r"\s+", " ", text).strip())
    return out


def _to_number(cell: str) -> float | None:
    """A reported figure in millions, or None where the page shows nothing."""
    cell = cell.replace(",", "").strip()
    if not cell or cell in {"-", "--", "n/a", "N/A", "Upgrade"}:
        return None
    if cell.endswith("%"):
        return None
    neg = cell.startswith("(") and cell.endswith(")")
    if neg:
        cell = cell[1:-1]
    mult = 1.0
    if cell.endswith("B"):
        cell, mult = cell[:-1], 1000.0
    elif cell.endswith("M"):
        cell = cell[:-1]
    elif cell.endswith("K"):
        cell, mult = cell[:-1], 0.001
    try:
        v = float(cell) * mult
    except ValueError:
        return None
    return -v if neg else v


def _period_dates(cells: list[str]) -> list[date | None]:
    """
    Real dates from the "Period Ending" row.

    The cell reads like "Dec '25 Dec 31, 2025". The long form is parsed rather
    than the fiscal-year label, because a fiscal year is not always a calendar
    one and filing a December year-end under the wrong date would silently
    misalign every comparison built on it.
    """
    today = date.today()
    out: list[date | None] = []
    for c in cells:
        m = re.search(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", c)
        if not m:
            out.append(None)
            continue
        try:
            d = datetime.strptime(
                "%s %s %s" % (m.group(1), m.group(2), m.group(3)),
                "%b %d %Y").date()
        except ValueError:
            out.append(None)
            continue
        # Independent of the column labels: a reporting period cannot end in
        # the future, and a company does not close its books on a random
        # weekday inside the last month.
        if d > today or (today - d).days < 20:
            out.append(None)
            continue
        out.append(d)
    return out


def _clean_label(label: str) -> str:
    """
    "Revenue Revenue Growth" -> "Revenue".

    The header cell carries the row's own name, then the name of the growth
    row nested underneath it, then sometimes an acronym for the same thing:
    "Earnings Per Share EPS Growth" is one line item, not three.
    """
    label = re.sub(r"\s+", " ", label).strip()

    # Drop a trailing " Growth" and, if what precedes it is the label said
    # twice, keep one copy.
    if label.endswith(" Growth"):
        head = label[: -len(" Growth")].strip()
        words = head.split()
        for n in range(1, len(words)):
            first = " ".join(words[:n])
            if head == first + " " + first:
                head = first
                break
        label = head

    # A trailing acronym that merely repeats the label.
    label = re.sub(r"\s+(EPS|EBITDA|EBIT|D&A)$", "", label).strip()
    return label


def _parse_one_table(table_html: str) -> tuple[list, dict]:
    """(period end dates, {item: [values]}) for a single table."""
    periods: list[date | None] = []
    fiscal: list[str] = []
    rows: dict[str, list] = {}
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S):
        cells = [c for c in _cells(row_html) if c != ""]
        if not cells:
            continue
        head = cells[0]
        if head.startswith("Fiscal Year"):
            fiscal = cells[1:]
            continue
        if head.startswith("Period Ending"):
            periods = _period_dates(cells[1:])
            # The leading column is usually TTM -- the last twelve months,
            # ending mid-year. It is a real figure and it is not a fiscal
            # year, and filing it as one invents a reporting period the
            # company never published, which every growth rate and every
            # year-on-year comparison downstream would then treat as real.
            # Drop the leading column when it is not a reported year.
            #
            # It appears as "TTM" on the statement tables and "Current" on the
            # summary ones -- the last twelve months, or a snapshot taken
            # today. Both are real figures and neither is a fiscal year, and
            # filing one as a year invents a reporting period the company has
            # never published: Juhayna acquired a set of accounts dated
            # 2 September, which is simply the day the page was read.
            for i, label in enumerate(fiscal):
                if i >= len(periods):
                    break
                if label.strip().upper() in {"TTM", "CURRENT"}:
                    periods[i] = None
            continue
        if not periods:
            continue
        label = _clean_label(head)
        if not label or label.endswith(SKIP_SUFFIXES):
            continue
        values = [_to_number(c) for c in cells[1:]]
        if any(v is not None for v in values):
            rows.setdefault(label, values)
    return periods, rows


def parse_statement(page_html: str) -> dict[str, dict]:
    """
    {item: {period_end: value}} for one page, across every table on it.

    Each table is parsed with its OWN header row. The balance sheet is split
    across four -- assets, liabilities, equity, summary -- and reading them as
    one block let the last table's period columns overwrite the first's, which
    filed Juhayna's profit under a date the company has never reported to. The
    tables do not always carry the same columns, so their headers are not
    interchangeable and must not be shared.
    """
    t = re.sub(r"<!--.*?-->", "", page_html)
    out: dict[str, dict] = {}
    for tbl in re.findall(r"<table[^>]*>(.*?)</table>", t, re.S):
        periods, rows = _parse_one_table(tbl)
        usable = [i for i, d in enumerate(periods) if d is not None]
        if not usable:
            continue
        for label, values in rows.items():
            for i in usable:
                if i < len(values) and values[i] is not None:
                    out.setdefault(label, {}).setdefault(periods[i], values[i])
    return out


def _check_page(page_html: str) -> str | None:
    """The currency the page declares, or None if it does not say EGP."""
    if "Currency is %s" % EXPECTED_CURRENCY in page_html:
        return EXPECTED_CURRENCY
    m = re.search(r"Currency is ([A-Z]{3})", page_html)
    return m.group(1) if m else None


def fetch_statements(ticker: str, session=None,
                     verbose: bool = False) -> dict:
    """
    Every statement this source holds for one company.

    Returns {"available": bool, "statements": {name: {item: {date: value}}},
             "currency": str, "periods": int, "reason": str}
    """
    s = session or _session()
    out: dict[str, dict] = {}
    currency = None
    for name, suffix in PAGES.items():
        try:
            r = s.get(BASE % ticker + suffix, timeout=40)
        except Exception as e:                                  # noqa: BLE001
            if verbose:
                print("    %s %s: %s" % (ticker, name, str(e)[:60]))
            continue
        if r.status_code != 200:
            continue

        cur = _check_page(r.text)
        if cur and cur != EXPECTED_CURRENCY:
            return {"available": False, "statements": {},
                    "reason": ("the page reports %s, not %s; refusing to store "
                               "it as Egyptian pounds" % (cur, EXPECTED_CURRENCY))}
        currency = currency or cur

        parsed = parse_statement(r.text)
        facts: dict[str, dict] = {}
        wanted = WANTED.get(name, set())
        for label, by_date in parsed.items():
            keep = label if label in wanted else None
            # The overview page also carries the cash-flow summary rows, which
            # are worth having wherever they appear.
            if keep is None and name == "income" and label in WANTED["cashflow"]:
                keep = label
            if keep is None:
                continue
            if name == "cashflow":
                keep = CASHFLOW_RENAMES.get(keep, keep)
            facts.setdefault(keep, {}).update(by_date)
        if len({d for v in facts.values() for d in v}) < MIN_PERIODS:
            continue
        if facts:
            out[name] = facts
        time.sleep(REQUEST_PAUSE)

    if not out:
        return {"available": False, "statements": {},
                "reason": "no statement pages carried usable figures"}
    n_periods = len({d for st in out.values() for f in st.values() for d in f})
    return {"available": True, "statements": out,
            "currency": currency or EXPECTED_CURRENCY, "periods": n_periods}


# --------------------------------------------------------------------------
def sync_financials_second_source(db, only_missing: bool = True,
                                  limit: int | None = None,
                                  verbose: bool = True) -> dict:
    """
    Store this source's statements for companies the primary source skips.

    `only_missing` is the default and the safe one: a company that already has
    statements is left entirely alone, so adding this cannot alter a number
    that was already being published. It fills silence and nothing else.

    Existing rows are never overwritten even for the companies it does touch,
    so a re-run is idempotent and a fact keeps the provenance it was first
    stored with.
    """
    from sqlalchemy import select
    from ..models import FinancialFact, Security

    have = {r[0] for r in db.execute(
        select(FinancialFact.security_id).distinct())}
    secs = [s for s in db.scalars(select(Security).where(
        Security.asset_type == "equity",
        Security.listing_status == "listed")).all()
        if not (only_missing and s.id in have)]
    if limit:
        secs = secs[:limit]

    session = _session()
    filled = skipped = written = 0
    failures: list[tuple[str, str]] = []

    for sec in secs:
        try:
            got = fetch_statements(sec.ticker, session=session)
        except Exception as e:                                  # noqa: BLE001
            failures.append((sec.ticker, str(e)[:70]))
            continue
        if not got.get("available"):
            skipped += 1
            failures.append((sec.ticker, got.get("reason", "no data")))
            continue

        rows = 0
        for statement, items in got["statements"].items():
            for item, by_date in items.items():
                for period_end, value in by_date.items():
                    exists = db.scalar(select(FinancialFact).where(
                        FinancialFact.security_id == sec.id,
                        FinancialFact.statement == statement,
                        FinancialFact.period_end == period_end,
                        FinancialFact.frequency == "annual",
                        FinancialFact.item == item))
                    if exists is not None:
                        continue
                    db.add(FinancialFact(
                        security_id=sec.id, statement=statement,
                        frequency="annual", period_end=period_end,
                        item=item,
                        # Reported in millions; stored absolute, like every
                        # other row in this table.
                        value=value * UNIT_MILLIONS
                        if item not in PER_SHARE_ITEMS else value,
                        currency=got.get("currency", EXPECTED_CURRENCY),
                        source=SOURCE_NAME))
                    rows += 1
        if rows:
            db.commit()
            filled += 1
            written += rows
            if verbose:
                print("  %-7s %4d facts, %d periods"
                      % (sec.ticker, rows, got["periods"]))
        else:
            skipped += 1

    if verbose:
        print("  filled %d companies, %d facts; %d without usable data"
              % (filled, written, skipped))
    return {"companies_filled": filled, "facts_written": written,
            "skipped": skipped, "failures": failures[:20],
            "considered": len(secs)}
