/* EGX Research — tool pages: scenario, screener, compare, backtest,
   forecast, portfolio, education. */

/* =======================================================================
   WHAT IF I HAD INVESTED?
   ======================================================================= */
function viewScenario(view, args) {
  const preset = (args && args[0]) ? decodeURIComponent(args[0]) : "COMI";
  const d = new Date(); d.setFullYear(d.getFullYear() - 5);
  const today = new Date().toISOString().slice(0, 10);

  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>What if I had invested?</h2>
      <p>Using real historical prices, real dividend payments and realistic
         trading costs. Nothing here is simulated or estimated.</p>
    </div>

    <div class="card">
      <div class="ranges" id="sc-mode">
        <button class="range on" data-m="lump">One-off investment</button>
        <button class="range" data-m="monthly">Every month</button>
      </div>

      <div id="sc-form" style="margin-top:18px">
        <div class="form-row">
          <div class="field"><label id="sc-amt-label">I invest</label>
            <div class="input-money"><span class="prefix">EGP</span>
              <input id="sc-amount" type="number" value="100000" min="100" step="1000"></div></div>
          <div class="field"><label>in</label>${tickerSelect("sc-ticker", preset)}</div>
          <div class="field"><label>starting on</label>
            <input id="sc-date" type="date" value="${d.toISOString().slice(0, 10)}" max="${today}"></div>
          <div class="field field-btn"><button class="btn" onclick="runScenario()">Calculate</button></div>
        </div>
        <div class="form-row" style="margin-top:12px">
          <div class="field"><label>Assumed inflation (per year)</label>
            <input id="sc-infl" type="number" value="20" min="0" max="60" step="1"></div>
          <div class="field" id="sc-initial-wrap" style="display:none">
            <label>Starting amount (optional)</label>
            <div class="input-money"><span class="prefix">EGP</span>
              <input id="sc-initial" type="number" value="0" min="0" step="1000"></div></div>
        </div>
        <label class="check" id="sc-reinvest-wrap">
          <input id="sc-reinvest" type="checkbox">
          <span>Reinvest dividends back into the shares</span></label>
      </div>

      <div class="chips" style="margin-top:16px">
        <span class="muted" style="font-size:13px;align-self:center">Quick dates:</span>
        ${[["1 year", 1], ["3 years", 3], ["5 years", 5], ["10 years", 10]].map(([l, y]) =>
          `<button class="chip" onclick="setScenarioYears(${y})">${l} ago</button>`).join("")}
      </div>

      <div id="sc-result"></div>
    </div>`;

  document.querySelectorAll("#sc-mode .range").forEach(b => b.onclick = () => {
    document.querySelectorAll("#sc-mode .range").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    const monthly = b.dataset.m === "monthly";
    document.getElementById("sc-amt-label").textContent = monthly ? "I invest each month" : "I invest";
    document.getElementById("sc-amount").value = monthly ? 5000 : 100000;
    document.getElementById("sc-initial-wrap").style.display = monthly ? "" : "none";
    document.getElementById("sc-reinvest-wrap").style.display = monthly ? "none" : "";
    document.getElementById("sc-result").innerHTML = "";
  });
}

function setScenarioYears(y) {
  const d = new Date(); d.setFullYear(d.getFullYear() - y);
  document.getElementById("sc-date").value = d.toISOString().slice(0, 10);
  runScenario();
}

async function runScenario() {
  const box = document.getElementById("sc-result");
  const monthly = document.querySelector("#sc-mode .range.on").dataset.m === "monthly";
  const btn = document.querySelector("#sc-form .btn");
  btn.disabled = true; btn.textContent = "Working…";
  box.innerHTML = "";
  try {
    const common = {
      ticker: pickerValue("sc-ticker"),
      start: document.getElementById("sc-date").value,
      inflation_annual: (+document.getElementById("sc-infl").value || 0) / 100,
    };
    if (monthly) {
      const r = await post("/api/scenario/monthly", {
        ...common,
        monthly_amount: +document.getElementById("sc-amount").value,
        initial_amount: +document.getElementById("sc-initial").value || 0,
      });
      renderMonthly(r, box);
    } else {
      const r = await post("/api/scenario/lumpsum", {
        ...common,
        amount: +document.getElementById("sc-amount").value,
        reinvest_dividends: document.getElementById("sc-reinvest").checked,
      });
      renderLump(r, box);
    }
  } catch (e) {
    box.innerHTML = `<div style="margin-top:22px"><div class="error">${esc(e.message)}</div></div>`;
  } finally { btn.disabled = false; btn.textContent = "Calculate"; }
}

function renderLump(r, box) {
  const up = r.profit >= 0;
  const infl = r.beat_inflation
    ? `Your money grew faster than prices rose. In today's purchasing power it is
       worth about <strong>${egp(r.real_value)}</strong> — a real gain of ${pct(r.real_return_pct)}.`
    : `Although the number went up, prices rose faster. In real purchasing power your
       ${egp(r.amount_invested)} is worth about <strong>${egp(r.real_value)}</strong> —
       you would be able to buy <strong>less</strong> than when you started.`;

  box.innerHTML = `
    <div style="margin-top:26px;padding-top:24px;border-top:1px solid var(--line)">
      ${r.entry_date_adjusted ? `<div class="callout">The market was closed on
        ${esc(r.requested_date)}, so this assumes you bought on
        <strong>${esc(r.entry_date)}</strong>, the next trading day.</div>` : ""}

      <p style="font-size:15px;color:var(--ink-2);line-height:1.65;margin:0 0 18px">
        If you had put <strong style="color:var(--ink)">${egp(r.amount_invested)}</strong> into
        <strong style="color:var(--ink)">${esc(r.name)}</strong> on
        <strong style="color:var(--ink)">${esc(r.entry_date)}</strong>, you would have bought about
        <strong style="color:var(--ink)">${nf(r.shares_bought)}</strong> shares at ${price(r.entry_price)} each.
        Today those shares are worth <strong style="color:var(--ink)">${egp(r.market_value)}</strong>${
          r.dividends_received > 0 ? `, and you would also have collected
          <strong style="color:var(--ink)">${egp(r.dividends_received)}</strong> in dividends` : ""}.
      </p>

      <div class="k">Total value today</div>
      <p class="big-num ${cls(r.profit)}">${egp(r.final_value)}</p>
      <p style="font-size:15px;color:var(--ink-2);margin:6px 0 0">
        A ${up ? "gain" : "loss"} of <strong style="color:var(--ink)">${egp(Math.abs(r.profit))}</strong>
        — ${pct(r.total_return_pct)} over ${num(r.years_held, 1)} years.</p>
      <div style="margin-top:12px">${shareCardButton("sc-lump")}</div>

      <div class="stats">
        <div class="stat"><div class="k">Total return</div>
          <div class="v ${cls(r.total_return_pct)}">${pct(r.total_return_pct)}</div>
          <div class="note">price + dividends</div></div>
        <div class="stat"><div class="k">Share price only</div>
          <div class="v ${cls(r.price_only_return_pct)}">${pct(r.price_only_return_pct)}</div>
          <div class="note">excluding dividends</div></div>
        ${r.cagr_pct != null ? `<div class="stat"><div class="k">Per year</div>
          <div class="v ${cls(r.cagr_pct)}">${pct(r.cagr_pct)}</div>
          <div class="note">average yearly growth</div></div>` : ""}
        <div class="stat"><div class="k">Dividends</div>
          <div class="v">${egp(r.dividends_received)}</div>
          <div class="note">cash paid to you</div></div>
        ${r.max_drawdown_pct != null ? `<div class="stat"><div class="k">Worst fall</div>
          <div class="v down">${pctPlain(r.max_drawdown_pct)}</div>
          <div class="note">biggest drop along the way</div></div>` : ""}
        ${r.volatility_pct != null ? `<div class="stat"><div class="k">Bumpiness</div>
          <div class="v">${pctPlain(r.volatility_pct)}</div>
          <div class="note">how much it swung</div></div>` : ""}
      </div>

      <div class="callout"><strong>After inflation.</strong> ${infl}
        This assumes prices rose ${pctPlain(r.inflation_assumption_pct)} a year —
        an assumption, not measured data.</div>

      <div class="chart-box"><canvas id="sc-chart"></canvas></div>
      ${assumptionsBlock(r.assumptions)}
    </div>`;

  drawScenarioChart(r);

  // A shareable card. What travels otherwise is a screenshot of one big
  // number with none of the assumptions that make it honest — so the card
  // carries the period, the dividends, the real-terms figure and the source.
  const scBtn = document.getElementById("sc-lump");
  if (scBtn) scBtn.onclick = () => downloadShareCard(
    `egx-${r.ticker}-what-if.png`, {
      eyebrow: "What if I had invested?",
      headline: `${egp(r.amount_invested)} in ${r.name} in ${String(r.entry_date).slice(0, 4)}`
        + ` would be ${egp(r.final_value)} today`,
      figures: [
        {label: "Total return", value: pct(r.total_return_pct),
         tone: r.total_return_pct >= 0 ? "up" : "down"},
        {label: "After inflation", value: pct(r.real_return_pct),
         tone: r.real_return_pct >= 0 ? "up" : "down"},
        {label: "Dividends collected", value: egp(r.dividends_received)},
      ],
      footnotes: [
        `Held ${num(r.years_held, 1)} years from ${r.entry_date}. Dividends `
        + `included and reinvested; dealing costs deducted.`,
        `"After inflation" assumes prices rose `
        + `${pctPlain(r.inflation_assumption_pct)} a year.`,
        "Past performance, calculated from real market data. It is not a "
        + "forecast and not advice.",
      ],
    });
}

async function drawScenarioChart(r) {
  try {
    const px = await api(`/api/security/${encodeURIComponent(r.ticker)}/prices?range=max`);
    const pts = px.points.filter(p => p.d >= r.entry_date && p.d <= r.exit_date);
    if (!pts.length) return;
    const base = pts[0].a;
    lineChart("sc-chart", pts.map(p => p.d), [{
      label: "Value of your investment",
      data: pts.map(p => r.amount_invested * (p.a / base)),
      borderColor: GREEN, borderWidth: 2, pointRadius: 0, tension: .12,
      backgroundColor: "rgba(11,107,94,.08)", fill: true,
    }], {title: "What your money was worth along the way"});
  } catch (e) {}
}

function renderMonthly(r, box) {
  box.innerHTML = `
    <div style="margin-top:26px;padding-top:24px;border-top:1px solid var(--line)">
      <p style="font-size:15px;color:var(--ink-2);line-height:1.65;margin:0 0 18px">
        Investing <strong style="color:var(--ink)">${egp(r.monthly_amount)}</strong> every month in
        <strong style="color:var(--ink)">${esc(r.name)}</strong> from
        <strong style="color:var(--ink)">${esc(r.start_date)}</strong> — that is
        ${count(r.n_purchases)} separate purchases totalling
        <strong style="color:var(--ink)">${egp(r.total_contributed)}</strong>.</p>

      <div class="k">Value today</div>
      <p class="big-num ${cls(r.profit)}">${egp(r.final_value)}</p>
      <p style="font-size:15px;color:var(--ink-2);margin:6px 0 0">
        You put in ${egp(r.total_contributed)} and it became ${egp(r.final_value)} —
        ${pct(r.total_return_pct)}.</p>

      <div class="stats">
        <div class="stat"><div class="k">You contributed</div><div class="v">${egp(r.total_contributed)}</div></div>
        <div class="stat"><div class="k">Investment gain</div>
          <div class="v ${cls(r.profit)}">${egp(r.profit)}</div></div>
        <div class="stat"><div class="k">Total return</div>
          <div class="v ${cls(r.total_return_pct)}">${pct(r.total_return_pct)}</div></div>
        <div class="stat"><div class="k">Average price paid</div>
          <div class="v">${price(r.average_cost_per_share)}</div>
          <div class="note">vs ${price(r.exit_price)} today</div></div>
        <div class="stat"><div class="k">Dividends</div><div class="v">${egp(r.dividends_received)}</div></div>
        <div class="stat"><div class="k">In today's money</div><div class="v">${egp(r.real_value)}</div>
          <div class="note">after ${pctPlain(r.inflation_assumption_pct)} inflation</div></div>
      </div>

      <div class="callout info"><strong>Why no "per year" figure?</strong>
        Each instalment was invested for a different length of time, so a single
        annual growth rate would be misleading. The total return above compares
        everything you put in with what you have now.</div>

      ${assumptionsBlock(r.assumptions)}
    </div>`;
}

/* =======================================================================
   SCREENER
   ======================================================================= */
let screenFilters = [];

async function viewScreener(view) {
  const f = await api("/api/screener/fields");
  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>Stock screener</h2>
      <p>Filter the whole Egyptian Exchange by value, quality, growth and risk.
         Companies missing a measure you filter on are excluded and counted, never
         silently treated as zero.</p>
    </div>

    <div class="card">
      <div class="form-row">
        <div class="field"><label>Measure</label>
          <select id="sf-field">${f.fields.map(x =>
            `<option value="${esc(x.field)}">${esc(x.label)}${x.unit ? " (" + esc(x.unit) + ")" : ""}</option>`).join("")}</select></div>
        <div class="field" style="max-width:150px"><label>Condition</label>
          <select id="sf-op">
            <option value="gte">at least</option>
            <option value="lte">at most</option>
          </select></div>
        <div class="field" style="max-width:150px"><label>Value</label>
          <input id="sf-value" type="number" value="15" step="any"></div>
        <div class="field field-btn"><button class="btn btn-ghost" onclick="addFilter()">Add filter</button></div>
      </div>

      <div class="chips" id="sf-active"></div>

      <div class="chips" style="margin-top:14px">
        <span class="muted" style="font-size:13px;align-self:center">Ready-made screens:</span>
        <button class="chip" onclick="presetScreen('quality')">Profitable &amp; growing</button>
        <button class="chip" onclick="presetScreen('value')">Low valuation</button>
        <button class="chip" onclick="presetScreen('income')">Dividend payers</button>
        <button class="chip" onclick="presetScreen('stable')">Lower volatility</button>
      </div>

      ${(f.withheld || []).length ? `<div class="callout" style="margin-top:16px">
        <strong>One measure is deliberately not here.</strong>
        ${f.withheld.map(w => esc(w.reason)).join(" ")}</div>` : ""}

      <div class="form-row" style="margin-top:16px">
        <div class="field"><label>Sort by</label>
          <select id="sf-sort">${f.fields.map(x =>
            `<option value="${esc(x.field)}"${x.field === "market_cap" ? " selected" : ""}>${esc(x.label)}</option>`).join("")}</select></div>
        <div class="field field-btn"><button class="btn" onclick="runScreen()">Run screen</button></div>
      </div>
    </div>

    <div id="sf-results"></div>`;
  renderFilterChips();
  runScreen();
}

