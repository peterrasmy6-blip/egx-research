# Project status

Last updated: 2026-08-28

---

## COMPLETED

### Data foundation
- **Full EGX universe discovered automatically** — 227 securities (225 listed,
  2 renamed/delisted), not a hard-coded list. Fetched at run time from public sources, so new listings, delistings and
  renames flow through by themselves.
- Companies with poor data are **kept and labelled**, never deleted.
- Delisted/renamed companies are marked, not removed (their price history stays valid).
- ~10 years of daily prices, dividends, and annual + quarterly financial statements.
- Provenance stored on every figure: source, currency, reporting period, capture time.
- Every ingestion attempt logged to `ingest_runs`, so failures are visible not silent.
- Retry with exponential backoff; a rate-limit is never mistaken for "no data".
- Failed refresh never destroys existing good data.
- SQLite in WAL mode, so the site stays up while data loads behind it.

### Price integrity (added after finding a real bug)
- **Detects unadjusted corporate actions.** The homepage was briefly reporting
  FERC at +805% — its price jumps 9.22 → 97.57 overnight, which EGX daily price
  limits make impossible as real trading. It was an unapplied 6-for-1 consolidation.
- **31 of 227 companies** carry such breaks. Returns spanning them are now
  suppressed and explained, not published.
- Correctly distinguishes fake jumps from genuine extreme moves: BIOC's +762%
  is a real run of consecutive +20% limit-up days and is preserved.

### Currency integrity (a second real bug)
- Four securities are share classes quoted in **US dollars** while their
  accounts are filed in Egyptian pounds. FAITA showed a P/E of 0.15 and
  "undervalued by 2,934%".
- Detected by comparing price against book value per share. Per-share figures
  and fair values are withheld for them.

### Analysis engines (all deterministic — no AI involved in any number)
- Ratios computed from raw statements: P/E, P/B, P/S, EV/EBITDA, ROE, ROA, ROIC,
  margins, growth, debt/equity, market cap, enterprise value.
- Risk: volatility, max drawdown, recovery time, Sharpe, Sortino — all using an
  **Egyptian** risk-free rate, not a developed-market one.
- **Valuation engine** with method selection by business type: residual income
  and DDM for banks, cash-flow models for operating companies, asset-based for
  property. Bear/base/bull ranges, never a single number. Confidence falls when
  methods disagree.
- **Historical scenarios**: lump sum and monthly, with real dividends and costs.
- **Backtesting**: multi-asset, day-by-day, with rebalancing, costs, dividend
  reinvestment, and no look-ahead.
- **Forecasting**: three-scenario projections and Monte Carlo with percentiles,
  probability of loss, and stated limitations.
- **Screener** across 21 measures; missing data excludes and is counted, never zeroed.
- **Comparison** of up to 6 companies.
- **Portfolio analysis**: concentration, sector exposure, effective holdings.

### Website
- Nine sections: Home, Markets, Screener, Compare, What If, Backtest, Future
  Scenarios, Portfolio, Learn.
- Search by ticker, company name, partial name or sector — no ticker knowledge needed.
- Mobile-first responsive layout.
- Data-quality badge on every company; stale-data banner sitewide.
- No login required for anything.

### Education
- 24-term plain-English dictionary, 6 guides, 10-question risk-awareness
  questionnaire that describes tendencies and **never** issues an allocation.

### Static build (no server, cannot start charging)
- Exported to `site/` — 242 files, 14 MB. Shared files are only 256 KB, so the
  page loads instantly and company data loads on demand.
- The Python engine was ported to JavaScript so every calculation runs in the
  visitor's browser.
- **267 parity assertions** check the browser engine against the Python engine.
  They caught two genuine defects: a rounding mismatch (the feed returns float32
  noise like 139.27999877929688 for a price of 139.28), and a risk-free rate
  that had drifted to 22% in `portfolio.py` while `valuation.py` used a sourced
  20.5% — shifting every Sharpe ratio by 0.05.
- They also caught a name collision that silently broke the screener: `runScreen`
  was defined in both the data layer and the view layer.

### Testing
- **155 Python tests** (41 + 114) — correct answers *and* correct refusals.
- **267 browser parity assertions** — the browser must match Python exactly.
- **24 end-to-end checks** against the built static site.
- `RUN_TESTS.bat` runs all three.

### Documentation
- `START_HERE.md`, `DEPLOY.md`, `PROJECT_COST.md`, `DATA_SOURCES.md`,
  `EGX_COVERAGE_REPORT.md` (auto-generated), `docs/ARCHITECTURE.md`.

---

## IN PROGRESS

Nothing. The data load is complete and the pipeline has run end to end.

---

## NEEDS PETER

**One thing only: uploading the `site` folder to a free host.** I cannot create
an account in your name.

The site is now **static** — a folder of ordinary files with no server, so
nothing can ever start charging. `DEPLOY.md` gives three free routes; the
quickest is dragging the folder onto https://app.netlify.com/drop.

---

## KNOWN LIMITATIONS

Documented honestly rather than papered over. Each was investigated.

| Limitation | Why | What we did |
|---|---|---|
| **EGX index history unavailable** | Yahoo serves the current EGX30 level but refuses historical ranges. No free source found with usable history | Index history is **not shown**. Reconstructing one without official historical constituents and weights would be a fabricated series wearing an official name |
| **No Egyptian fund data** | No free source publishes NAV history in machine-readable form | Funds absent. Schema supports them if a source appears |
| **Single price source** | Only one free source carries full EGX history | The company *roster* is cross-checked against a second source; prices cannot yet be |
| **No Arabic names** | No free machine-readable source found | Column exists, left honestly empty. Search works on English name, ticker, sector |
| **Sector labels partly heuristic** | No free source classifies EGX listings | ~50 liquid names hand-checked; rest by keyword; unmatched left blank |
| **Inflation is an assumption** | Not measured data | Adjustable, defaults to 20%/yr, labelled as an assumption everywhere shown |
| **~29 companies have no price history** | Not carried by the free source | Kept in the database, labelled "Unavailable" |
| **Yahoo terms** | Not licensed for commercial redistribution | Positioned as free non-commercial research/education. Would need a licensed feed before any commercial launch — see `DATA_SOURCES.md` |

---

## DELIBERATELY NOT BUILT

- **AI chat analyst.** Would require a paid API (breaking the EGP 0 rule) and
  would risk fabricating figures. The platform explains itself through the
  deterministic engine instead. Reasoning in `PROJECT_COST.md`.
- **Personalised recommendations.** Out of scope by design. The platform gives
  information and tools; the user decides.

---

## FINAL DATA STATE

| | |
|---|---|
| Securities discovered | 227 |
| With price history | 198 (87%) |
| With financial statements | 90 (40%) |
| With a fair-value estimate | 78 |
| Daily price records | 458,848 |
| Statement figures | 92,465 |
| Dividend payments | 1,815 |

The 108 price-only companies were verified individually: the free source
genuinely publishes no accounts for them. Not a fetch failure.

---

## NEXT TASK

1. **Deploy** — blocked only on the hosting account (see `DEPLOY.md`).
2. Test the live site once it is up.
3. Then, in priority order:
   - Arabic company names, if a free source can be found
   - Cross-source price validation, if a second free EGX feed appears
   - Funds, if NAV data becomes available
