# Data sources

Every source used by this platform, what it provides, and how its terms were
assessed. Target operating cost: **EGP 0**. No paid data is used anywhere.

## Classification scheme

| Class | Meaning |
|---|---|
| **A** | Free and suitable for a public site |
| **B** | Free but restricted in some way |
| **C** | Free for personal / non-commercial use only |
| **D** | Terms unclear |
| **E** | Paid |

---

## 1. Yahoo Finance — via the `yfinance` library

| | |
|---|---|
| **URL** | https://finance.yahoo.com — accessed through the open-source `yfinance` package |
| **Provides** | Daily OHLCV prices, split/dividend-adjusted closes, dividend history, annual and quarterly income statement, balance sheet and cash-flow statement |
| **EGX coverage** | Short EGX tickers with the `.CA` suffix (e.g. `COMI.CA`). ~10 years of daily prices and 4–5 years of statements for most liquid names |
| **Update frequency** | Daily, after market close |
| **Cost** | Free |
| **Class** | **C / D** — see the note below |
| **Role** | **Primary source** for prices, dividends and financial statements |
| **Fallback** | None currently. This is the platform's single largest dependency and its main structural risk |

**Terms assessment — read this before making the site public.**

Yahoo does not publish a general-purpose free API for redistribution. `yfinance`
is an independent open-source project that reads Yahoo's public web endpoints;
it is not endorsed by Yahoo. Yahoo's terms of service restrict redistribution of
their data, and their API terms are aimed at personal, non-commercial use.

What this means in practice:

- Using this data for **personal research and analysis** is the normal, widely
  practised use of `yfinance` and is what this project does today.
- **Publicly redistributing** the raw data as a commercial service would be a
  different matter and is not covered by any licence we hold.
- This platform is therefore positioned as free, non-commercial research and
  education software. It does not sell data, does not sell access, and does not
  offer bulk data download.

**This is a genuine limitation, not a solved problem.** If the platform were
ever to become commercial, this source would need to be replaced with a licensed
feed. That is a legal question, and it should be checked with someone qualified
before any commercial launch. It is documented here rather than glossed over.

**Reliability note.** Yahoo throttles bursty clients. The ingestion layer uses a
1.5-second delay between requests and exponential-backoff retries. This was not
theoretical — an early unthrottled run was rate-limited and returned "no data"
for every single company. Because a throttle looks identical to genuine absence,
the loader distinguishes the two explicitly; without that, real companies would
have been silently dropped from the universe.

---

## 2. stockanalysis.com — EGX listed-company index

| | |
|---|---|
| **URL** | https://stockanalysis.com/list/egyptian-stock-exchange/ |
| **Provides** | The list of EGX short ticker codes with English company names (224 found) |
| **Why needed** | Yahoo's search indexes Egyptian listings by **ISIN-form** symbols (`EGS60121C018.CA`), which return only a current price — no history, no statements. The **short** codes (`COMI.CA`) carry the full data but are not discoverable through any Yahoo search endpoint. This page is the only free source found that publishes the short codes |
| **Update frequency** | Daily |
| **Cost** | Free |
| **Class** | **B** — free to access; used to build a ticker index only |
| **Role** | Universe discovery — company identity, not financial data |
| **Fallback** | Cached copy on disk (`data/universe_cache.json`). If the page becomes unavailable or its layout changes, the loader **refuses to shrink the universe** and falls back to the cache, so companies never silently disappear |

Only ticker codes and company names are read. No prices, ratios or financial
figures are taken from this source.

---

## 3. Yahoo lookup endpoint — Egyptian ISIN prefix

| | |
|---|---|
| **URL** | `https://query1.finance.yahoo.com/v1/finance/lookup?query=EGS...` |
| **Provides** | ~254 EGX securities by ISIN (all Egyptian ISINs begin `EGS`), with names |
| **Role** | **Independent cross-check** of the company roster, plus ISIN codes |
| **Class** | **C / D**, same assessment as source 1 |
| **Fallback** | Optional — the platform works without it |

This is the platform's answer to the cross-validation requirement: the listed
roster is confirmed against a second, independent source. It cannot yet be
extended to prices and fundamentals, because no second free source carries EGX
financial history.

---

## Sources investigated and rejected

| Source | Why not used |
|---|---|
| **EGX official site** (egx.com.eg) | Publishes indices and constituents as ASP.NET web pages with no public API and no machine-readable export. Scraping it would be fragile and its terms are unclear. Investigated; no usable free automated feed found |
| **EODHD** | Has good EGX coverage including fundamentals — but it is a **paid** subscription. Class E. Rejected under the zero-cost requirement |
| **Twelve Data** | Covers EGX (exchange code XCAI). Free tier is limited to 8 requests/minute and 800/day, which cannot refresh 224 companies daily, and fundamentals are on paid plans. Class E in practice |
| **ICE / Refinitiv / Bloomberg / FactSet / Capital IQ** | Paid enterprise feeds. Class E. Rejected |
| **investing.com / TradingView** | Both explicitly prohibit automated scraping in their terms. Class B/C, rejected on terms rather than on capability |
| **Kaggle EGX dataset** | A static historical snapshot, not a live feed. Unsuitable for a site showing current prices |

---

## Gaps with no free solution found

These are documented rather than filled with invented data.

### EGX index history (EGX30, EGX70, EGX100)

Yahoo serves the **current** EGX30 level under `^CASE30` but rejects historical
range requests for it (`Period 'max' is invalid, must be one of: 1d, 5d`). No
free alternative providing EGX index history was located.

**Decision: index history is not shown.** It would be possible to reconstruct a
synthetic index from constituent prices — but without the official constituent
list, official weights, and the historical membership at each past date, the
result would be a fabricated series wearing an official name. That is exactly
the kind of plausible-but-false number this platform exists to avoid.

### Egyptian investment funds

No free source was found publishing NAV history for Egyptian mutual funds, money
market funds, or gold funds in machine-readable form. Fund data is therefore
absent. The database schema supports an `asset_type` of `fund`, so the section
can be added if a legitimate free source appears.

### Arabic company names

No free machine-readable source located. Search works on English name, ticker
and sector. The `name_ar` column exists and is populated as `NULL` — honestly
empty rather than filled with transliteration guesses.

---

## Provenance stored with every figure

| Stored on | Fields |
|---|---|
| Every price row | source, currency |
| Every dividend | source, currency |
| Every statement figure | source, currency, reporting period, frequency, capture timestamp |
| Every company | source, source URL, ISIN, last refresh time, measured data-quality status |
| Every ingestion attempt | job, target, status, rows written, error message, timestamps (`ingest_runs` table) |

The `ingest_runs` table is what makes a failure visible instead of silent: if a
figure on the site looks stale, that table says exactly which job failed, when,
and why.