function addFilter() {
  const field = document.getElementById("sf-field").value;
  const op = document.getElementById("sf-op").value;
  const value = parseFloat(document.getElementById("sf-value").value);
  if (isNaN(value)) return;
  screenFilters.push({field, op, value});
  renderFilterChips();
}
function removeFilter(i) { screenFilters.splice(i, 1); renderFilterChips(); }

function renderFilterChips() {
  const el = document.getElementById("sf-active");
  if (!el) return;
  const labels = {gte: "≥", lte: "≤"};
  el.innerHTML = screenFilters.length
    ? screenFilters.map((f, i) => `<button class="chip on" onclick="removeFilter(${i})">
        ${esc(f.field.replace(/_pct$/, "").replace(/_/g, " "))} ${labels[f.op] || f.op} ${f.value}
        <span class="x">×</span></button>`).join("")
    : `<span class="muted" style="font-size:13px">No filters — showing the whole exchange.</span>`;
}

function presetScreen(kind) {
  const presets = {
    quality: [{field: "roe_pct", op: "gte", value: 15},
              {field: "net_margin_pct", op: "gte", value: 8},
              {field: "revenue_growth_pct", op: "gte", value: 5}],
    value: [{field: "pe", op: "lte", value: 10}, {field: "pb", op: "lte", value: 2}],
    income: [{field: "dividend_yield_pct", op: "gte", value: 4}],
    stable: [{field: "volatility_pct", op: "lte", value: 35}],
  };
  screenFilters = presets[kind] || [];
  renderFilterChips();
  runScreen();
}

