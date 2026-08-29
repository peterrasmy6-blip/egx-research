/* EGX Research — client-side calculation engine.

   A direct port of the Python engine in backend/app/engine/. The site is served
   as static files, so these calculations run in the visitor's browser rather
   than on a server.

   The deterministic functions here (what-if, backtest, projections) are
   verified against the Python implementation to the cent by
   backend/tests/test_js_parity.py — a mismatch fails the build. Monte Carlo is
   stochastic and cannot be bit-identical across languages; it is checked for
   distributional agreement instead.

   Conventions carried over from Python, because getting them wrong is the
   classic source of bad numbers:
     close     - split-adjusted, NOT dividend-adjusted. What a buyer paid.
                 Used for share counts and price-only return.
     adj_close - split- AND dividend-adjusted. Used for total return and risk.
*/

const ENGINE = (() => {
  const TRADING_DAYS = 252;
  const DEFAULT_COST_RATE = 0.00175;
  const DEFAULT_INFLATION = 0.20;
  const MAX_ENTRY_ROLL_DAYS = 14;
  const EGP_RISK_FREE = 0.205;

  class InsufficientData extends Error {}

  /* ---------------- date helpers (UTC, to avoid timezone drift) ---------- */
  const toDays = iso => Date.parse(iso + "T00:00:00Z") / 86400000;
  const dayDiff = (a, b) => Math.round(toDays(a) - toDays(b));

  function addMonths(iso, n) {
    const [y, m, d] = iso.split("-").map(Number);
    const total = (y * 12 + (m - 1)) + n;
    const ny = Math.floor(total / 12);
    const nm = (total % 12) + 1;
    const nd = Math.min(d, 28);
    return `${ny}-${String(nm).padStart(2, "0")}-${String(nd).padStart(2, "0")}`;
  }

  /* ---------------- price series access --------------------------------- */
  /** Index of the first day on or after `iso`, or -1. */
  function idxOnOrAfter(days, iso) {
    let lo = 0, hi = days.length - 1, ans = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (days[mid] >= iso) { ans = mid; hi = mid - 1; } else lo = mid + 1;
    }
    return ans;
  }

  /** Index of the last day on or before `iso`, or -1. */
  function idxOnOrBefore(days, iso) {
    let lo = 0, hi = days.length - 1, ans = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (days[mid] <= iso) { ans = mid; lo = mid + 1; } else hi = mid - 1;
    }
    return ans;
  }

  /* ---------------- statistics ------------------------------------------ */
  function dailyReturns(values) {
    const out = [];
    for (let i = 1; i < values.length; i++) {
      const prev = values[i - 1];
      if (prev && prev > 0) out.push(values[i] / prev - 1);
    }
    return out;
  }

  function annualisedVolatility(rets) {
    const n = rets.length;
    if (n < 20) return null;               // too short to mean anything
    const mean = rets.reduce((a, b) => a + b, 0) / n;
    let ss = 0;
    for (const r of rets) ss += (r - mean) ** 2;
    return Math.sqrt(ss / (n - 1)) * Math.sqrt(TRADING_DAYS);
  }

  function cagr(startValue, endValue, years) {
    if (startValue <= 0 || endValue <= 0 || years <= 0) return null;
    if (years < 1) return null;            // annualising months overstates wildly
    return Math.pow(endValue / startValue, 1 / years) - 1;
  }

  function maxDrawdown(values) {
    if (values.length < 2) return null;
    let peak = values[0], worst = 0, peakI = 0, troughI = 0, curPeakI = 0;
    for (let i = 0; i < values.length; i++) {
      const v = values[i];
      if (v > peak) { peak = v; curPeakI = i; }
      if (peak > 0) {
        const dd = v / peak - 1;
        if (dd < worst) { worst = dd; peakI = curPeakI; troughI = i; }
      }
    }
    return {max_drawdown: worst, peak_index: peakI, trough_index: troughI};
  }

  function sharpeRatio(rets, rf) {
    const n = rets.length;
    if (n < 20) return null;
    const meanA = (rets.reduce((a, b) => a + b, 0) / n) * TRADING_DAYS;
    const vol = annualisedVolatility(rets);
    if (!vol) return null;
    return (meanA - rf) / vol;
  }

  function sortinoRatio(rets, rf) {
    const n = rets.length;
    if (n < 20) return null;
    const meanA = (rets.reduce((a, b) => a + b, 0) / n) * TRADING_DAYS;
    const down = rets.filter(r => r < 0);
    if (down.length < 5) return null;
    let ss = 0;
    for (const r of down) ss += r * r;
    const dd = Math.sqrt(ss / down.length) * Math.sqrt(TRADING_DAYS);
    if (dd === 0) return null;
    return (meanA - rf) / dd;
  }

  const r2 = x => x == null ? null : Math.round(x * 100) / 100;
  const r4 = x => x == null ? null : Math.round(x * 10000) / 10000;

  /* ===================================================================== */
  /* Historical scenario: lump sum                                          */
  /* ===================================================================== */
  function lumpSum(co, amount, start, opts = {}) {
    const costRate = opts.cost_rate ?? DEFAULT_COST_RATE;
    const inflation = opts.inflation_annual ?? DEFAULT_INFLATION;
    const reinvest = !!opts.reinvest_dividends;

    if (amount <= 0) throw new InsufficientData("Investment amount must be greater than zero.");

    const {d, c, a} = co.prices;
    if (!d || !d.length) throw new InsufficientData(`No price history for ${co.ticker}.`);

    const ei = idxOnOrAfter(d, start);
    if (ei < 0) {
      throw new InsufficientData(
        `No trading data for ${co.ticker} on or after ${start}. The earliest ` +
        `price we hold is later than the date you chose.`);
    }
    // Rolling a weekend or holiday forward is fine; rolling forward by years
    // would answer a question the user did not ask.
    if (dayDiff(d[ei], start) > MAX_ENTRY_ROLL_DAYS) {
      throw new InsufficientData(
        `Our price history for ${co.ticker} only begins on ${d[ei]}, so we ` +
        `cannot say what would have happened if you invested on ${start}. ` +
        `Try a date on or after ${d[ei]}.`);
    }

    const end = opts.end || d[d.length - 1];
    let xi = idxOnOrBefore(d, end);
    if (xi < 0) xi = d.length - 1;
    if (xi <= ei) throw new InsufficientData("Not enough price history between those dates.");

    const entryDate = d[ei], exitDate = d[xi];
    const entryPrice = c[ei], exitPrice = c[xi];

    const costs = amount * costRate;
    const shares = (amount - costs) / entryPrice;

    let running = shares, dividendCash = 0;
    const events = [];
    for (const dv of (co.dividends || [])) {
      if (dv.ex_date <= entryDate || dv.ex_date > exitDate) continue;
      const payment = running * dv.amount;
      let reinvestedShares = 0;
      if (reinvest) {
        const pi = idxOnOrAfter(d, dv.ex_date);
        if (pi >= 0 && c[pi] > 0) { reinvestedShares = payment / c[pi]; running += reinvestedShares; }
        else dividendCash += payment;
      } else dividendCash += payment;
      events.push({date: dv.ex_date, per_share: dv.amount,
                   payment: r2(payment), reinvested_shares: r4(reinvestedShares)});
    }

    const marketValue = running * exitPrice;
    const finalValue = marketValue + dividendCash;
    const profit = finalValue - amount;
    const totalReturn = profit / amount;
    const priceOnly = exitPrice / entryPrice - 1;
    const years = dayDiff(exitDate, entryDate) / 365.25;

    const closes = c.slice(ei, xi + 1);
    const adj = a.slice(ei, xi + 1);
    const dd = maxDrawdown(closes);
    const vol = annualisedVolatility(dailyReturns(adj));

    const inflFactor = years > 0 ? Math.pow(1 + inflation, years) : 1;
    const realValue = finalValue / inflFactor;
    const realReturn = realValue / amount - 1;
    const cg = cagr(amount, finalValue, years);

    return {
      type: "lump_sum", ticker: co.ticker, name: co.name, currency: co.currency,
      requested_date: start, entry_date: entryDate,
      entry_date_adjusted: entryDate !== start, exit_date: exitDate,
      years_held: r2(years),
      amount_invested: r2(amount), transaction_costs: r2(costs),
      entry_price: r4(entryPrice), exit_price: r4(exitPrice),
      shares_bought: r4(shares), shares_final: r4(running),
      market_value: r2(marketValue), dividends_received: r2(dividendCash),
      dividends_reinvested: reinvest, dividend_events: events,
      final_value: r2(finalValue), profit: r2(profit),
      total_return_pct: r2(totalReturn * 100),
      price_only_return_pct: r2(priceOnly * 100),
      cagr_pct: cg == null ? null : r2(cg * 100),
      volatility_pct: vol ? r2(vol * 100) : null,
      max_drawdown_pct: dd ? r2(dd.max_drawdown * 100) : null,
      inflation_assumption_pct: r2(inflation * 100),
      real_value: r2(realValue), real_return_pct: r2(realReturn * 100),
      beat_inflation: realReturn > 0,
      assumptions: [
        `Bought at the closing price on ${entryDate}.`,
        `Transaction cost of ${(costRate * 100).toFixed(3)}% applied on purchase.`,
        `Dividends ${reinvest ? "reinvested at the closing price on the ex-date"
                              : "held as cash, not reinvested"}.`,
        "No tax has been applied.",
        `Inflation assumed at ${(inflation * 100).toFixed(1)}% per year to show ` +
        `purchasing power. This is an assumption, not measured data.`,
      ],
    };
  }

  /* ===================================================================== */
  /* Historical scenario: monthly plan                                      */
  /* ===================================================================== */
  function monthlyPlan(co, monthlyAmount, start, opts = {}) {
    const costRate = opts.cost_rate ?? DEFAULT_COST_RATE;
    const inflation = opts.inflation_annual ?? DEFAULT_INFLATION;
    const initial = opts.initial_amount || 0;

    if (monthlyAmount <= 0 && initial <= 0)
      throw new InsufficientData("Enter a monthly amount or a starting amount.");

    const {d, c} = co.prices;
    if (!d || !d.length) throw new InsufficientData(`No price history for ${co.ticker}.`);

    const fi = idxOnOrAfter(d, start);
    if (fi < 0) throw new InsufficientData(
      `No trading data for ${co.ticker} on or after ${start}.`);

    const end = opts.end || d[d.length - 1];
    let shares = 0, contributed = 0, costsTotal = 0;
    const purchases = [];

    if (initial > 0) {
      const cost = initial * costRate;
      shares += (initial - cost) / c[fi];
      contributed += initial; costsTotal += cost;
      purchases.push({date: d[fi], amount: initial, price: r4(c[fi])});
    }

    // Same month arithmetic as the Python implementation.
    const [sy, sm] = start.split("-").map(Number);
    const [ey, em] = end.split("-").map(Number);
    const nMonths = (ey - sy) * 12 + (em - sm);
    for (let m = 0; m <= nMonths; m++) {
      const buyDate = addMonths(start, m);
      if (buyDate > end) break;
      const pi = idxOnOrAfter(d, buyDate);
      if (pi < 0 || d[pi] > end) continue;
      const cost = monthlyAmount * costRate;
      shares += (monthlyAmount - cost) / c[pi];
      contributed += monthlyAmount; costsTotal += cost;
      purchases.push({date: d[pi], amount: monthlyAmount, price: r4(c[pi])});
    }

    if (!purchases.length)
      throw new InsufficientData("No purchase dates fell inside the available price history.");

    let xi = idxOnOrBefore(d, end);
    if (xi < 0) xi = d.length - 1;
    const exitDate = d[xi], exitPrice = c[xi];

    let dividendCash = 0;
    for (const dv of (co.dividends || [])) {
      if (dv.ex_date <= d[fi] || dv.ex_date > exitDate) continue;
      let held = 0;
      for (const p of purchases) {
        if (p.date <= dv.ex_date) held += p.amount * (1 - costRate) / p.price;
      }
      dividendCash += held * dv.amount;
    }

    const marketValue = shares * exitPrice;
    const finalValue = marketValue + dividendCash;
    const profit = finalValue - contributed;
    const years = dayDiff(exitDate, d[fi]) / 365.25;
    const inflFactor = years > 0 ? Math.pow(1 + inflation, years) : 1;

    return {
      type: "monthly_plan", ticker: co.ticker, name: co.name, currency: co.currency,
      start_date: d[fi], exit_date: exitDate, years: r2(years),
      n_purchases: purchases.length, monthly_amount: monthlyAmount,
      initial_amount: initial,
      total_contributed: r2(contributed), transaction_costs: r2(costsTotal),
      shares_final: r4(shares),
      average_cost_per_share: shares ? r4((contributed - costsTotal) / shares) : null,
      exit_price: r4(exitPrice), market_value: r2(marketValue),
      dividends_received: r2(dividendCash), final_value: r2(finalValue),
      profit: r2(profit),
      total_return_pct: contributed ? r2(profit / contributed * 100) : null,
      gain_from_contributions: r2(contributed), gain_from_returns: r2(profit),
      inflation_assumption_pct: r2(inflation * 100),
      real_value: r2(finalValue / inflFactor),
      purchases,
      assumptions: [
        `Bought once a month on (or just after) day ${Math.min(Number(start.split("-")[2]), 28)}.`,
        `Transaction cost of ${(costRate * 100).toFixed(3)}% applied on each purchase.`,
        "Dividends held as cash, not reinvested.",
        "No tax applied.",
        "Because money was added over time, a single annual growth rate is not " +
        "shown - each instalment was invested for a different length of time.",
      ],
    };
  }

  /* ===================================================================== */
  /* Portfolio backtest                                                     */
  /* ===================================================================== */
  function backtest(companies, holdings, start, opts = {}) {
    const costRate = opts.cost_rate ?? DEFAULT_COST_RATE;
    const riskFree = opts.risk_free ?? EGP_RISK_FREE;
    const initial = opts.initial ?? 100000;
    const monthly = opts.monthly ?? 0;
    const rebalance = opts.rebalance || "none";
    const reinvest = opts.reinvest_dividends !== false;

    if (!holdings.length) throw new InsufficientData("Select at least one security.");
    if (initial <= 0 && monthly <= 0)
      throw new InsufficientData("Enter a starting amount or a monthly amount.");

    const end = opts.end || null;
    const totalW = holdings.reduce((s, h) => s + (h.weight || 0), 0);
    if (totalW <= 0) throw new InsufficientData("Portfolio weights must add up to more than zero.");

    const secs = holdings.map(h => {
      const co = companies[h.ticker];
      if (!co) throw new InsufficientData(`We do not hold data for '${h.ticker}'.`);
      return {co, weight: h.weight / totalW};
    });

    // Shared trading calendar.
    const daySet = new Set();
    for (const s of secs) {
      const {d} = s.co.prices;
      s.map = new Map();
      for (let i = 0; i < d.length; i++) {
        if (d[i] < start) continue;
        if (end && d[i] > end) continue;
        s.map.set(d[i], s.co.prices.c[i]);
        daySet.add(d[i]);
      }
    }
    const days = [...daySet].sort();
    if (!days.length)
      throw new InsufficientData("No price history exists for those securities in that period.");

    for (const s of secs) {
      const first = [...s.map.keys()].sort()[0];
      if (!first) throw new InsufficientData(`${s.co.ticker} has no prices in that period.`);
      if (dayDiff(first, days[0]) > 30) {
        throw new InsufficientData(
          `${s.co.ticker} only has prices from ${first}, which is after your ` +
          `start date. Choose a later start date or remove it.`);
      }
      // Forward-fill across days the security did not trade.
      s.ff = new Map();
      let last = null;
      for (const day of days) {
        if (s.map.has(day)) last = s.map.get(day);
        if (last !== null) s.ff.set(day, last);
      }
      s.divs = new Map();
      for (const dv of (s.co.dividends || [])) {
        if (dv.ex_date >= days[0] && dv.ex_date <= days[days.length - 1])
          s.divs.set(dv.ex_date, dv.amount);
      }
      s.shares = 0;
    }

    let cash = 0, contributed = 0, costsTotal = 0, dividendsTotal = 0;

    const buy = (day, amount) => {
      const cost = amount * costRate;
      costsTotal += cost;
      const net = amount - cost;
      for (const s of secs) {
        const px = s.ff.get(day);
        if (px && px > 0) s.shares += (net * s.weight) / px;
      }
    };
    const portfolioValue = day => {
      let v = 0;
      for (const s of secs) { const px = s.ff.get(day); if (px) v += s.shares * px; }
      return v;
    };

    if (initial > 0) { buy(days[0], initial); contributed += initial; }

    const rebMonths = {monthly: 1, quarterly: 3, annual: 12}[rebalance] || null;
    const series = [], contribSeries = [];
    let lastMonth = days[0].slice(0, 7);
    let lastReb = days[0];

    for (const day of days) {
      for (const s of secs) {
        const amt = s.divs.get(day);
        if (amt && s.shares > 0) {
          const pay = s.shares * amt;
          dividendsTotal += pay;
          if (reinvest) {
            const px = s.ff.get(day);
            if (px && px > 0) s.shares += pay / px; else cash += pay;
          } else cash += pay;
        }
      }

      const ym = day.slice(0, 7);
      if (monthly > 0 && ym !== lastMonth) {
        buy(day, monthly); contributed += monthly; lastMonth = ym;
      }

      if (rebMonths) {
        const [ly, lm] = lastReb.split("-").map(Number);
        const [cy, cm] = day.split("-").map(Number);
        if ((cy - ly) * 12 + (cm - lm) >= rebMonths) {
          const v = portfolioValue(day);
          if (v > 0) {
            let turnover = 0;
            for (const s of secs) {
              const px = s.ff.get(day);
              if (!px || px <= 0) continue;
              turnover += Math.abs(v * s.weight - s.shares * px);
            }
            const fee = (turnover / 2) * costRate;
            costsTotal += fee;
            const vAfter = v - fee;
            for (const s of secs) {
              const px = s.ff.get(day);
              if (px && px > 0) s.shares = (vAfter * s.weight) / px;
            }
          }
          lastReb = day;
        }
      }

      series.push([day, portfolioValue(day) + cash]);
      contribSeries.push(contributed);
    }

    const values = series.map(x => x[1]);
    const final = values[values.length - 1];
    const profit = final - contributed;
    const years = dayDiff(days[days.length - 1], days[0]) / 365.25;
    const rets = dailyReturns(values);
    const vol = annualisedVolatility(rets);
    const dd = maxDrawdown(values);
    const cg = monthly === 0 ? cagr(contributed, final, years) : null;
    const twr = timeWeightedReturn(series, contribSeries);

    const byYear = {};
    for (const [day, v] of series) {
      const y = day.slice(0, 4);
      (byYear[y] = byYear[y] || []).push(v);
    }
    const yearly = {};
    for (const [y, vs] of Object.entries(byYear)) {
      if (vs.length > 1 && vs[0] > 0) yearly[y] = r2((vs[vs.length - 1] / vs[0] - 1) * 100);
    }
    const yearEntries = Object.entries(yearly);

    const sh = sharpeRatio(rets, riskFree), so = sortinoRatio(rets, riskFree);
    const step = Math.max(1, Math.floor(series.length / 400));
    const trimmed = [];
    for (let i = 0; i < series.length; i += step) {
      trimmed.push({d: series[i][0], v: r2(series[i][1]), c: r2(contribSeries[i])});
    }

    return {
      holdings: secs.map(s => ({ticker: s.co.ticker, name: s.co.name,
                                weight_pct: r2(s.weight * 100), sector: s.co.sector})),
      start_date: days[0], end_date: days[days.length - 1], years: r2(years),
      trading_days: days.length, initial, monthly, rebalance,
      reinvest_dividends: reinvest,
      total_contributed: r2(contributed), final_value: r2(final), profit: r2(profit),
      total_return_pct: contributed ? r2(profit / contributed * 100) : null,
      cagr_pct: cg == null ? null : r2(cg * 100),
      time_weighted_return_pct: twr == null ? null : r2(twr * 100),
      dividends_received: r2(dividendsTotal), transaction_costs: r2(costsTotal),
      volatility_pct: vol ? r2(vol * 100) : null,
      max_drawdown_pct: dd ? r2(dd.max_drawdown * 100) : null,
      recovery_days: recoveryDays(series, dd),
      sharpe: sh == null ? null : r2(sh), sortino: so == null ? null : r2(so),
      risk_free_used_pct: Math.round(riskFree * 1000) / 10,
      best_year: yearEntries.length ? yearEntries.reduce((a, b) => b[1] > a[1] ? b : a) : null,
      worst_year: yearEntries.length ? yearEntries.reduce((a, b) => b[1] < a[1] ? b : a) : null,
      yearly_returns: yearly,
      series: trimmed,
      assumptions: [
        "Bought at closing prices; no intraday timing.",
        `Transaction cost of ${(costRate * 100).toFixed(3)}% on every purchase and on rebalancing trades.`,
        `Dividends ${reinvest ? "reinvested" : "held as cash"}.`,
        `Rebalancing: ${rebalance !== "none" ? rebalance : "never"}.`,
        `Risk-adjusted measures use an EGP risk-free rate of ${(riskFree * 100).toFixed(1)}%. ` +
        "This matters: with Egyptian deposit rates this high, a nominal gain can " +
        "still be a poor risk-adjusted result.",
        "No tax applied. Prices on non-trading days carry forward.",
        "Past performance does not indicate future results.",
      ],
    };
  }

  function timeWeightedReturn(series, contribs) {
    if (series.length < 2) return null;
    let factor = 1, prevV = series[0][1], prevC = contribs[0];
    for (let i = 1; i < series.length; i++) {
      const v = series[i][1];
      const flow = contribs[i] - prevC;
      const base = prevV + flow;
      if (base > 0) factor *= v / base;
      prevV = v; prevC = contribs[i];
    }
    const years = dayDiff(series[series.length - 1][0], series[0][0]) / 365.25;
    if (years <= 0 || factor <= 0) return null;
    return years >= 1 ? Math.pow(factor, 1 / years) - 1 : factor - 1;
  }

  function recoveryDays(series, dd) {
    if (!dd) return null;
    try {
      const peakV = series[dd.peak_index][1];
      const troughI = dd.trough_index, troughD = series[troughI][0];
      for (let i = troughI; i < series.length; i++) {
        if (series[i][1] >= peakV) return dayDiff(series[i][0], troughD);
      }
      return null;
    } catch (e) { return null; }
  }

  /* ===================================================================== */
  /* Portfolio composition                                                  */
  /* ===================================================================== */
  function analyseComposition(metrics, holdings) {
    const total = holdings.reduce((s, h) => s + (h.value || 0), 0);
    if (total <= 0) throw new InsufficientData("Portfolio values must be greater than zero.");

    const rows = [], bySector = {};
    for (const h of holdings) {
      const m = metrics[h.ticker.toUpperCase()];
      if (!m) continue;
      const w = h.value / total;
      const sector = m.sector || "Unclassified";
      bySector[sector] = (bySector[sector] || 0) + w;
      rows.push({ticker: h.ticker.toUpperCase(), name: m.name, sector,
                 value: r2(h.value), weight_pct: r2(w * 100)});
    }
    rows.sort((a, b) => b.weight_pct - a.weight_pct);
    const sectors = Object.entries(bySector)
      .map(([sector, w]) => ({sector, weight_pct: r2(w * 100)}))
      .sort((a, b) => b.weight_pct - a.weight_pct);

    let hhi = 0;
    for (const r of rows) hhi += (r.weight_pct / 100) ** 2;
    const effectiveN = hhi > 0 ? Math.round(10 / hhi) / 10 : null;

    const obs = [];
    if (rows.length && rows[0].weight_pct >= 30) {
      obs.push(`${rows[0].ticker} alone accounts for ${rows[0].weight_pct.toFixed(0)}% of ` +
        `this portfolio. When one holding is this large, the portfolio's result ` +
        `depends heavily on that single company.`);
    }
    if (sectors.length && sectors[0].weight_pct >= 50) {
      obs.push(`${sectors[0].weight_pct.toFixed(0)}% sits in ${sectors[0].sector}. ` +
        `Companies in the same sector tend to move together, so a sector-wide ` +
        `event affects most of the portfolio at once.`);
    }
    if (effectiveN != null && effectiveN < 3) {
      obs.push(`The portfolio behaves like roughly ${effectiveN.toFixed(1)} equally ` +
        `weighted holdings, which is a concentrated position.`);
    }
    if (rows.length >= 8 && effectiveN && effectiveN > 6) {
      obs.push(`Holdings are spread fairly evenly across ${rows.length} securities.`);
    }
    if (!obs.length) obs.push("No single holding or sector dominates this portfolio.");

    return {
      total_value: r2(total), holdings: rows, sectors,
      largest_holding_pct: rows.length ? rows[0].weight_pct : null,
      largest_sector_pct: sectors.length ? sectors[0].weight_pct : null,
      effective_holdings: effectiveN,
      observations: obs,
      note: "These are descriptive observations about what the portfolio contains. " +
            "They are not advice, and they do not take your personal circumstances " +
            "into account.",
    };
  }

  /* ===================================================================== */
  /* Forward scenarios                                                      */
  /* ===================================================================== */
  function scenarioProjection(initial, monthly, years, annualReturns,
                              inflation = DEFAULT_INFLATION, annualIncrease = 0) {
    if (years < 1 || years > 40) throw new InsufficientData("Choose a horizon between 1 and 40 years.");
    if (initial <= 0 && monthly <= 0) throw new InsufficientData("Enter a starting amount or a monthly amount.");

    const out = {};
    for (const [name, r] of Object.entries(annualReturns)) {
      let balance = initial, contributed = initial, contrib = monthly;
      const monthR = Math.pow(1 + r, 1 / 12) - 1;
      const path = [];
      for (let y = 1; y <= years; y++) {
        for (let i = 0; i < 12; i++) {
          balance = balance * (1 + monthR) + contrib;
          contributed += contrib;
        }
        contrib *= (1 + annualIncrease);
        const f = Math.pow(1 + inflation, y);
        path.push({year: y, nominal: r2(balance), real: r2(balance / f),
                   contributed: r2(contributed)});
      }
      out[name] = {
        annual_return_pct: r2(r * 100),
        final_nominal: r2(balance),
        final_real: r2(balance / Math.pow(1 + inflation, years)),
        total_contributed: r2(contributed),
        growth_from_returns: r2(balance - contributed),
        path,
      };
    }

    return {
      type: "scenario", years, initial, monthly,
      annual_contribution_increase_pct: r2(annualIncrease * 100),
      inflation_assumption_pct: r2(inflation * 100),
      scenarios: out,
      assumptions: [
        "Returns are assumed to be steady every year. Real markets are not " +
        "steady - they rise and fall, and the order matters.",
        "Contributions are added at the end of each month.",
        `Inflation of ${(inflation * 100).toFixed(1)}% a year is applied to show ` +
        "future purchasing power.",
        "No tax, fees or charges are deducted.",
      ],
      disclaimer: "These are arithmetic projections of the rates you chose. They " +
                  "are not forecasts and not a promise of any outcome.",
    };
  }

  /* ---- seeded generator so a reload never changes the "probabilities" --- */
  function mulberry32(seed) {
    let t = seed >>> 0;
    return function () {
      t = (t + 0x6D2B79F5) >>> 0;
      let r = Math.imul(t ^ (t >>> 15), 1 | t);
      r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }

  function gaussian(rand) {
    // Box-Muller; guard against log(0).
    let u = 0, v = 0;
    while (u === 0) u = rand();
    while (v === 0) v = rand();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  function monteCarlo(initial, monthly, years, annualReturn, annualVolatility,
                      opts = {}) {
    const simulations = opts.simulations ?? 5000;
    const inflation = opts.inflation ?? DEFAULT_INFLATION;
    const target = opts.target ?? null;
    const seed = opts.seed ?? 42;

    if (simulations < 100 || simulations > 20000)
      throw new InsufficientData("Choose between 100 and 20,000 simulations.");
    if (years < 1 || years > 40)
      throw new InsufficientData("Choose a horizon between 1 and 40 years.");
    if (annualVolatility <= 0)
      throw new InsufficientData("Volatility must be greater than zero.");

    const rand = mulberry32(seed);
    const months = years * 12;
    const sdM = annualVolatility / Math.sqrt(12);
    const muM = Math.log(1 + annualReturn) / 12 - 0.5 * sdM * sdM;

    const finals = [];
    const contributed = initial + monthly * months;
    const samplePaths = [];

    for (let i = 0; i < simulations; i++) {
      let bal = initial;
      const path = i < 40 ? [bal] : null;
      for (let m = 0; m < months; m++) {
        bal = bal * Math.exp(muM + sdM * gaussian(rand)) + monthly;
        if (path && (m + 1) % 12 === 0) path.push(bal);
      }
      finals.push(bal);
      if (path) samplePaths.push(path.map(x => r2(x)));
    }
    finals.sort((a, b) => a - b);

    const pct = p => finals[Math.min(finals.length - 1, Math.max(0, Math.floor(p * finals.length)))];
    const inflFactor = Math.pow(1 + inflation, years);

    // Both sides of the purchasing-power comparison must be in the same money:
    // a contribution made in year 10 is not worth its face value today.
    let realContributed = initial;
    for (let m = 1; m <= months; m++) realContributed += monthly / Math.pow(1 + inflation, m / 12);

    const lossCount = finals.filter(f => f < contributed).length;
    const realLossCount = finals.filter(f => f / inflFactor < realContributed).length;
    const targetCount = target ? finals.filter(f => f >= target).length : null;

    return {
      type: "monte_carlo", simulations, years, initial, monthly,
      total_contributed: r2(contributed),
      total_contributed_real: r2(realContributed),
      assumed_annual_return_pct: r2(annualReturn * 100),
      assumed_annual_volatility_pct: r2(annualVolatility * 100),
      inflation_assumption_pct: r2(inflation * 100),
      percentiles: {p10: r2(pct(0.10)), p25: r2(pct(0.25)), median: r2(pct(0.50)),
                    p75: r2(pct(0.75)), p90: r2(pct(0.90))},
      percentiles_real: {p10: r2(pct(0.10) / inflFactor),
                         median: r2(pct(0.50) / inflFactor),
                         p90: r2(pct(0.90) / inflFactor)},
      probability_of_loss_pct: Math.round(lossCount / simulations * 1000) / 10,
      probability_of_real_loss_pct: Math.round(realLossCount / simulations * 1000) / 10,
      real_loss_note:
        `Compares the final value in today's money against what you paid in, also ` +
        `expressed in today's money (EGP ${Math.round(realContributed).toLocaleString("en-US")}). ` +
        `Both sides are in the same money, which is the only way the comparison means anything.`,
      target,
      probability_of_target_pct: target ? Math.round(targetCount / simulations * 1000) / 10 : null,
      sample_paths: samplePaths.slice(0, 40),
      assumptions: [
        "Monthly returns are drawn at random from a bell-shaped distribution " +
        "built from the return and volatility you chose.",
        "Each month is assumed independent of the last.",
        "Contributions are added at the end of each month.",
        `Inflation of ${(inflation * 100).toFixed(1)}% a year is used for the ` +
        "purchasing-power figures.",
        "The same inputs always produce the same result.",
      ],
      limitations: [
        `A low chance of nominal loss is not reassurance. At ${(inflation * 100).toFixed(0)}% ` +
        "inflation, simply getting your pounds back is a large loss in what they " +
        "can buy - which is why the purchasing-power figure is shown next to it.",
        "Real markets have more extreme days than a bell curve predicts, and bad " +
        "months tend to cluster together. The genuine chance of a poor outcome is " +
        "therefore somewhat higher than shown here.",
        "The simulation assumes the chosen return and volatility hold for the " +
        "whole period. Neither is stable in reality.",
        "This is a model of the assumptions, not a forecast of the market.",
      ],
      disclaimer: "These probabilities describe the model, not the future. They " +
                  "are not a prediction and not advice.",
    };
  }

  /** Historical drift and volatility measured from a company's own prices. */
  function estimateParameters(co, lookbackYears = 5) {
    const {d, a} = co.prices;
    if (!d || d.length < 250)
      throw new InsufficientData(
        `Only ${d ? d.length : 0} trading days of history are available. At ` +
        `least 250 are needed before a simulation would mean anything.`);
    const cutoff = Math.max(0, d.length - lookbackYears * TRADING_DAYS);
    const adj = a.slice(cutoff), dates = d.slice(cutoff);
    const rets = dailyReturns(adj);
    if (rets.length < 250) throw new InsufficientData("Not enough return history to estimate risk.");
    const n = rets.length;
    const meanD = rets.reduce((x, y) => x + y, 0) / n;
    let ss = 0;
    for (const r of rets) ss += (r - meanD) ** 2;
    const sdD = Math.sqrt(ss / (n - 1));
    return {
      annual_return_historical: Math.pow(1 + meanD, TRADING_DAYS) - 1,
      annual_volatility: sdD * Math.sqrt(TRADING_DAYS),
      observations: n,
      years_of_history: Math.round(n / TRADING_DAYS * 10) / 10,
      period_start: dates[0], period_end: dates[dates.length - 1],
    };
  }

  return {
    InsufficientData, lumpSum, monthlyPlan, backtest, analyseComposition,
    scenarioProjection, monteCarlo, estimateParameters,
    dailyReturns, annualisedVolatility, cagr, maxDrawdown,
    sharpeRatio, sortinoRatio, idxOnOrAfter, idxOnOrBefore,
    DEFAULT_COST_RATE, DEFAULT_INFLATION, EGP_RISK_FREE,
  };
})();

