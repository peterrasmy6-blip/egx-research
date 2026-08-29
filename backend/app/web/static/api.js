/* EGX Research — data access layer.

   The site is served as static files, so there is no backend to call. This
   module presents the same `api()` / `post()` interface the views already use,
   but resolves reads from pre-built JSON and runs calculations locally through
   ENGINE.

   Keeping the interface identical means the view code is the same whether the
   site is served by the local Python server or by a static host — so what is
   tested locally is exactly what ships.
*/

/* Wrapped in an IIFE and exposing only `api` and `post`.

   These helpers previously sat in the global scope, where `runScreen` collided
   with the identically named UI function in views2.js. Whichever file loaded
   last won, which silently broke the screener. Nothing here should be reachable
   by name from the view layer.
*/
const {api, post} = (() => {

  const DATA = "data";
  const _cache = new Map();

  async function loadJSON(path) {
    if (_cache.has(path)) return _cache.get(path);
    const p = fetch(path).then(r => {
      if (!r.ok) throw new Error(`Could not load ${path} (${r.status})`);
      return r.json();
    });
    _cache.set(path, p);
    try { return await p; } catch (e) { _cache.delete(path); throw e; }
  }

  const loadCompany = t => loadJSON(`${DATA}/company/${encodeURIComponent(t.toUpperCase())}.json`);
  const loadMetrics = () => loadJSON(`${DATA}/metrics.json`);
  const loadReference = () => loadJSON(`${DATA}/reference.json`);

  class ApiError extends Error {}

  /* ---------------- helpers ---------------- */
  function parseQuery(path) {
    const i = path.indexOf("?");
    const out = {};
    if (i < 0) return [path, out];
    for (const [k, v] of new URLSearchParams(path.slice(i + 1))) out[k] = v;
    return [path.slice(0, i), out];
  }

  function sliceRange(prices, range) {
    const days = {"1m": 30, "3m": 91, "6m": 182, "1y": 365, "3y": 1095,
                  "5y": 1826, "10y": 3652, "max": 100000}[String(range).toLowerCase()] ?? 1826;
    const d = prices.d;
    if (!d.length) return [];
    const lastMs = Date.parse(d[d.length - 1] + "T00:00:00Z");
    const cutoff = new Date(lastMs - days * 86400000).toISOString().slice(0, 10);
    const out = [];
    for (let i = 0; i < d.length; i++) {
      if (d[i] >= cutoff) out.push({d: d[i], c: prices.c[i], a: prices.a[i]});
    }
    return out;
  }

  /* ---------------- GET ---------------- */
  async function api(rawPath) {
    const [path, q] = parseQuery(rawPath.replace(/^\/+/, ""));
    const parts = path.split("/").filter(Boolean);     // ["api", ...]
    const seg = parts.slice(1);

    if (seg[0] === "securities") return loadJSON(`${DATA}/securities.json`);
    if (seg[0] === "sectors") return loadJSON(`${DATA}/sectors.json`);
    if (seg[0] === "status") return loadJSON(`${DATA}/status.json`);
    if (seg[0] === "disclaimer") {
      const s = await loadJSON(`${DATA}/status.json`);
      return {disclaimer: s.disclaimer};
    }

    if (seg[0] === "search") {
      const term = (q.q || "").trim().toLowerCase();
      if (!term) return [];
      const list = await loadJSON(`${DATA}/securities.json`);
      return list
        .filter(s => s.ticker.toLowerCase().includes(term) ||
                     s.name.toLowerCase().includes(term) ||
                     (s.sector || "").toLowerCase().includes(term))
        .sort((a, b) => {
          // Exact ticker match first, then by size.
          const ax = a.ticker.toLowerCase() === term ? 1 : 0;
          const bx = b.ticker.toLowerCase() === term ? 1 : 0;
          if (ax !== bx) return bx - ax;
          return (b.market_cap || 0) - (a.market_cap || 0);
        })
        .slice(0, 25)
        .map(s => ({ticker: s.ticker, name: s.name, sector: s.sector,
                    data_quality: s.data_quality,
                    listing_status: s.listing_status, price: s.price}));
    }

    if (seg[0] === "market") {
      if (seg[1] === "composite") return loadJSON(`${DATA}/composite.json`);
      if (seg[1] === "indices-note") return (await loadReference()).indices_note;
    }

    if (seg[0] === "education") {
      const e = await loadJSON(`${DATA}/education.json`);
      if (seg[1] === "glossary") return {terms: e.glossary};
      if (seg[1] === "lessons") return {lessons: e.lessons};
      if (seg[1] === "questionnaire") {
        return {questions: e.questionnaire,
                note: "This questionnaire is educational. It describes how you " +
                      "tend to think about risk. It does not produce a " +
                      "personalised investment recommendation."};
      }
    }

    if (seg[0] === "screener" && seg[1] === "fields") {
      return {fields: (await loadReference()).screener_fields};
    }

    if (seg[0] === "compare") {
      return compareCompanies(await loadMetrics(),
                              (q.tickers || "").split(",").map(t => t.trim()).filter(Boolean));
    }

    if (seg[0] === "security") {
      const ticker = decodeURIComponent(seg[1] || "");
      let co;
      try { co = await loadCompany(ticker); }
      catch (e) { throw new ApiError(`We do not hold data for '${ticker}'.`); }

      if (!seg[2]) {
        // Company detail. `valuation` here is the ratio block the view expects.
        return {...co, valuation: co.valuation_ratios || {}};
      }
      if (seg[2] === "prices") {
        const pts = sliceRange(co.prices, q.range || "5y");
        return {ticker: co.ticker, currency: co.currency, range: q.range || "5y",
                available: pts.length > 0, points: pts};
      }
      if (seg[2] === "fundamentals") {
        const freq = q.frequency === "quarterly" ? "quarterly" : "annual";
        const hist = (co.fundamentals || {})[freq] || [];
        if (!hist.length) {
          return {ticker: co.ticker, available: false,
                  reason: `No ${freq} financial statements are available for this ` +
                          `company from free sources.`};
        }
        return {ticker: co.ticker, currency: co.currency, frequency: freq,
                available: true, history: hist, source: co.data_quality.source};
      }
      if (seg[2] === "dividends") {
        const divs = (co.dividends || []).slice().reverse();
        return {ticker: co.ticker, currency: co.currency, count: divs.length,
                dividends: divs};
      }
      if (seg[2] === "valuation") {
        if (!co.valuation) {
          return {available: false,
                  reason: co.data_quality.units_suspect
                    ? "This security's price and its published accounts do not " +
                      "appear to be in the same currency, so a fair value cannot " +
                      "be estimated."
                    : "Not enough financial data is available to estimate a fair " +
                      "value for this company."};
        }
        return {...co.valuation, ticker: co.ticker, name: co.name,
                as_of: co.price_date};
      }
      if (seg[2] === "risk-parameters") {
        const p = ENGINE.estimateParameters(co);
        return {ticker: co.ticker, name: co.name,
                annual_return_historical_pct: Math.round(p.annual_return_historical * 10000) / 100,
                annual_volatility_pct: Math.round(p.annual_volatility * 10000) / 100,
                years_of_history: p.years_of_history,
                period_start: p.period_start, period_end: p.period_end,
                note: "Measured from past prices. The past is not a forecast."};
      }
    }

    throw new ApiError(`Unknown request: ${rawPath}`);
  }

  /* ---------------- POST (computed locally) ---------------- */
  async function post(rawPath, body) {
    const path = rawPath.replace(/^\/+/, "");
    const seg = path.split("/").filter(Boolean).slice(1);
    const today = new Date().toISOString().slice(0, 10);

    try {
      if (seg[0] === "scenario") {
        if (body.start > today)
          throw new ApiError("That date is in the future. This tool looks at what already happened.");
        const co = await loadCompany(body.ticker);
        if (seg[1] === "lumpsum") {
          return ENGINE.lumpSum(co, body.amount, body.start, {
            end: body.end, reinvest_dividends: body.reinvest_dividends,
            inflation_annual: body.inflation_annual,
          });
        }
        if (seg[1] === "monthly") {
          return ENGINE.monthlyPlan(co, body.monthly_amount, body.start, {
            end: body.end, initial_amount: body.initial_amount,
            inflation_annual: body.inflation_annual,
          });
        }
      }

      if (seg[0] === "backtest") {
        if (body.start > today) throw new ApiError("The start date is in the future.");
        const companies = {};
        for (const h of body.holdings) companies[h.ticker] = await loadCompany(h.ticker);
        return ENGINE.backtest(companies, body.holdings, body.start, {
          end: body.end, initial: body.initial, monthly: body.monthly,
          rebalance: body.rebalance, reinvest_dividends: body.reinvest_dividends,
        });
      }

      if (seg[0] === "portfolio" && seg[1] === "analyse") {
        return ENGINE.analyseComposition(await loadMetrics(), body);
      }

      if (seg[0] === "forecast") {
        if (seg[1] === "scenarios") {
          return ENGINE.scenarioProjection(
            body.initial, body.monthly, body.years,
            {conservative: body.conservative_pct / 100,
             base: body.base_pct / 100,
             optimistic: body.optimistic_pct / 100},
            body.inflation_pct / 100, (body.annual_increase_pct || 0) / 100);
        }
        if (seg[1] === "montecarlo") return monteCarloRequest(body);
      if (seg[1] === "portfolio") {
        return forecastPortfolioLocal(body, {
          loadJSON, loadCompany, loadMetrics, DATA, ApiError});
      }
      }

      if (seg[0] === "screener") {
        return runScreen(await loadMetrics(), await loadReference(), body);
      }

      if (seg[0] === "education" && seg[1] === "questionnaire") {
        const e = await loadJSON(`${DATA}/education.json`);
        return scoreQuestionnaire(e, body.answers || {});
      }
    } catch (e) {
      if (e instanceof ENGINE.InsufficientData) throw new ApiError(e.message);
      throw e;
    }

    throw new ApiError(`Unknown request: ${rawPath}`);
  }

  /* ---------------- Monte Carlo assumption handling ---------------- */
  async function monteCarloRequest(body) {
    let r = body.annual_return_pct != null ? body.annual_return_pct / 100 : null;
    let v = body.annual_volatility_pct != null ? body.annual_volatility_pct / 100 : null;
    let basis = "assumptions you provided";
    const warnings = [];
    let historical = null;

    if (body.ticker) {
      const co = await loadCompany(body.ticker);
      const p = ENGINE.estimateParameters(co);
      historical = p.annual_return_historical;
      if (v == null) v = p.annual_volatility;

      // Volatility is reasonably stable to measure from history. Expected return
      // is not: a company fresh off a strong run would project a spectacular
      // future purely because it did well before. The default is therefore the
      // market-implied cost of equity, not the past average.
      const ref = await loadReference();
      const marketExpected = ref.valuation_defaults.risk_free_rate +
                             ref.valuation_defaults.equity_risk_premium;
      if (r == null) {
        r = marketExpected;
        basis = `a market-based expected return of ${(r * 100).toFixed(1)}% ` +
                `(Egyptian government yield plus an equity risk premium), with ` +
                `volatility of ${(v * 100).toFixed(1)}% measured from ${co.ticker}'s ` +
                `own history between ${p.period_start} and ${p.period_end}`;
        if (historical > marketExpected * 1.3) {
          warnings.push(
            `${co.ticker} returned about ${(historical * 100).toFixed(0)}% a year over ` +
            `the past ${p.years_of_history} years. That is far above what investors ` +
            `currently require, and assuming it continues would produce a very ` +
            `flattering projection. This simulation uses ${(r * 100).toFixed(1)}% instead. ` +
            `You can override it, but a past run is not a forecast.`);
        }
      } else {
        basis = `your chosen return of ${(r * 100).toFixed(1)}%, with volatility of ` +
                `${(v * 100).toFixed(1)}% measured from ${co.ticker}'s history`;
      }
    }

    if (r == null || v == null) {
      throw new ApiError("Provide an expected return and volatility, or choose a " +
                         "company so volatility can be measured from its history.");
    }

    const out = ENGINE.monteCarlo(body.initial, body.monthly, body.years, r, v, {
      simulations: body.simulations, inflation: body.inflation_pct / 100,
      target: body.target,
    });
    out.basis = basis;
    out.ticker = body.ticker || null;
    out.warnings = warnings;
    out.historical_return_pct = historical == null ? null
      : Math.round(historical * 1000) / 10;
    return out;
  }

  /* ---------------- screener ---------------- */
  function runScreen(metrics, reference, req) {
    const fields = new Set(reference.screener_fields.map(f => f.field));
    const labels = {};
    for (const f of reference.screener_fields) labels[f.field] = f;

    const filters = (req.filters || []).filter(f => fields.has(f.field));
    const used = filters.map(f => f.field);
    const entries = Object.entries(metrics);

    let skipped = 0;
    const kept = [];
    for (const [ticker, m] of entries) {
      if (req.sectors && req.sectors.length && !req.sectors.includes(m.sector)) continue;
      // A company must have every filtered metric to be judged fairly. Missing
      // is never treated as zero.
      if (used.some(f => m[f] == null)) { skipped++; continue; }
      let ok = true;
      for (const f of filters) {
        const val = m[f.field], target = Number(f.value);
        if (Number.isNaN(target)) continue;
        const op = f.op || "gte";
        if (op === "gte" && !(val >= target)) ok = false;
        else if (op === "lte" && !(val <= target)) ok = false;
        else if (op === "gt" && !(val > target)) ok = false;
        else if (op === "lt" && !(val < target)) ok = false;
        else if (op === "eq" && Math.abs(val - target) >= 1e-9) ok = false;
        if (!ok) break;
      }
      if (ok) kept.push([ticker, m]);
    }

    const sortBy = req.sort_by || "market_cap";
    const desc = req.descending !== false;
    kept.sort((a, b) => {
      if (sortBy === "ticker") return desc ? b[0].localeCompare(a[0]) : a[0].localeCompare(b[0]);
      if (sortBy === "name") return desc ? b[1].name.localeCompare(a[1].name)
                                         : a[1].name.localeCompare(b[1].name);
      const av = a[1][sortBy], bv = b[1][sortBy];
      // Unknown sorts last rather than counting as zero.
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return desc ? bv - av : av - bv;
    });

    const limit = req.limit || 100;
    return {
      count: kept.length, returned: Math.min(limit, kept.length),
      skipped_missing_data: skipped, universe_size: entries.length,
      filters_applied: filters.map(f => ({
        field: f.field, label: labels[f.field].label, op: f.op || "gte",
        value: f.value, unit: labels[f.field].unit})),
      results: kept.slice(0, limit).map(([ticker, m]) => ({ticker, ...m})),
      note: skipped ? `${skipped} companies were left out because at least one of ` +
        `the measures you filtered on is not available for them. They are not ` +
        `necessarily failing the test - we simply cannot check.` : null,
    };
  }

  /* ---------------- comparison ---------------- */
  function compareCompanies(metrics, tickers) {
    if (tickers.length < 2) throw new ApiError("Choose at least two companies to compare.");
    if (tickers.length > 6) throw new ApiError("Compare at most six companies at a time.");

    const rows = tickers.map(t => {
      const m = metrics[t.toUpperCase()];
      if (!m) throw new ApiError(`We do not hold data for '${t}'.`);
      return {ticker: t.toUpperCase(), ...m};
    });

    const measures = [
      ["price", "Price", null, "EGP"],
      ["market_cap", "Market value", null, "EGP"],
      ["pe", "Price / earnings", false, "x"],
      ["pb", "Price / book", false, "x"],
      ["ev_ebitda", "EV / EBITDA", false, "x"],
      ["dividend_yield_pct", "Dividend yield", true, "%"],
      ["roe_pct", "Return on equity", true, "%"],
      ["roic_pct", "Return on invested capital", true, "%"],
      ["net_margin_pct", "Net margin", true, "%"],
      ["revenue_growth_pct", "Revenue growth", true, "%"],
      ["earnings_growth_pct", "Profit growth", true, "%"],
      ["debt_to_equity", "Debt / equity", false, "x"],
      ["volatility_pct", "Volatility", false, "%"],
      ["max_drawdown_pct", "Worst fall", true, "%"],
      ["ret_1y", "1-year return", true, "%"],
      ["ret_3y", "3-year return", true, "%"],
      ["upside_pct", "Model upside", true, "%"],
    ];

    const table = [], observations = [];
    for (const [field, label, higher, unit] of measures) {
      const vals = rows.map(r => [r.ticker, r[field] ?? null]);
      const present = vals.filter(v => v[1] != null);
      let leader = null;
      if (higher != null && present.length >= 2) {
        leader = present.reduce((a, b) => (higher ? b[1] > a[1] : b[1] < a[1]) ? b : a)[0];
      }
      table.push({field, label, unit,
                  values: Object.fromEntries(vals), leader,
                  missing: vals.filter(v => v[1] == null).map(v => v[0])});
    }

    const note = (field, label, higher, digits, suffix) => {
      const present = rows.filter(r => r[field] != null).map(r => [r.ticker, r[field]]);
      if (present.length < 2) return;
      const best = present.reduce((a, b) => (higher ? b[1] > a[1] : b[1] < a[1]) ? b : a);
      const worst = present.reduce((a, b) => (higher ? b[1] < a[1] : b[1] > a[1]) ? b : a);
      if (best[0] !== worst[0]) {
        observations.push(`${label}: ${best[0]} is at ${best[1].toFixed(digits)}${suffix}, ` +
          `against ${worst[1].toFixed(digits)}${suffix} for ${worst[0]}.`);
      }
    };
    note("roe_pct", "Return on equity", true, 1, "%");
    note("pe", "Price to earnings", false, 1, "x");
    note("dividend_yield_pct", "Dividend yield", true, 2, "%");
    note("volatility_pct", "Volatility", false, 1, "%");
    note("revenue_growth_pct", "Revenue growth", true, 1, "%");

    return {
      companies: rows, table, observations,
      note: "Leading on one measure does not make a company a better investment. " +
            "Which measures matter depends on what you are trying to achieve, and " +
            "that judgement is yours.",
    };
  }

  /* ---------------- questionnaire ---------------- */
  function scoreQuestionnaire(edu, answers) {
    const questions = edu.questionnaire, PROFILES = edu.profiles;
    const dims = {tolerance: [], capacity: [], horizon: [], knowledge: []};
    let answered = 0;
    for (const q of questions) {
      const v = parseInt(answers[q.id], 10);
      if (Number.isInteger(v) && v >= 1 && v <= 4) { dims[q.dimension].push(v); answered++; }
    }
    const need = Math.floor(questions.length * 0.6);
    if (answered < need) {
      return {complete: false,
              reason: `Please answer more of the questions - at least ${need} of ` +
                      `${questions.length} - before we describe a profile.`};
    }

    const pct = vals => vals.length
      ? Math.round((vals.reduce((a, b) => a + b, 0) / vals.length - 1) / 3 * 100) : null;
    const tolerance = pct(dims.tolerance), capacity = pct(dims.capacity),
          horizon = pct(dims.horizon), knowledge = pct(dims.knowledge);

    const parts = [tolerance, capacity, horizon].filter(x => x != null);
    let overall = parts.length ? Math.round(parts.reduce((a, b) => a + b, 0) / parts.length) : 0;
    // Capacity and horizon constrain what tolerance can safely mean.
    if (capacity != null && horizon != null) {
      overall = Math.min(overall, Math.min(capacity, horizon) + 20);
    }

    const name = overall < 30 ? "Conservative" : overall < 55 ? "Moderate"
               : overall < 78 ? "Growth-oriented" : "Aggressive";

    const tensions = [];
    if (tolerance != null && capacity != null && tolerance - capacity >= 30) {
      tensions.push("Your appetite for risk is considerably higher than your current " +
        "ability to absorb a loss. Being willing to take a risk and being able to " +
        "afford it are different things, and the second is the one that determines " +
        "what a bad year does to your life.");
    }
    if (horizon != null && horizon < 35 && tolerance != null && tolerance > 60) {
      tensions.push("You are comfortable with volatility, but you may need this money " +
        "within a few years. Time is what allows a market fall to recover; without " +
        "it, a fall and a loss become the same thing.");
    }
    if (capacity != null && capacity < 30) {
      tensions.push("Your answers suggest limited savings to fall back on. " +
        "Historically, an emergency reserve is what stops people from having to " +
        "sell investments at the worst possible moment.");
    }
    if (knowledge != null && knowledge < 35) {
      tensions.push("You described limited investing experience. That is not a " +
        "problem in itself - but it is a strong argument for understanding what " +
        "you own before committing money to it.");
    }

    return {
      complete: true, profile: name, summary: PROFILES[name].range,
      what_this_means: PROFILES[name].means,
      scores: {risk_tolerance: tolerance, risk_capacity: capacity,
               time_horizon: horizon, knowledge, overall},
      score_meaning: {
        risk_tolerance: "How comfortable you feel about losses and swings.",
        risk_capacity: "How much loss your finances could actually absorb.",
        time_horizon: "How long before you are likely to need the money.",
        knowledge: "How familiar you are with investing concepts.",
      },
      tensions,
      next_steps: [
        "Read the education section to understand the measures used on this site.",
        "Use the historical scenario tool to see how real EGX investments behaved, " +
        "including their worst falls.",
        "Use the Monte Carlo tool to see a range of possible outcomes rather than " +
        "a single expected number.",
      ],
      disclaimer: "This is an educational exercise, not advice. It does not know " +
        "your full circumstances, and it deliberately does not suggest what to buy, " +
        "sell, or how to split your money. Those decisions are yours, and a " +
        "licensed adviser can help with them.",
    };
  }

    return {api, post};
  })();
