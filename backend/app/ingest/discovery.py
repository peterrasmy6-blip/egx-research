"""
Discovery of the EGX listed universe.

The company list is NOT hard-coded. It is fetched from public sources at run
time, so new listings, delistings and renames flow through automatically.

Sources, in priority order:

  1. stockanalysis.com EGX listing page  - short EGX ticker codes + English
     names. This is the only free source found that publishes the short codes
     ("COMI", "SWDY") which are also the symbols carrying full history on
     Yahoo. Free to access; used here to build a ticker index, not to
     redistribute their data.
  2. Yahoo lookup by Egyptian ISIN prefix ("EGS") - independent cross-check of
     the roster, and a source of names for anything source 1 misses. ISIN-form
     symbols resolve to a current price only, so they are used for
     verification and naming, never as the price/statement source.

A ticker that either source knows about is a *candidate*. It is then filtered
against the reference stock universe in `reference_universe.py`, because the
raw merge of the two rosters is noticeably dirty: it carries tickers renamed
years ago, companies that have left the exchange, and non-ordinary instruments
such as rights issues and preferred shares. See that module for the rules.

Coverage is then measured per company by `sync_universe`, which records what
data actually exists rather than assuming.
"""
from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

from curl_cffi import requests as cr

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

SA_URL = "https://stockanalysis.com/list/egyptian-stock-exchange/"
AM_URL = ("https://www.african-markets.com/en/stock-markets/egx/"
          "listed-companies")
YAHOO_LOOKUP = "https://query1.finance.yahoo.com/v1/finance/lookup"

# Sector labels are curated: no free source classifies EGX listings reliably,
# and an unclassified company is better than a wrongly classified one.
SECTOR_KEYWORDS = [
    ("Banks", ["bank", "banque", "banking"]),
    ("Financial Services", ["financial", "finance", "investment", "capital",
                            "holding for financial", "leasing", "insurance",
                            "securities", "brokerage"]),
    ("Real Estate", ["real estate", "housing", "development", "developments",
                     "properties", "urban", "resort", "land", "city"]),
    ("Construction & Materials", ["cement", "construction", "contracting",
                                  "building", "ceramic", "refractor", "marble"]),
    ("Chemicals", ["fertilizer", "chemical", "petrochemical", "pesticide",
                   "polypropylene", "paints", "gas"]),
    ("Metals & Mining", ["steel", "iron", "aluminum", "aluminium", "copper",
                         "metal", "mining", "ferro"]),
    ("Food & Beverage", ["food", "dairy", "sugar", "juhayna", "poultry",
                         "agricultur", "mills", "oils", "beverage", "edita",
                         "meat", "starch", "bakeries"]),
    ("Healthcare", ["pharma", "medical", "hospital", "health", "clinic",
                    "drug", "care"]),
    ("Technology", ["technolog", "digitize", "software", "electronic",
                    "e-finance", "fintech", "information"]),
    ("Telecommunications", ["telecom", "communication", "mobile"]),
    ("Transport & Logistics", ["transport", "shipping", "logistic", "port",
                               "maritime", "navigation", "canal"]),
    ("Tourism & Leisure", ["tourism", "hotel", "touristic", "entertainment"]),
    ("Textiles", ["weav", "textile", "spinning", "cotton", "garment", "wool"]),
    ("Energy & Utilities", ["petroleum", "energy", "electric", "power",
                            "solar", "oil", "drilling"]),
    ("Industrials", ["industr", "engineering", "cable", "glass", "paper",
                     "packaging", "plastic", "manufactur", "auto", "vehicle",
                     "tyre", "pumps"]),
    ("Media", ["media", "publishing", "advertis", "printing"]),
    ("Education", ["education", "school", "university", "academy"]),
    ("Consumer & Retail", ["trade", "trading", "commercial", "retail",
                           "market", "consumer", "distribution"]),
]