/* =======================================================================
   PORTFOLIO FORECAST
   A port of backend/app/engine/portfolio_forecast.py +
   forecast_portfolio_run.py. Verified against the Python engine by the
   parity harness.

   The model in one line:
       expected return = income + growth + valuation change
   built per holding from what that company actually reports, then pulled
   toward the market-wide expected return so recent form is not projected
   forever. Risk uses real volatility and real correlations.
   ======================================================================= */
const FORECAST = (() => {
  const MAX_GROWTH_BLOCK = 0.25;
  const MAX_VALUATION_BLOCK = 0.10;
  const MAX_INCOME_BLOCK = 0.15;
  const MIN_EXPECTED = -0.05;
  const MAX_EXPECTED = 0.60;
  const MAX_SELF_WEIGHT = 0.65;
  const TD = 252;

  const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

  function marketExpected(ref) {
    const d = (ref && ref.valuation_defaults) || {};
    return (d.risk_free_rate ?? 0.205) + (d.equity_risk_premium ?? 0.055);
  }

  /** One holding's expected return, from the blocks it genuinely supports. */
  function expectedReturnFor(m, sectorMedianPe, ref) {
    const blocks = [], skipped = [];
    const market = marketExpected(ref);

    const dy = m.dividend_yield_pct;
    if (dy != null && dy > 0) {
      blocks.push({name: "Dividend income", value: clamp(dy / 100, 0, MAX_INCOME_BLOCK),
                   detail: `pays ${nf(dy, 2)}% a year in cash`});
    } else {
      skipped.push("no dividend, so no income contribution");
    }

    const g3 = m.revenue_cagr_3y_pct, g1 = m.earnings_growth_pct;
    const roe = m.roe_pct, ni = m.net_income;
    if (ni != null && ni <= 0) {
      skipped.push("loss-making, so earnings growth is not meaningful");
    } else {
      const cand = [g3, g1].filter(x => x != null);
      if (cand.length) {
        const g = Math.min(...cand) / 100;
        blocks.push({name: "Earnings growth", value: clamp(g * 0.5, -0.05, MAX_GROWTH_BLOCK),
                     detail: `grew ${nf(Math.min(...cand), 1)}% a year recently, halved ` +
                             `here because growth rarely persists at full rate`});
      } else if (roe != null && roe > 0) {
        const payout = clamp((dy || 0) / Math.max(roe, 1e-9), 0, 1);
        blocks.push({name: "Reinvested earnings",
                     value: clamp((roe / 100) * (1 - payout) * 0.5, -0.05, MAX_GROWTH_BLOCK),
                     detail: `estimated from a ${nf(roe, 1)}% return on equity`});
      } else {
        skipped.push("no usable growth or profitability history");
      }
    }

    const pe = m.pe;
    if (pe && sectorMedianPe && pe > 0 && sectorMedianPe > 0) {
      const annual = clamp(((sectorMedianPe / pe) - 1) / 5, -MAX_VALUATION_BLOCK, MAX_VALUATION_BLOCK);
      if (Math.abs(annual) > 0.002) {
        blocks.push({name: "Valuation change", value: annual,
                     detail: `on ${nf(pe, 1)}x earnings against a sector norm of ${nf(sectorMedianPe, 1)}x`});
      }
    } else {
      skipped.push("no comparable sector multiple, so no re-rating assumed");
    }

    const raw = blocks.reduce((s, b) => s + b.value, 0);
    const evidence = blocks.length ? clamp((m.statement_periods || 0) / 5, 0, 1) : 0;
    const selfW = MAX_SELF_WEIGHT * evidence;
    const expected = clamp(selfW * raw + (1 - selfW) * market, MIN_EXPECTED, MAX_EXPECTED);

    return {
      expected_return: expected,
      blocks: blocks.map(b => ({...b, value_pct: Math.round(b.value * 10000) / 100})),
      skipped,
      basis: `${Math.round(selfW * 100)}% from this company's own figures, ` +
             `${Math.round((1 - selfW) * 100)}% from the market-wide expected return`,
    };
  }

  /** Volatility per holding and the correlation matrix, from real prices. */
  function covariance(seriesByTicker) {
    const tickers = Object.keys(seriesByTicker);
    // Align on dates every holding shares.
    let common = null;
    for (const t of tickers) {
      const s = new Set(Object.keys(seriesByTicker[t]));
      common = common === null ? s : new Set([...common].filter(d => s.has(d)));
    }
    const days = [...(common || [])].sort();
    if (days.length < 61) return {vol: {}, corr: {}, n: days.length};

    const rets = {};
    for (const t of tickers) {
      const vals = days.map(d => seriesByTicker[t][d]);
      rets[t] = ENGINE.dailyReturns(vals);
    }
    const n = Math.min(...tickers.map(t => rets[t].length));
    if (n < 60) return {vol: {}, corr: {}, n};

    const mean = {}, sd = {};
    for (const t of tickers) {
      const a = rets[t].slice(0, n);
      mean[t] = a.reduce((x, y) => x + y, 0) / n;
      sd[t] = Math.sqrt(a.reduce((s, r) => s + (r - mean[t]) ** 2, 0) / (n - 1));
    }
    const vol = {}, corr = {};
    for (const t of tickers) vol[t] = sd[t] * Math.sqrt(TD);
    for (const a of tickers) {
      corr[a] = {};
      for (const b of tickers) {
        if (a === b) { corr[a][b] = 1; continue; }
        let cov = 0;
        for (let i = 0; i < n; i++) cov += (rets[a][i] - mean[a]) * (rets[b][i] - mean[b]);
        cov /= (n - 1);
        corr[a][b] = (sd[a] > 0 && sd[b] > 0) ? cov / (sd[a] * sd[b]) : 0;
      }
    }
    return {vol, corr, n};
  }

  function portfolioRisk(weights, vol, corr) {
    const ts = Object.keys(weights).filter(t => vol[t] != null);
    if (!ts.length) return null;
    let v = 0;
    for (const a of ts) for (const b of ts) {
      const c = (corr[a] && corr[a][b] != null) ? corr[a][b] : (a === b ? 1 : 0);
      v += weights[a] * weights[b] * vol[a] * vol[b] * c;
    }
    return v > 0 ? Math.sqrt(v) : null;
  }

  return {expectedReturnFor, covariance, portfolioRisk, marketExpected,
          MIN_EXPECTED, MAX_EXPECTED};
})();
