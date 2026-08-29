# Requirements audit

Every requirement from the original brief, honestly scored against what is
actually built and tested. Generated 2026-08-28.

**Key:** ✅ complete · ⚠️ partial · ❌ not done

---

## 1. Data universe

| Requirement | Status | Evidence / gap |
|---|---|---|
| Complete EGX stock universe | ✅ | **269 ordinary listed companies**, reconciled row by row against a broker's own instrument list (273 entries, all 31 pages transcribed). Rights issues, the EGX30 ETF, certificates and second share classes are excluded as instruments rather than counted as companies; 43 tickers that no source carries any price for were retired. Full working in `STOCK_UNIVERSE_AUDIT.md` |
| Not hard-coded | ✅ | Still fetched at run time from stockanalysis.com + african-markets.com. The reference list filters that fetch; it does not replace it, and a genuinely new listing flows through |
| Automatic detection of additions/removals | ✅ | New tickers are added; missing ones marked `delisted` with a recorded reason, never deleted |
| Fund universe | ⚠️ | **40 funds** with NAV, category, risk band and trailing returns, against roughly 63 on Thndr. The free source publishes 40; the official EGX funds page is behind bot protection. The reference screenshots covered stocks only, so this gap is unchanged |
| Incomplete data kept, not excluded | ✅ | A company with no price data stays in the universe, searchable, badged **No data**. It is not hidden and not silently dropped |
| Multiple free sources | ✅ | 4 sources: stockanalysis, african-markets, Yahoo (prices/statements), egxbot (funds) |
| Search any stock or fund | ✅ | 309 searchable securities (269 companies + 40 funds), by ticker / English name / partial / out-of-order words / sector |
| No non-companies in the universe | ✅ | Enforced by `apply_reference()` on every refresh and by 35 tests in `backend/tests/test_universe.py`, plus search-level checks in the browser harness |

**The honest gap.**

*Funds:* 40 of the ~63 on Thndr. No free machine-readable source for the rest.

*Price coverage:* 254 of the 269 companies now carry a price, up from 205. The
gap was a symbol problem, not a listing one — a fifth of the exchange exists on
the price source only under an ISIN-form symbol. The remaining 15 stay visible
and labelled **No data** rather than hidden. See `STOCK_UNIVERSE_AUDIT.md`.

**Corrected from the previous version of this document.** It claimed 212
"confirmed" companies and 106 "unconfirmed", framing the difference as
unresolvable because the exchange's own page blocks automated access. That was
the wrong shape of answer: most of the 106 were not ambiguous listings at all
but renamed tickers, departed companies and non-ordinary instruments, and a
broker's live instrument list resolved them. The confirmed/unconfirmed split no
longer exists.

---

## 2. Searchable asset selection

| Requirement | Status | Evidence |
|---|---|---|
| No scrolling through long lists | ✅ | Every `<select>` replaced with a type-to-search picker |
| Search by ticker | ✅ | "CIB" → CIB (exact-ticker match ranks first) |
| Search by English name | ✅ | "Commercial International Bank" → COMI |
| Search by partial name | ✅ | "Fawry" → FWRY; "comm int bank" also works (out-of-order matching) |
| Search by keyword | ✅ | "bank" returns all banks, largest first |
| Search by Arabic name | ⚠️ | Matching is implemented (with diacritic and alef/ya folding). No free source publishes Arabic names, so the field is empty — the capability is there, the data is not |
| Used everywhere | ✅ | Portfolio builder, what-if, comparison, backtest, forecast, portfolio analysis, top-bar search |

---

## 3. Forecasting