# Hand-checked sectors for the most liquid names. Keyword matching gets some
# of these wrong (El Sewedy Electric is a cable manufacturer, not a utility),
# so verified labels win over the heuristic.
CURATED_SECTORS = {
    "COMI": "Banks", "HRHO": "Financial Services", "CIEB": "Banks",
    "ADIB": "Banks", "SAUD": "Banks", "EXPA": "Banks", "FAIT": "Banks",
    "HDBK": "Banks", "QNBE": "Banks", "CANA": "Banks", "EFIH": "Technology",
    "BINV": "Financial Services", "AMER": "Real Estate", "TMGH": "Real Estate",
    "EMFD": "Real Estate", "PHDC": "Real Estate", "MNHD": "Real Estate",
    "HELI": "Real Estate", "OCDI": "Real Estate", "ORHD": "Real Estate",
    "ARCC": "Construction & Materials", "ORAS": "Construction & Materials",
    "SWDY": "Industrials", "ABUK": "Chemicals", "MFPC": "Chemicals",
    "SKPC": "Chemicals", "EGAL": "Metals & Mining", "ESRS": "Metals & Mining",
    "IRON": "Metals & Mining", "KZPC": "Chemicals", "PRMH": "Financial Services",
    "JUFO": "Food & Beverage", "EAST": "Food & Beverage",
    "EFID": "Food & Beverage", "CCAP": "Financial Services",
    "ISPH": "Healthcare", "CLHO": "Healthcare", "RMDA": "Healthcare",
    "OLFI": "Food & Beverage", "DOMT": "Food & Beverage", "SPMD": "Healthcare",
    "FWRY": "Technology", "ETEL": "Telecommunications",
    "MTIE": "Consumer & Retail", "ATQA": "Metals & Mining",
    "GBCO": "Consumer & Retail", "EKHO": "Financial Services",
    "EKHOA": "Financial Services", "ORWE": "Textiles",
    "SUGR": "Food & Beverage", "ELEC": "Industrials",
}


def classify_sector(name: str) -> str | None:
    """Best-effort sector from the company name. None when nothing matches."""
    n = (name or "").lower()
    for sector, keys in SECTOR_KEYWORDS:
        for k in keys:
            if k in n:
                return sector
    return None


def _session():
    return cr.Session(impersonate="chrome")


# --------------------------------------------------------------------------
def fetch_ticker_index(verbose: bool = True) -> dict[str, dict]:
    """
    Short EGX ticker -> {name, source_url}.

    Raises on failure rather than returning a partial roster silently: a short
    list here would look like companies had been delisted.
    """
    s = _session()
    r = s.get(SA_URL, timeout=40)
    r.raise_for_status()
    rows = re.findall(
        r'href="/quote/egx/([A-Z0-9]{2,8})/">[A-Z0-9]{2,8}</a>.*?'
        r'<td class="slw[^"]*">([^<]{2,140})</td>',
        r.text, re.S)
    out: dict[str, dict] = {}
    for tk, nm in rows:
        out.setdefault(tk, {
            "name": html.unescape(nm).strip(),
            "source_url": "https://stockanalysis.com/quote/egx/%s/" % tk,
        })
    if len(out) < 50:
        raise RuntimeError(
            "EGX ticker index returned only %d rows; the page layout has "
            "probably changed. Refusing to shrink the universe." % len(out))
    if verbose:
        print("  ticker index: %d EGX tickers" % len(out))
    return out


def fetch_isin_roster(verbose: bool = True) -> dict[str, dict]:
    """Yahoo lookup across Egyptian ISIN prefixes -> {isin_symbol: {...}}."""
    import string
    s = _session()
    found: dict[str, dict] = {}
    queries = ["EGS"] + ["EGS" + c for c in string.digits + string.ascii_uppercase]
    for q in queries:
        start = 0
        while start < 300:
            try:
                r = s.get(YAHOO_LOOKUP, params={
                    "query": q, "type": "equity", "count": 100, "start": start,
                    "formatted": "false", "lang": "en-US", "region": "EG"},
                    timeout=25)
                res = r.json().get("finance", {}).get("result", [])
                if not res:
                    break
                docs = res[0].get("documents", []) or []
                total = res[0].get("count", 0)
                if not docs:
                    break
                for d in docs:
                    sym = d.get("symbol", "")
                    if sym.endswith(".CA"):
                        found.setdefault(sym, {
                            "name": (d.get("shortName") or "").strip(),
                            "isin": sym.replace(".CA", ""),
                        })
                start += 100
                if start >= total:
                    break
                time.sleep(0.3)
            except Exception:
                break
        time.sleep(0.15)
    if verbose:
        print("  ISIN roster: %d symbols" % len(found))
    return found


