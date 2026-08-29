# START HERE

Your Egyptian stock market research website. Written for someone who does not
write code.

---

## 1. Opening the website on your computer

1. Open the folder `Desktop\Website`.
2. Double-click **START_WEBSITE.bat**.
3. A black window opens. **Leave it open.**
4. Open your browser and go to:

   **http://127.0.0.1:8200**

To stop it, close the black window.

> **Do not** double-click `site\index.html` directly — browsers block pages
> from reading local data files, so it will look broken. Use the .bat file.

> If the black window closes instantly, tell me *"the start file closes
> immediately"* and I will fix it.

---

## 2. Putting it online for your friends

The website is now a **static site** — just a folder of ordinary files, sitting
in `Desktop\Website\site`. There is no server to run and nothing that can ever
start charging you.

The fastest way to see it live: go to **https://app.netlify.com/drop** and drag
the `site` folder onto the page. You get a working link in under a minute.

**DEPLOY.md** covers that plus two permanent free options (Cloudflare Pages and
GitHub Pages), step by step.

The one thing I cannot do is create an account in your name. Everything else is
built and waiting.

---

## 3. What the website does

**Nine sections**, all free, no login needed:

| Section | What it does |
|---|---|
| **Home** | Biggest movers, largest companies, market overview |
| **Markets** | Every listed Egyptian company, filterable by sector |
| **Screener** | Filter the whole exchange — "show me profitable companies trading cheaply" |
| **Compare** | Up to six companies side by side |
| **What If?** | What a real investment would actually have done |
| **Backtest** | Test a mix of shares over history, with rebalancing and costs |
| **Future Scenarios** | Projections and Monte Carlo — ranges, never predictions |
| **Portfolio** | Enter what you hold and see what it is exposed to |
| **Learn** | 24 terms explained, 6 guides, a risk questionnaire |

**Search works without knowing ticker codes.** Type "bank", "Commercial", or
"COMI" — all three find CIB.

---

## 4. Three things worth knowing

### It shows you inflation

Most sites say "your money grew 337%!" and stop. Real example from your data —
CIB, 100,000 EGP, five years:

| | |
|---|---|
| What the number says | **437,562 EGP** (+337%) |
| What it can actually buy | **~147,000 EGP** of 2021 goods (+47%) |

Both true. The second one decides whether you actually got richer.

### It refuses to guess

If a company does not publish something, the site shows a dash — not a zero, not
an estimate. About 29 companies have no price data available free. They stay in
the list, marked "Unavailable", rather than quietly disappearing.

### It caught its own mistake

While building, the homepage briefly showed a company up **+805% in a year**. It
wasn't. Its price jumped from 9.22 to 97.57 overnight — impossible, because the
Egyptian Exchange limits daily moves to about 10–20%. It was a share
consolidation the data source never applied to the older prices.

**31 of 227 companies** had this problem. The site now detects it and hides
those returns instead of publishing fiction. It still shows genuinely huge
moves — one company really did rise 762% through weeks of hitting the daily
limit — because those are real.

It also caught a second fault. Four companies appeared to be spectacular
bargains — one "undervalued by 2,934%". They are share classes quoted in **US
dollars** while the company files its accounts in **Egyptian pounds**. Dividing
one by the other is meaningless. Those figures are now withheld too.

---

## 5. Why fair values may look pessimistic

The site often says Egyptian shares look expensive, even at a P/E of 6. That is
not a bug.

Egyptian government paper pays roughly **20% a year** with far less risk than
shares. So a company has to clear a very high bar before owning it beats simply
lending to the government. A valuation model built on European interest rates of
8% would roughly double every number on this site — and every one would be wrong.

The rate used is shown on every valuation page, along with where it came from.

---

## 6. What it will not do

It will never tell you to buy or sell anything, or how to divide your money.

That is deliberate. It is research, analysis and education software — not a
licensed adviser. It gives you information and tools; the decision is yours.

**Research. Understand. Decide.**

---

## 7. Keeping data current

**Set it to update itself:** see **AUTOMATIC_UPDATES.md**. About 15 minutes of
setup, once, and then the site refreshes every trading day on its own — free,
and neither you nor I ever touch it again.

One honest limit: live, second-by-second prices are not available for free. The
data source publishes Egyptian prices once a day only, and its "current price"
field for EGX is broken (it reports CIB at a July 2024 price). So the site
updates after each trading day's close. That is the ceiling without a paid
exchange feed.

Until you set that up, just say *"update the market data"* and I will run it.

---

## 8. The other documents

| File | What it is |
|---|---|
| **DEPLOY.md** | How to put the site online, step by step |
| **AUTOMATIC_UPDATES.md** | How to make it refresh itself every trading day |
| **PROJECT_STATUS.md** | What is done, what is missing, what needs you |
| **PROJECT_COST.md** | Proof it costs EGP 0, and what was deliberately not bought |
| **DATA_SOURCES.md** | Every data source and its terms |
| **EGX_COVERAGE_REPORT.md** | Evidence of exactly what is covered — generated from the database |
| **docs/ARCHITECTURE.md** | Technical detail |

---

## 9. What to ask for next

Just say it in plain words:

- *"Put the website online."*
- *"Update the market data."*
- *"Add Arabic company names."*
- *"The screener should also filter by X."*