async function runScreen() {
  const box = document.getElementById("sf-results");
  box.innerHTML = `<div class="spinner">Screening…</div>`;
  try {
    const r = await post("/api/screener", {
      filters: screenFilters,
      sort_by: document.getElementById("sf-sort").value,
      descending: true, limit: 150,
    });
    const cols = [
      ["ticker", "Ticker"], ["name", "Company"], ["price", "Price"],
      ["pe", "P/E"], ["pb", "P/B"], ["roe_pct", "ROE"],
      ["net_margin_pct", "Net margin"], ["dividend_yield_pct", "Yield"],
      ["revenue_growth_pct", "Rev growth"], ["ret_1y", "1 year"],
      ["market_cap", "Market value"],
    ];
    const cell = (row, key) => {
      const v = row[key];
      if (key === "ticker") return `<td class="tk">${esc(v)}</td>`;
      if (key === "name") return `<td style="text-align:left;max-width:210px;overflow:hidden;text-overflow:ellipsis">${esc(v)}</td>`;
      if (key === "market_cap") return `<td>${bigMoney(v)}</td>`;
      if (key === "price") return `<td>${price(v)}</td>`;
      if (key.endsWith("_pct") || key === "ret_1y")
        return `<td class="${cls(key === "ret_1y" || key === "revenue_growth_pct" ? v : null)}">${v != null ? nf(v, 1) + "%" : "—"}</td>`;
      return `<td>${v != null ? nf(v, 2) : "—"}</td>`;
    };

    box.innerHTML = `<div class="card">
      <p style="margin:0 0 6px;font-size:14px">
        <strong>${count(r.count)}</strong> of ${count(r.universe_size)} companies match${r.count > r.returned ? `, showing the first ${count(r.returned)}` : ""}.</p>
      ${r.note ? `<div class="callout"><strong>Excluded for missing data:</strong> ${esc(r.note)}</div>` : ""}
      ${r.results.length ? `<div class="table-scroll"><table class="tbl">
        <thead><tr>${cols.map(([k, l]) =>
          `<th${k === "name" ? ' style="text-align:left"' : ""}>${esc(l)}</th>`).join("")}</tr></thead>
        <tbody>${r.results.map(row => `<tr onclick="go('/stock/${esc(row.ticker)}')">
          ${cols.map(([k]) => cell(row, k)).join("")}</tr>`).join("")}</tbody>
      </table></div>` : `<p class="muted">No company matches every filter. Try relaxing one.</p>`}
      ${r.results.length ? `<div style="margin-top:12px">${csvButton("scr-csv", "Download these results")}</div>` : ""}
      <p class="disclaim">A screen is a starting point for research, not a
        recommendation. Passing a numeric filter tells you nothing about whether a
        business is sound.</p>
    </div>`;

    const csvBtn = document.getElementById("scr-csv");
    if (csvBtn) csvBtn.onclick = () => downloadCSV(
      "egx-screen.csv", r.results,
      cols.map(([k, l]) => ({label: l, key: k}))
        .concat([{label: "Liquidity", key: "liquidity_band"},
                 {label: "Days traded of last 90", key: "days_traded_90d"},
                 {label: "Avg daily value traded (EGP)", key: "adtv_90d"}]));
  } catch (e) {
    box.innerHTML = `<div class="card"><div class="error">${esc(e.message)}</div></div>`;
  }
}