def fetch_african_markets(verbose: bool = True) -> dict[str, dict]:
    """
    A second, independent roster of EGX tickers.

    Added because the first source lists 224 companies while the exchange has
    appreciably more -- this one lists 285, and the union of the two comes to
    318. Relying on a single roster was quietly under-representing the market
    by roughly a fifth.

    It also publishes a sector for each company, which is used where the
    curated list has no entry.
    """
    s = _session()
    r = s.get(AM_URL, timeout=45)
    r.raise_for_status()
    out: dict[str, dict] = {}
    for code, name, sector in re.findall(
            r"code=([A-Z0-9]{2,8})'[^>]*>([^<]{2,120})</a>\s*</td>\s*"
            r"<td[^>]*>([^<]*)</td>", r.text):
        sector = html.unescape(sector).strip()
        # The sector column occasionally holds a stray number.
        if re.fullmatch(r"[\d.,%+-]+", sector or ""):
            sector = ""
        out[code] = {"name": html.unescape(name).strip(),
                     "sector_hint": sector or None,
                     "source_url": "https://www.african-markets.com/en/"
                                   "stock-markets/egx/listed-companies/company"
                                   "?code=%s" % code}
    if len(out) < 100:
        raise RuntimeError(
            "African-markets roster returned only %d rows; layout probably "
            "changed." % len(out))
    if verbose:
        print("  african-markets roster: %d tickers" % len(out))
    return out


# Map the second source's broad sector labels onto ours.
AM_SECTOR_MAP = {
    "Financials": "Financial Services",
    "Basic Materials": "Chemicals",
    "Industrials": "Industrials",
    "Consumer Goods": "Consumer & Retail",
    "Consumer Services": "Consumer & Retail",
    "Health Care": "Healthcare",
    "Technology": "Technology",
    "Telecommunications": "Telecommunications",
    "Oil & Gas": "Energy & Utilities",
    "Utilities": "Energy & Utilities",
    "Real Estate": "Real Estate",
}


def apply_reference(index: dict[str, dict], verbose: bool = True) -> dict[str, dict]:
    """
    Reduce the raw two-roster merge to the reference stock universe.

    Three things happen here, in order:

      * a stale ticker is folded into the current one it renamed to, so its
        history is not stranded under a name nobody searches for;
      * anything the reference list classifies as a non-ordinary instrument
        (rights, ETF, certificate, fund, second share class) is dropped from
        the *stock* universe, with the reason kept for the coverage report;
      * anything left that the reference list does not recognise is dropped.

    The reference set is the floor, not the ceiling: a company in the reference
    list that neither roster mentioned is still added, because the roster
    missing it is a roster problem.
    """
    from .reference_universe import (EXCLUDED, KEEP_EXTRA,
                                     NOTE_NOT_ON_REFERENCE, ORDINARY, RENAMES)

    out: dict[str, dict] = {}
    renamed = dropped_instrument = dropped_unknown = 0

    for tk, rec in index.items():
        target = RENAMES.get(tk, tk)
        if target != tk:
            renamed += 1

        if target in EXCLUDED:
            dropped_instrument += 1
            continue
        if target not in ORDINARY:
            dropped_unknown += 1
            continue

        # A rename collapses two rows onto one; keep the richer record.
        prev = out.get(target)
        if prev is None or rec.get("sources", 1) > prev.get("sources", 1):
            out[target] = dict(rec)
        out[target]["sources"] = max(rec.get("sources", 1),
                                     (prev or {}).get("sources", 1))

    # Reference entries neither roster produced.
    restored = 0
    for tk, name in ORDINARY.items():
        if tk not in out:
            out[tk] = {"name": name, "sources": 1,
                       "source_url": None, "sector_hint": None}
            restored += 1

    # The reference name is the authoritative one -- roster names are often
    # abbreviated, misspelt, or a former trading name.
    for tk, rec in out.items():
        rec["name"] = ORDINARY[tk]
        rec["on_reference_list"] = tk not in KEEP_EXTRA
        if tk in KEEP_EXTRA:
            rec["data_note"] = NOTE_NOT_ON_REFERENCE

    if verbose:
        print("  reference filter: %d ordinary stocks "
              "(%d renamed, %d non-ordinary instruments removed, "
              "%d unrecognised removed, %d restored from reference)"
              % (len(out), renamed, dropped_instrument, dropped_unknown,
                 restored))
    return out


