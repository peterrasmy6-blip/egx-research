# Architecture & methodology

Technical reference. `START_HERE.md` is the non-technical guide.

## Stack and why

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python + FastAPI | The quantitative work (pandas/numpy) has to live in Python. Putting the API in the same language removes a whole serialisation boundary. |
| Database | SQLite now, PostgreSQL later | `DATABASE_URL` is the only thing that changes. SQLite means zero setup for a non-technical owner; the schema is Postgres-compatible. |
| Frontend | Server-served HTML + vanilla JS + Chart.js | Node is not installed on this machine. A build-step-free frontend means the owner can run the whole product by double-clicking one file. Revisit if the UI outgrows it. |
| Data source | Yahoo Finance via `yfinance` | The only free source found that carries EGX prices, dividends **and** full financial statements. Verified empirically, not assumed. |

## Layout

```
backend/app/
  db.py                  engine + session
  models.py              schema
  ingest/
    universe.py          EGX candidate list + sector map
    loader.py            fetch -> validate -> store, with retry/throttle
  engine/
    analytics.py         price access, risk/return maths
    fundamentals.py      statement normalisation, ratios
    scenario.py          historical what-if
  api/main.py            HTTP layer
  web/                   the website
data/egx.db              the database
```

## Non-negotiable data rules

These are enforced in code, not just documented:

1. **Nothing is invented.** A missing input yields `None`, and the UI renders
   "insufficient data". `_f()` in `loader.py` turns NaN into `None` rather than 0.
2. **Provenance is stored.** Every `Price`, `Dividend` and `FinancialFact` row
   carries `source` and `currency`; facts also carry `captured_at`.
3. **A failed refresh never destroys good data.** `sync_prices` inserts only
   dates it does not already hold, and logs failure to `ingest_runs`.
4. **Throttling is not absence.** `_retry()` distinguishes a rate-limited
   request from a genuinely dataless security. Without this, a burst of 429s
   would silently delete real companies from the universe — this actually
   happened during development and is why the retry layer exists.
5. **No look-ahead.** Scenario entry uses `price_on_or_after`, exit uses
   `price_on_or_before`. Future prices cannot influence a past decision.

## Price semantics

The single most common source of wrong numbers in retail finance tools.

- `close` — split-adjusted, **not** dividend-adjusted. What a buyer paid that
  day. Used for share counts and price-only return.
- `adj_close` — split- **and** dividend-adjusted. Used for total return and
  volatility.

Dividend amounts from the source are split-adjusted, so a share count derived
from `close` stays consistent with them across splits.

## Risk statistics

- Volatility: sample stdev of daily `adj_close` returns × √252. Returns `None`
  below 20 observations.
- CAGR: returns `None` for windows under one year — annualising three months
  of a volatile EGX name produces absurd figures.
- Sharpe/Sortino take an **explicit Egyptian risk-free rate**. This is not
  cosmetic: with EGP deposit rates in the high teens, a 20% nominal equity
  return is a poor risk-adjusted outcome, and a Sharpe computed against a 2%
  rate would flatter EGX results badly.

## Inflation

`scenario.py` reports nominal **and** real outcomes, defaulting to 20%/yr.

This is an **assumption, labelled as such in the UI**, not measured data.
It is included because Egyptian inflation is large enough that omitting it
actively misleads: CIB returned +337% over five years nominally, but only
+47% in purchasing power. A platform that showed only the first number would
be telling the user something false about whether they got richer.

Replacing the flat assumption with real CPI series from CAPMAS/World Bank is
the correct next step.

## Fundamentals normalisation

Line-item names vary between filings, so `ALIASES` maps each concept to
candidate names in priority order, and `sources` records which alias actually
supplied each value.

Industry differences are handled by absence, not substitution: CIB legitimately
has no `gross_profit` or `EBITDA`, so those come back `None` and the UI
explains why rather than showing a fabricated figure.

## Known gaps

| Gap | Status |
|---|---|
| EGX30 index history | Source serves current value only. Needs an alternative provider or a constituent-weighted reconstruction. **Not faked.** |
| 6 companies without statements | IRON, KZPC, PRMH, SPMD, SUGR, ELEC — reported as unavailable. |
| 5 unresolved tickers | QNBA, MNHD, ESRS, AUTO (merged into GBCO), AIVC. Need symbol research. |
| Universe is ~49, not all ~250 EGX listings | Seeded with the liquid names. Expandable in `universe.py`. |
| Single data source | Rule 74 (cross-source validation) is not yet implementable with one provider. |
| No scheduler | Refresh is manual. |
| No auth | No user accounts yet, so no personal data is stored — which is also why no security layer is needed *yet*. It will be before accounts ship. |

## Regulatory position

Egyptian FRA licensing is required to provide personalised investment advice
to the public. This build is deliberately positioned as **research, analysis
and simulation software** and the footer says so on every page. The portfolio
recommendation engine described in the original brief must not ship to the
public without licensing review — that is a legal constraint, not a technical
one, and no amount of code changes it.