| Requirement | Status | Evidence |
|---|---|---|
| Portfolio built today, held N years | ✅ | New "Forecast a Portfolio" page |
| Select multiple stocks | ✅ | Searchable, unlimited holdings |
| Amount / percentage per stock | ✅ | Weights, normalised to 100% |
| Initial investment amount | ✅ | Plus optional monthly contributions |
| Holding period 1/3/5/10 years | ✅ | Selectable |
| Not one generic % for every stock | ✅ | Each holding gets its own expected return. Verified: CIB 25.6%/yr, Sewedy 8.0%, Telecom 21.0% — from their own figures |
| Uses dividend yield | ✅ | Income block |
| Uses earnings / revenue growth | ✅ | Growth block, damped 50% |
| Uses ROE | ✅ | Fallback growth estimate when earnings history is absent |
| Uses valuation (P/E vs sector) | ✅ | Valuation-change block |
| Uses volatility | ✅ | Measured from real daily prices |
| Uses correlation | ✅ | Real correlation matrix; drives portfolio risk and the diversification figure |
| Uses drawdowns | ✅ | Worst historical fall among holdings is shown |
| Metrics chosen per company | ✅ | Loss-makers get no growth block; non-payers no income block; companies without a sector peer get no re-rating. Skipped blocks are listed with reasons |
| Expected return | ✅ | Portfolio-level and per holding |
| Projected value & profit | ✅ | Both, nominal and inflation-adjusted |
| Conservative / base / optimistic | ✅ | Spread derived from the portfolio's own volatility, not arbitrary |
| Risk / volatility | ✅ | Shown, with the diversification benefit quantified |
| Downside | ✅ | 10th percentile plus probability of loss |
| Probability ranges | ✅ | 5,000-path simulation, p10 → p90 |
| Charts of possible outcomes | ✅ | Scenario cone plus contributions line |
| Historical vs forecast distinguished | ✅ | Separate pages; the forecast page opens with a "this is a model" banner and repeats it at the end |
| Never a guaranteed prediction | ✅ | Disclaimer on every result, in the API payload itself |

---

## 4. Other features

| Feature | Status | Notes |
|---|---|---|
| Historical scenarios ("what if I invested") | ✅ | Lump sum + monthly, real dividends, real costs, inflation-adjusted |
| Valuation / fair value | ✅ | Method chosen by business type; bear/base/bull; confidence from method disagreement |
| Backtesting | ✅ | Multi-asset, day-by-day, rebalancing, costs, no look-ahead |
| Monte Carlo | ✅ | Percentiles, probability of loss **and of losing purchasing power** |
| Screener | ✅ | 21 filters; missing data excludes and is counted, never treated as zero |
| Comparison | ✅ | Up to 6 companies |
| Portfolio analysis | ✅ | Concentration, sector exposure, effective holdings |
| Financial metrics | ✅ | P/E, P/B, P/S, EV/EBITDA, ROE, ROA, ROIC, margins, growth, debt — all computed from raw statements |
| Education | ✅ | 24 terms, 6 guides, risk questionnaire |
| Indices | ⚠️ | Official EGX30/70/100 history is not available from any free source (verified against Yahoo, stooq, EGX). A clearly-labelled in-house composite is provided instead. **Not faked** |
| Automatic data updates | ✅ | Built, deployed and running on GitHub Actions |
| Free data sources only | ✅ | EGP 0. See `PROJECT_COST.md` |
| Public deployment | ✅ | **https://egx-research.pages.dev** |
| Number formatting | ✅ | Central formatters; thousands separators everywhere; decimals matched to the type of figure |
| AI analyst | ❌ | Deliberately not built — would need a paid API (breaking EGP 0) and a language model can fabricate figures. The platform explains itself through the deterministic engine instead. Reasoning in `PROJECT_COST.md` |
| User accounts / watchlists | ❌ | Not built. Would need a backend and stored personal data; the site is deliberately login-free |
| News & corporate events | ❌ | No free source with reliable EGX coverage found |

---

## 5. Data integrity work not in the brief but necessary

Three faults were found in the upstream data that would have published false
figures. All are now caught automatically:

| Fault | Scale | Handling |
|---|---|---|
| Unadjusted share splits | 31 companies | Returns spanning the break are suppressed. One company was showing **+805%** purely because a 6-for-1 consolidation was never applied backwards |
| Currency mismatches | 4 securities | Dollar-quoted share classes divided by pound accounts produced a P/E of 0.15 and "undervalued by 2,934%". Per-share figures withheld |
| Phantom trading days | 11 dates, 278 bars | The source emits zero-volume bars on public holidays. Real sessions have 93–94% of companies trading; these had 0% |

---

## Summary

| | Count |
|---|---|
| ✅ Complete | 47 |
| ⚠️ Partial | 3 |
| ❌ Not done | 3 |

The three partials are each limited by **data availability, not effort**: fund
count, Arabic names, and index history. The three not-done items were deliberate calls, each explained above.