def build_universe(verbose: bool = True, use_cache: bool = False) -> dict[str, dict]:
    """
    Merge both sources into the candidate universe.

    Cached to disk so a later source outage cannot wipe the roster.
    """
    cache = DATA_DIR / "universe_cache.json"

    if use_cache and cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if verbose:
            print("  using cached universe: %d tickers" % len(data))
        # A cache written before the reference filter existed would otherwise
        # reintroduce every ghost ticker. Filtering is idempotent.
        return apply_reference(data, verbose)

    index: dict[str, dict] = {}
    errors: list[str] = []

    # Two independent rosters, merged. Either alone under-represents the
    # exchange; together they cover it.
    try:
        for tk, rec in fetch_ticker_index(verbose).items():
            rec["sources"] = 1
            index[tk] = rec
    except Exception as e:
        errors.append("stockanalysis: %s" % e)

    try:
        for tk, rec in fetch_african_markets(verbose).items():
            if tk in index:
                # Listed by both rosters -- treat the listing as confirmed.
                index[tk].setdefault("sector_hint", rec.get("sector_hint"))
                index[tk]["sources"] = index[tk].get("sources", 1) + 1
            else:
                # Only this roster knows it. Kept, but not counted as a
                # confirmed current listing until something corroborates it.
                index[tk] = {"name": rec["name"],
                             "source_url": rec["source_url"],
                             "sector_hint": rec.get("sector_hint"),
                             "sources": 1}
    except Exception as e:
        errors.append("african-markets: %s" % e)

    if not index:
        if cache.exists():
            if verbose:
                print("  both rosters failed (%s); falling back to cache"
                      % "; ".join(errors))
            return apply_reference(
                json.loads(cache.read_text(encoding="utf-8")), verbose)
        raise RuntimeError("No roster source reachable: %s" % "; ".join(errors))

    if errors and verbose:
        print("  note: %s" % "; ".join(errors))

    # Names from the ISIN roster fill gaps and act as a cross-check.
    try:
        isin = fetch_isin_roster(verbose)
    except Exception:
        isin = {}

    isin_names = {}
    for sym, d in isin.items():
        nm = d["name"].lower()
        if nm:
            isin_names[nm] = d

    index = apply_reference(index, verbose)

    for tk, rec in index.items():
        rec["yahoo_symbol"] = tk + ".CA"
        hint = rec.get("sector_hint")
        rec["sector"] = (CURATED_SECTORS.get(tk)
                         or classify_sector(rec["name"])
                         or AM_SECTOR_MAP.get(hint or ""))
        rec["sector_verified"] = tk in CURATED_SECTORS
        low = rec["name"].lower()
        for nm, d in isin_names.items():
            if nm and (nm[:22] in low or low[:22] in nm):
                rec["isin"] = d["isin"]
                break

    DATA_DIR.mkdir(exist_ok=True)
    cache.write_text(json.dumps(index, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    if verbose:
        matched = sum(1 for r in index.values() if r.get("isin"))
        classified = sum(1 for r in index.values() if r.get("sector"))
        print("  universe: %d tickers | %d ISIN-matched | %d sector-classified"
              % (len(index), matched, classified))
    return index