/* =======================================================================
   COMPARE
   ======================================================================= */
let cmpList = [];

function viewCompare(view, args) {
  if (args && args[0]) {
    const t = decodeURIComponent(args[0]);
    if (!cmpList.includes(t)) cmpList.push(t);
  }
  if (!cmpList.length) cmpList = ["COMI", "HRHO"];

  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>Compare companies</h2>
      <p>Put up to six companies side by side on the same measures.</p>
    </div>
    <div class="card">
      <div class="form-row">
        <div class="field"><label>Add a company</label>${tickerSelect("cmp-add")}</div>
        <div class="field field-btn"><button class="btn btn-ghost" onclick="addCompare()">Add</button></div>
        <div class="field field-btn"><button class="btn" onclick="runCompare()">Compare</button></div>
      </div>
      <div class="chips" id="cmp-chips"></div>
    </div>
    <div id="cmp-results"></div>`;
  renderCmpChips();
  runCompare();
}

function addCompare() {
  const t = pickerValue("cmp-add");
  if (cmpList.includes(t)) return;
  if (cmpList.length >= 6) return;
  cmpList.push(t); renderCmpChips();
}
function removeCompare(i) { cmpList.splice(i, 1); renderCmpChips(); }
function renderCmpChips() {
  document.getElementById("cmp-chips").innerHTML = cmpList.map((t, i) =>
    `<button class="chip on" onclick="removeCompare(${i})">${esc(t)}<span class="x">×</span></button>`).join("");
}

async function runCompare() {
  const box = document.getElementById("cmp-results");
  if (cmpList.length < 2) {
    box.innerHTML = `<div class="card"><p class="muted">Add at least two companies.</p></div>`;
    return;
  }
  box.innerHTML = `<div class="spinner">Comparing…</div>`;
  try {
    const r = await api("/api/compare?tickers=" + encodeURIComponent(cmpList.join(",")));
    const fmt = (v, unit) => {
      if (v == null) return "—";
      if (unit === "EGP") return Math.abs(v) > 1e6 ? bigMoney(v) : price(v);
      if (unit === "%") return nf(v, 2) + "%";
      if (unit === "x") return mult(v);
      return nf(v, 2);
    };
    box.innerHTML = `<div class="card">
      <div class="table-scroll"><table class="tbl">
        <thead><tr><th style="text-align:left">Measure</th>
          ${r.companies.map(c => `<th>${esc(c.ticker)}</th>`).join("")}</tr></thead>
        <tbody>
          <tr><td style="color:var(--ink-3);font-size:12px">Company</td>
            ${r.companies.map(c => `<td style="font-size:12px;color:var(--ink-2);white-space:normal;max-width:150px">${esc(c.name.slice(0, 40))}</td>`).join("")}</tr>
          ${r.table.map(row => `<tr><td>${esc(row.label)}</td>
            ${r.companies.map(c => {
              const v = row.values[c.ticker];
              const isLead = row.leader === c.ticker;
              return `<td class="${isLead ? "lead" : ""}">${fmt(v, row.unit)}</td>`;
            }).join("")}</tr>`).join("")}
        </tbody></table></div>
      <p class="muted" style="font-size:12.5px;margin-top:10px">
        Highlighted cells lead on that measure. A dash means the figure is not
        available for that company.</p>

      ${r.observations.length ? `<h4 style="margin:22px 0 8px;font-size:15px">What stands out</h4>
        <ul style="color:var(--ink-2);font-size:14px;line-height:1.7;margin:0;padding-left:20px">
          ${r.observations.map(o => `<li>${esc(o)}</li>`).join("")}</ul>` : ""}

      <div class="callout info" style="margin-top:18px">${esc(r.note)}</div>
    </div>`;
  } catch (e) {
    box.innerHTML = `<div class="card"><div class="error">${esc(e.message)}</div></div>`;
  }
}

/* =======================================================================
   BACKTEST
   ======================================================================= */
let btHoldings = [{ticker: "COMI", weight: 50}, {ticker: "SWDY", weight: 50}];

function viewBacktest(view) {
  const d = new Date(); d.setFullYear(d.getFullYear() - 5);
  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>Backtest a portfolio</h2>
      <p>Test how a mix of Egyptian shares would have performed, day by day, using
         only prices that existed at the time.</p>
    </div>

    <div class="card">
      <div class="card-head"><h2>Holdings</h2><p class="sub">Weights are scaled to add up to 100%.</p></div>
      <div id="bt-holdings"></div>
      <div class="form-row" style="margin-top:12px">
        <div class="field"><label>Add a company</label>${tickerSelect("bt-add")}</div>
        <div class="field field-btn"><button class="btn btn-ghost" onclick="addHolding()">Add</button></div>
      </div>
    </div>

    <div class="card">
      <div class="form-row">
        <div class="field"><label>Starting amount</label>
          <div class="input-money"><span class="prefix">EGP</span>
            <input id="bt-initial" type="number" value="100000" min="0" step="1000"></div></div>
        <div class="field"><label>Added each month</label>
          <div class="input-money"><span class="prefix">EGP</span>
            <input id="bt-monthly" type="number" value="0" min="0" step="500"></div></div>
        <div class="field"><label>Start date</label>
          <input id="bt-start" type="date" value="${d.toISOString().slice(0, 10)}"
                 max="${new Date().toISOString().slice(0, 10)}"></div>
        <div class="field"><label>Rebalance</label>
          <select id="bt-reb">
            <option value="none">Never</option>
            <option value="annual">Once a year</option>
            <option value="quarterly">Every 3 months</option>
            <option value="monthly">Every month</option>
          </select></div>
        <div class="field field-btn"><button class="btn" onclick="runBacktest()">Run backtest</button></div>
      </div>
      <label class="check"><input id="bt-reinvest" type="checkbox" checked>
        <span>Reinvest dividends</span></label>
    </div>

    <div id="bt-results"></div>`;
  renderHoldings();
}

