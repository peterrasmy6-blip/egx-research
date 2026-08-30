# Stock universe audit

What the reference screenshots contained, what was treated as a company, and
exactly what changed in the site's stock list as a result.

Generated 2026-08-29.

---

## The headline numbers you asked for

| | Count |
|---|---:|
| Total entries in the screenshots | **273** |
| Actual ordinary stocks identified | **262** |
| Excluded rights / certificates / other instruments | **11** |
| Stocks added | **14** |
| Stocks removed as duplicates or non-stock instruments | **63** |
| **Final stock universe** | **269** |

The final figure is 262 + 7. The seven extra are explained under
[Seven companies kept](#seven-companies-kept-that-are-not-on-the-screenshots).

The 273 is not an estimate. All 31 screenshot pages were read and every row
transcribed: 30 in the "popular" block at the top and 243 in the A–Z list
below it, with no overlap between them. That the total lands exactly on the
273 you quoted is the strongest check available that nothing was missed.

---

## The 11 entries that are not companies

Each of these appears in the screenshots as its own row. None is an ordinary
share of a company, and counting them would either invent a company that does
not exist or count a real one twice.

| Ticker | What it actually is |
|---|---|
| `AMES_r2` | Rights issue of Alexandria New Medical Center — a temporary right to subscribe to new shares |
| `ARAB_r2` | Rights issue of ARAB Developers Holding |
| `ASPI_r3` | Subscription rights of Aspire Capital |
| `FCMD_r3` | Rights issue of Future Care Medical |
| `KRDI_r1` | Rights issue of Al Khair River |
| `SVCE_r1` | Subscription rights of South Valley Cement |
| `EGX30ETF` | An index tracker holding thirty companies. Not a business |
| `KASABF` | Certificates over Odin Egyptian — a wrapper, not a listed company |
| `EGREF` | A listed real-estate **fund**, not an operating company |
| `FAITA` | The dollar-quoted class of Faisal Islamic Bank. The bank is covered once, as `FAIT` |
| `VLMR` | The dollar-quoted class of Valmore Holding. Covered once, as `VLMRA` |

The company behind every rights issue is still in the universe under its own
ticker — `AMES`, `ARAB`, `ASPI`, `FCMD`, `KRDI`, `SVCE` — and Odin itself is
there as `ODIN`. Nothing was lost by excluding the wrappers.

A rights issue is not a pedantic distinction. `KRDI_r1` traded at EGP 0.22
against `KRDI` at EGP 0.45 on the same day; treating it as a company would have
put a "stock" on the screener at half the price of its own parent, with no
revenue, no earnings and no balance sheet.

---

## The 14 stocks added

Present in the screenshots, absent from the site before:

`ADRI` `AIFI` `ALEX` `BIDI` `FCMD` `FIRE` `FTNS` `HBCO` `HCFI` `IEEC` `MBEG`
`RKAZ` `TWSA` `UPMS`

Three of these were already in the database under a stale ticker and have been
renamed rather than duplicated, so their price history came with them:

* `ALRA` → `AIFI` — Atlas for Investment and Food Industries
* `ALEXA` → `ALEX` — Alexandria Portland Cement
* `MBEN` → `MBEG` — M.B Engineering

The other eleven are new rows.

---

## The 63 removals

### Not a company at all — 9

`EGX30ETF` (ETF) · `KASABF` (certificate) · `FAITA`, `VLMR`, `CCAPP`, `SEIGA`,
`AIVCB`, `AREHA`, `SMCSA` (second share classes: another currency, preferred
shares or bearer shares)

`CCAPP` is preferred stock of Qalaa Holdings, which is in the universe as
`CCAP`. `AREHA` is the bearer-share line of a company already listed. In every
case the business is still covered — once.

### The same company under a former ticker — 11

| Was | Is now | |
|---|---|---|
| `AUTO` | `GBCO` | GB Auto renamed itself GB Corp |
| `OTMT` | `OIH` | Orascom Telecom Media → Orascom Investment Holding |
| `OCIC` | `ORAS` | Orascom Construction Industries → Orascom Construction |
| `MNHD` | `MASR` | Medinet Nasr Housing → Madinet Masr |
| `SRWA` | `CNFN` | Sarwa Capital → Contact Financial Holding |
| `ABRD` | `FERC` | Egyptians Abroad for Investment and Development |
| `ODID` | `ODIN` | Odin for Investment and Development |
| `QNBA` | `QNBE` | spelling variant of Qatar National Bank Alahli |
| `MBEN` | `MBEG` | spelling variant of M.B Engineering |
| `ALEXA` | `ALEX` | Alexandria Portland Cement |
| `ALRA` | `AIFI` | Atlas for Investment and Food Industries |

Each pair was one company appearing twice. Where both rows existed, the one
with the longer price history was kept and the other retired.

### No longer on the exchange, and no data anywhere — 43

`AGIN` `AIND` `AITG` `AMEC` `ANFI` `BCAP` `BSFR` `CIRF` `EBDP` `ESGI` `FIRED`
`GETO` `ICAL` `IDHC` `INEE` `IPPM` `ITSY` `LKGP` `MEDA` `MFINEG` `MRCO` `NASR`
`NCEM` `NCIN` `NCIS` `NCMP` `NOAF` `ODHN` `OREG` `POCO` `PSAD` `PTCC` `REAC`
`RIVA` `SBAG` `SLTD` `SMCS` `TECH` `TOUR` `UNBE` `UNFO` `VODE` `XPIN`

Some are recognisable: Vodafone Egypt and Orange Egypt both left the exchange,
Integrated Diagnostics (`IDHC`) trades in London, Orascom Development Holding
(`ODHN`) is Swiss-listed. All 43 share the same two properties: they are absent
from the broker's live instrument list, and **not one of them returned a single
price bar from any source** across the full ten-year fetch. That is the
evidential test that was applied — not a guess about whether a name sounded
current.

**Nothing has been deleted.** Every removed ticker is still in the database,
marked with the reason it was retired, so it can be revived if it lists again.

---

## Seven companies kept that are not on the screenshots

Your instruction was not to delete anything without first establishing whether
it is a genuine ordinary stock. Seven survived that test: they are absent from
the broker's list, but each carries real, current price history on the
exchange.

| Ticker | Company | Price bars |
|---|---|---:|
| `EDBM` | Egyptian For Developing Building Materials | 2,465 |
| `NDRL` | National Drilling Company | 2,464 |
| `DCCC` | Damietta Container and Cargo Handling | 891 |
| `EKHO` | Egypt Kuwait Holding | ✓ |
| `ARVA` | Arab Valves Company | ✓ |
| `EIUD` | Egyptians For Investment and Urban Development | ✓ |
| `ICMI` | International Company For Medical Industries | ✓ |

Deleting a company that demonstrably trades on the EGX, purely because one
broker's app does not carry it, would have been the wrong call. They are in the
universe and flagged on their own pages with a note explaining that your broker
may not offer them.

If you would rather the site showed *only* what you can buy through Thndr, this
is a one-line change: remove the `KEEP_EXTRA` block in
`backend/app/ingest/reference_universe.py` and the count becomes exactly 262.

---

## How this is kept true

The classification is not a one-off database edit. It lives in
`backend/app/ingest/reference_universe.py` and is applied by
`apply_reference()` on **every** refresh, so tomorrow's automatic update cannot
quietly reintroduce the ghosts.

`backend/tests/test_universe.py` (35 checks) fails the build if:

* any ticker is classified as both a company and an excluded instrument;
* any rights issue, ETF, certificate or second share class becomes searchable;
* the company behind an excluded instrument goes missing;
* a rename produces two rows for one company;
* the searchable universe stops matching the reference list;
* a retired ticker is dropped without recording why.

The browser test harness adds search checks against the real universe: that
`AMES_r2` and its ten companions cannot be selected anywhere on the site, that
`AUTO` no longer resolves but `GBCO` does, and that typing `COMI`, `comi`,
`Commercial International Bank`, `comm int bank` or `bank` all reach CIB.

Writing that test found a real bug, which is now fixed: `classify()`
upper-cased the ticker before looking it up, so `AMES_r2` (lower-case `r`)
silently failed to match and would have been treated as an unknown company.

---

## Two things this does not fix

**Funds.** You mentioned roughly 63 funds; the site carries 40. The screenshots
covered stocks only, so there was nothing here to reconcile against. The free
source publishes 40 with NAV; the exchange's own funds page blocks automated
access. The gap is real and is not closed by this work.

**Price coverage — substantially improved, not solved.** Cleaning the universe
exposed a separate problem: 57 of the 269 companies had no price at all,
including Ezz Steel, Telecom Egypt, TAQA Arabia, Suez Cement and Qatar National
Bank Alahli. That was not a listing problem, it was a symbol problem.

The price source carries most of the exchange twice: under the short ticker
(`COMI.CA`), which has full history, and under an ISIN-form symbol
(`EGS3C251C013-EGP.CA`), which returns a live quote and nothing else. For about
a fifth of the market only the ISIN form exists, and the site was only ever
asking for the short one.

Two new steps now run on every refresh, `resolve_isins()` and `sync_quotes()`:

* 7 companies turned out to have full history under a corrected ticker and now
  carry it — `AIFI` gained 2,468 daily bars, `MBEG` 2,447, `BIDI` 1,961,
  `RKAZ` 1,903, `FIRE` 1,830, `MKIT` 1,951, `FTNS` 525;
* 42 more now have a real current price, market capitalisation and day change
  where they previously showed nothing.

Companies with price history: **205 → 254** of 269.

The quote is stored under its own source label (`yahoo-isin-quote`) and is never
allowed to masquerade as history. One bar cannot produce a return, a
volatility, a drawdown or a chart, and the engines go on refusing to compute
them — a single-bar company would otherwise have reported itself as its own
52-week high *and* low, sitting at "0% from its high", which is true and
useless; that is now guarded. Each such company carries a note saying plainly
that only a current price is available.

**15 companies still have no price of any kind.** They remain in the universe,
searchable and marked **No data**, per your instruction to keep incomplete
securities visible rather than hide them. Live counts are in
`EGX_COVERAGE_REPORT.md`, regenerated from the database rather than written by
hand.
