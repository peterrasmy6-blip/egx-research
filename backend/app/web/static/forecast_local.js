/* Portfolio forecast for the static build.

   Mirrors backend/app/engine/forecast_portfolio_run.py. Because there is no
   backend, this runs in the browser: it reads the pre-built metrics, and loads
   each holding's price series so the correlations between them are measured
   from real data rather than assumed.

   Exposed as a global so the data layer in api.js can dispatch to it.
*/

async function forecastPortfolioLocal(body, deps) {
  const {loadJSON, loadCompany, loadMetrics, DATA, ApiError} = deps;

  const ref = await loadJSON(DATA + "/reference.json");
  const metrics = await loadMetrics();
  const medians = ref.sector_medians || {};

  const holdings = (body.holdings || []).filter(h => (h.weight || 0) > 0);
  if (!holdings.length) throw new ApiError("Add at least one holding.");

  const years = body.years;
  const inflation = (body.inflation_pct || 0) / 100;
  const initial = body.initial || 0;
  const monthly = body.monthly || 0;
  const sims = body.simulations || 5000;

  if (years < 1 || years > 30)
    throw new ApiError("Choose a holding period between 1 and 30 years.");
  if (initial <= 0 && monthly <= 0)
    throw new ApiError("Enter a starting amount or a monthly amount.");

  const totalW = holdings.reduce((s, h) => s + h.weight, 0);
  if (totalW <= 0) throw new ApiError("Weights must add up to more than zero.");

  const weights = {}, details = [], seriesByTicker = {};

  for (const h of holdings) {
    const tk = String(h.ticker).toUpperCase();

    // Funds are checked first and by name, because they have no metrics row --
    // otherwise a fund produced the unhelpful "we do not hold data" message
    // rather than explaining why funds cannot be forecast.
    if (tk.startsWith("FUND-")) {
      const fund = (typeof UNIVERSE !== "undefined")
        ? UNIVERSE.find(u => u.ticker === tk) : null;
      throw new ApiError(
        (fund ? fund.name : tk) + " is an investment fund. Funds cannot be " +
        "forecast here: our free source publishes their current value but no " +
        "history of daily values, and without that history there is nothing " +
        "to measure risk from. Shares have full histories and can be forecast.");
    }

    const m = metrics[tk];
    if (!m) throw new ApiError("We do not hold data for '" + tk + "'.");
    if (m.price == null)
      throw new ApiError("We have no usable price history for " + tk + ".");

    weights[tk] = h.weight / totalW;

    const co = await loadCompany(tk);
    const cutoff = new Date(Date.now() - 3 * 365 * 86400000)
      .toISOString().slice(0, 10);
    const map = {};
    for (let i = 0; i < co.prices.d.length; i++) {
      if (co.prices.d[i] >= cutoff) map[co.prices.d[i]] = co.prices.a[i];
    }
    seriesByTicker[tk] = map;

    const med = (medians[m.sector || ""] || {}).pe;
    const er = FORECAST.expectedReturnFor(m, med, ref);
    details.push({
      ticker: tk, name: m.name, sector: m.sector,
      weight_pct: Math.round(weights[tk] * 10000) / 100,
      price: m.price,
      expected_return_pct: Math.round(er.expected_return * 10000) / 100,
      blocks: er.blocks, skipped: er.skipped, basis: er.basis,
      volatility_pct: m.volatility_pct, max_drawdown_pct: m.max_drawdown_pct,
      pe: m.pe, roe_pct: m.roe_pct, dividend_yield_pct: m.dividend_yield_pct,
      data_quality: m.data_quality,
    });
  }

  const mu = details.reduce(
    (s, d) => s + weights[d.ticker] * d.expected_return_pct / 100, 0);

  const cov = FORECAST.covariance(seriesByTicker);
  const vol = cov.vol, corr = cov.corr;
  let sigma = FORECAST.portfolioRisk(weights, vol, corr);
  let riskNote = null;
  if (!sigma) {
    sigma = details.reduce(
      (s, d) => s + weights[d.ticker] * (d.volatility_pct || 30) / 100, 0) || 0.30;
    riskNote = "There is not enough overlapping price history to measure how " +
      "these holdings move together, so the risk figure is an approximation. " +
      "A portfolio of similar companies is probably riskier than it suggests.";
  }

  const wAvgVol = Object.keys(weights)
    .reduce((s, t) => s + weights[t] * (vol[t] || 0), 0);
  const diversification = (wAvgVol > 0 && sigma < wAvgVol)
    ? Math.round((1 - sigma / wAvgVol) * 1000) / 10 : null;

  // Seeded so a reload never changes the "probabilities".
  let seed = 42 >>> 0;
  const rand = () => {
    seed = (seed + 0x6D2B79F5) >>> 0;
    let r = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
  const gauss = () => {
    let u = 0, v = 0;
    while (u === 0) u = rand();
    while (v === 0) v = rand();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };

  const months = years * 12;
  const sdM = sigma / Math.sqrt(12);
  const muM = mu > -0.99 ? Math.log(1 + mu) / 12 - 0.5 * sdM * sdM : -0.01;

  const finals = [], paths = [];
  const contributed = initial + monthly * months;
  for (let i = 0; i < sims; i++) {
    let bal = initial;
    const path = i < 40 ? [Math.round(bal * 100) / 100] : null;
    for (let k = 0; k < months; k++) {
      bal = bal * Math.exp(muM + sdM * gauss()) + monthly;
      if (path && (k + 1) % 12 === 0) path.push(Math.round(bal * 100) / 100);
    }
    finals.push(bal);
    if (path) paths.push(path);
  }
  finals.sort((a, b) => a - b);
  const q = p => finals[Math.min(finals.length - 1,
                                 Math.max(0, Math.floor(p * finals.length)))];

  const inflFactor = Math.pow(1 + inflation, years);
  let realContributed = initial;
  for (let k = 1; k <= months; k++) {
    realContributed += monthly / Math.pow(1 + inflation, k / 12);
  }

  const pathAt = rate => {
    let bal = initial;
    const out = [];
    const mr = Math.pow(1 + rate, 1 / 12) - 1;
    for (let y = 1; y <= years; y++) {
      for (let j = 0; j < 12; j++) bal = bal * (1 + mr) + monthly;
      out.push({year: y, value: Math.round(bal * 100) / 100,
                real: Math.round(bal / Math.pow(1 + inflation, y) * 100) / 100});
    }
    return out;
  };

  // The cone width comes from the portfolio's own volatility, so a risky mix
  // genuinely shows a wider spread than a steady one.
  const conservative = Math.max(FORECAST.MIN_EXPECTED, mu - sigma * 0.75);
  const optimistic = mu + sigma * 0.75;
  const median = q(0.50);
  const drawdowns = details.map(d => d.max_drawdown_pct).filter(x => x != null);
  const r2 = x => Math.round(x * 100) / 100;

  return {
    holdings: details, years, initial, monthly,
    total_contributed: r2(contributed),
    total_contributed_real: r2(realContributed),
    expected_return_pct: r2(mu * 100),
    volatility_pct: r2(sigma * 100),
    diversification_benefit_pct: diversification,
    risk_note: riskNote,
    correlations: Object.keys(corr).length
      ? Object.fromEntries(Object.entries(corr).map(([a, row]) =>
          [a, Object.fromEntries(Object.entries(row).map(([b, v]) => [b, r2(v)]))]))
      : null,
    scenarios: {
      conservative: {annual_return_pct: r2(conservative * 100),
                     final: r2(pathAt(conservative).slice(-1)[0].value),
                     path: pathAt(conservative)},
      base: {annual_return_pct: r2(mu * 100),
             final: r2(pathAt(mu).slice(-1)[0].value),
             path: pathAt(mu)},
      optimistic: {annual_return_pct: r2(optimistic * 100),
                   final: r2(pathAt(optimistic).slice(-1)[0].value),
                   path: pathAt(optimistic)},
    },
    percentiles: {p10: r2(q(0.10)), p25: r2(q(0.25)), median: r2(median),
                  p75: r2(q(0.75)), p90: r2(q(0.90))},
    percentiles_real: {p10: r2(q(0.10) / inflFactor),
                       median: r2(median / inflFactor),
                       p90: r2(q(0.90) / inflFactor)},
    projected_value: r2(median),
    projected_profit: r2(median - contributed),
    projected_profit_pct: contributed ? r2((median / contributed - 1) * 100) : null,
    probability_of_loss_pct:
      Math.round(finals.filter(f => f < contributed).length / sims * 1000) / 10,
    probability_of_real_loss_pct:
      Math.round(finals.filter(f => f / inflFactor < realContributed).length
                 / sims * 1000) / 10,
    worst_historical_drawdown_pct: drawdowns.length ? Math.min(...drawdowns) : null,
    sample_paths: paths.slice(0, 40),
    simulations: sims,
    inflation_assumption_pct: r2(inflation * 100),
    method: "Each holding's expected return is built from what it actually " +
      "reports — the dividend it pays, how fast its earnings have grown, and " +
      "how its valuation compares with its sector — then pulled toward the " +
      "market-wide expected return so recent form is not projected forever. " +
      "Risk uses each holding's real volatility and the real correlations " +
      "between them.",
    assumptions: [
      "Expected returns are estimates built from past figures, not forecasts.",
      "Recent earnings growth is halved, because it rarely persists at full rate.",
      "Valuation is assumed to drift toward the sector norm over five years.",
      "Risk is measured from up to three years of daily prices.",
      "Returns are treated as independent month to month; real markets have " +
      "runs of bad months, so the true chance of a poor outcome is somewhat " +
      "higher than shown.",
      "Inflation of " + (inflation * 100).toFixed(1) + "% a year is used for " +
      "purchasing-power figures.",
      "No tax, dealing costs or rebalancing are included.",
    ],
    disclaimer: "This is a model, not a prediction. It shows what the stated " +
      "assumptions imply, and those assumptions can be wrong. Real results " +
      "will differ, possibly by a wide margin. Nothing here is advice or a " +
      "recommendation to buy anything.",
  };
}