function renderHoldings() {
  document.getElementById("bt-holdings").innerHTML = btHoldings.map((h, i) => `
    <div class="form-row" style="margin-bottom:8px">
      <div class="field"><label>Company</label>
        ${tickerSelect("bt-h" + i, h.ticker, {needPrices: true,
          onSelect: it => { btHoldings[i].ticker = it.ticker; }})}</div>
      <div class="field" style="max-width:130px"><label>Weight %</label>
        <input type="number" value="${h.weight}" min="0" step="5"
               onchange="btHoldings[${i}].weight=+this.value"></div>
      <div class="field field-btn"><button class="btn btn-ghost btn-sm"
        onclick="btHoldings.splice(${i},1);renderHoldings()">Remove</button></div>
    </div>`).join("");
  initPickers();
}
function addHolding() {
  const t = pickerValue("bt-add");
  if (!t || btHoldings.some(h => h.ticker === t)) return;
  btHoldings.push({ticker: t, weight: 20}); renderHoldings();
}

async function runBacktest() {
  const box = document.getElementById("bt-results");
  box.innerHTML = `<div class="spinner">Running day by day…</div>`;
  try {
    const r = await post("/api/backtest", {
      holdings: btHoldings.map(h => ({ticker: h.ticker, weight: h.weight})),
      start: document.getElementById("bt-start").value,
      initial: +document.getElementById("bt-initial").value || 0,
      monthly: +document.getElementById("bt-monthly").value || 0,
      rebalance: document.getElementById("bt-reb").value,
      reinvest_dividends: document.getElementById("bt-reinvest").checked,
    });

    const yrs = Object.entries(r.yearly_returns || {}).sort();
    box.innerHTML = `<div class="card">
      <div class="k">Final value</div>
      <p class="big-num ${cls(r.profit)}">${egp(r.final_value)}</p>
      <p style="font-size:15px;color:var(--ink-2);margin:6px 0 0">
        You put in ${egp(r.total_contributed)} over ${r.years} years across
        ${r.holdings.length} companies. ${r.profit >= 0 ? "Gain" : "Loss"} of
        <strong style="color:var(--ink)">${egp(Math.abs(r.profit))}</strong>.</p>

      <div class="stats">
        <div class="stat"><div class="k">Total return</div>
          <div class="v ${cls(r.total_return_pct)}">${pct(r.total_return_pct)}</div></div>
        ${r.cagr_pct != null ? `<div class="stat"><div class="k">Per year</div>
          <div class="v ${cls(r.cagr_pct)}">${pct(r.cagr_pct)}</div></div>` : ""}
        ${r.time_weighted_return_pct != null ? `<div class="stat"><div class="k">Per year (timing removed)</div>
          <div class="v ${cls(r.time_weighted_return_pct)}">${pct(r.time_weighted_return_pct)}</div>
          <div class="note">ignores when you added money</div></div>` : ""}
        <div class="stat"><div class="k">Volatility</div>
          <div class="v">${pctPlain(r.volatility_pct)}</div></div>
        <div class="stat"><div class="k">Worst fall</div>
          <div class="v down">${pctPlain(r.max_drawdown_pct)}</div>
          ${r.recovery_days ? `<div class="note">recovered in ${r.recovery_days} days</div>`
            : `<div class="note">had not recovered by the end</div>`}</div>
        <div class="stat"><div class="k">Sharpe ratio</div>
          <div class="v">${num(r.sharpe, 2)}</div>
          <div class="note">vs ${pctPlain(r.risk_free_used_pct)} risk-free</div></div>
        <div class="stat"><div class="k">Dividends</div>
          <div class="v">${egp(r.dividends_received)}</div></div>
        <div class="stat"><div class="k">Costs paid</div>
          <div class="v">${egp(r.transaction_costs)}</div></div>
      </div>

      ${r.sharpe != null && r.sharpe < 0 ? `<div class="callout">
        <strong>A negative Sharpe ratio.</strong> Over this period the portfolio
        returned less than an Egyptian government deposit paying about
        ${pctPlain(r.risk_free_used_pct)}, despite carrying share-market risk.
        This is the kind of result a nominal return figure alone would hide.</div>` : ""}

      <div class="chart-box tall"><canvas id="bt-chart"></canvas></div>

      ${yrs.length ? `<h4 style="margin:20px 0 8px;font-size:15px">Year by year</h4>
        <div class="table-scroll"><table class="tbl">
          <thead><tr><th style="text-align:left">Year</th>${yrs.map(([y]) => `<th>${y}</th>`).join("")}</tr></thead>
          <tbody><tr><td>Return</td>${yrs.map(([, v]) =>
            `<td class="${cls(v)}">${pct(v)}</td>`).join("")}</tr></tbody>
        </table></div>` : ""}

      <h4 style="margin:22px 0 8px;font-size:15px">What was in it</h4>
      <div class="table-scroll"><table class="tbl">
        <thead><tr><th>Ticker</th><th style="text-align:left">Company</th>
          <th style="text-align:left">Sector</th><th>Weight</th></tr></thead>
        <tbody>${r.holdings.map(h => `<tr onclick="go('/stock/${esc(h.ticker)}')">
          <td class="tk">${esc(h.ticker)}</td>
          <td style="text-align:left">${esc(h.name)}</td>
          <td style="text-align:left;color:var(--ink-3);font-size:12.5px">${esc(h.sector || "—")}</td>
          <td>${pctPlain(h.weight_pct)}</td></tr>`).join("")}</tbody>
      </table></div>

      ${assumptionsBlock(r.assumptions)}
      <p class="disclaim">A backtest shows what already happened to one specific
        combination. It is not evidence that the same mix will do well in future.</p>
    </div>`;

    lineChart("bt-chart", r.series.map(p => p.d), [
      {label: "Portfolio value", data: r.series.map(p => p.v), borderColor: GREEN,
       borderWidth: 2, pointRadius: 0, tension: .1,
       backgroundColor: "rgba(11,107,94,.07)", fill: true},
      {label: "Money you put in", data: r.series.map(p => p.c), borderColor: "#8492a6",
       borderWidth: 1.5, pointRadius: 0, borderDash: [5, 4], tension: 0},
    ], {title: "Portfolio value vs money contributed"});
  } catch (e) {
    box.innerHTML = `<div class="card"><div class="error">${esc(e.message)}</div></div>`;
  }
}
