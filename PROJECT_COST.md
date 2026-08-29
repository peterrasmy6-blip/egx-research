# Project cost

## Mandatory monthly cost

# EGP 0

## Paid services

**None.**

---

## What everything costs

| Item | Service used | Cost |
|---|---|---|
| Market prices, dividends, financial statements | Yahoo Finance via `yfinance` (open source) | EGP 0 |
| EGX company list | stockanalysis.com public listing page | EGP 0 |
| Backend framework | FastAPI (open source) | EGP 0 |
| Database | SQLite (open source), file-based | EGP 0 |
| Charts | Chart.js (open source, MIT) | EGP 0 |
| Fonts | Google Fonts | EGP 0 |
| Calculations | Written in this project; nothing licensed | EGP 0 |
| Automated daily updates | GitHub Actions free tier (public repositories) | EGP 0 |
| Hosting | Free tier — see below | EGP 0 |
| Domain | None purchased. A free subdomain is used | EGP 0 |
| AI assistant | Not built as a paid dependency — see below | EGP 0 |

---

## Hosting: static, so it cannot start charging

The site is exported as a folder of plain files. There is no server, no
container, and no compute to bill.

| Option | Cost | Card needed? | Notes |
|---|---|---|---|
| **Cloudflare Pages** | Free forever | No | Recommended. Fast worldwide |
| **Netlify Drop** | Free | No | Easiest — drag the folder onto a web page |
| **GitHub Pages** | Free | No | Also enables free automatic daily updates |

**Why static rather than a running server.** Free tiers for *compute* are the
ones that get withdrawn, throttled, or moved behind a paid plan — Hugging Face
Docker Spaces, for instance, now give conflicting answers about whether the CPU
tier still runs free. Static file hosting has no such ambiguity: there is
nothing metered to charge for.

The trade-off is that every calculation runs in the visitor's browser instead of
on a server. The Python engine was ported to JavaScript for this, and the two
are checked against each other by 267 automated parity assertions — so moving
the maths into the browser did not change any answer.

A `Dockerfile` is still included if a server deployment is ever wanted, but it
is not needed and not used.

---

## Deliberately not purchased

These were investigated and rejected on cost, exactly as instructed.

| Service | Approximate cost | What it would have added | What we did instead |
|---|---|---|---|
| EODHD | ~$20–80/month | Clean EGX fundamentals, index history | Calculate every ratio ourselves from free raw statements |
| Twelve Data paid tier | ~$30+/month | Higher rate limits, fundamentals | Throttled, cached ingestion into our own database |
| Bloomberg / Refinitiv / FactSet | Thousands/month | Everything | Not needed for a research and education site |
| A domain name | ~$12/year | A nicer URL | A free subdomain works fine |
| Paid AI API | Usage-based | A chat assistant | See below |

**The rule applied throughout: never pay for a metric that can be calculated
from free raw data.** P/E, P/B, ROE, ROA, ROIC, margins, growth rates, CAGR,
volatility, Sharpe, Sortino, drawdown, market capitalisation and enterprise
value are all computed in this project's own code, from statements and prices we
already hold. Buying them pre-computed would cost money *and* make them
untraceable.

---

## About the AI assistant

An AI chat analyst was specified in the brief. Building it on a commercial AI API
would create a per-message running cost — breaking the EGP 0 requirement — and
would make the site's availability depend on a paid third party.

**What was built instead:** the platform explains itself in plain language
without any AI. Every valuation states its methods, assumptions and confidence.
Every metric carries a explanation. The education section defines every term
used. A user asking "why does this look undervalued?" gets a structured answer
from the deterministic engine, not from a language model that might invent one.

This is also the safer design. A language model asked about a stock can
fabricate figures. The quantitative engine cannot — it either has the data or
reports that it does not.

If an AI assistant is added later, it must sit on top of the existing structured
data and must never generate numbers itself. That constraint is recorded in
`docs/ARCHITECTURE.md`.

---

## If something ever genuinely requires payment

The rule followed here:

1. Do not purchase it.
2. Do not ask you to purchase it.
3. Search for a free alternative.
4. Explain the limitation honestly.
5. Implement the best free option available.

Two limitations currently fall under this rule and are **documented rather than
purchased around**: EGX index history, and Egyptian fund NAV data. Both are
recorded in `DATA_SOURCES.md` and shown as unavailable on the site. Neither is
faked.
