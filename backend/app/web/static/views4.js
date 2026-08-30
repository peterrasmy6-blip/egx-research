/* EGX Research — portfolio forecast.

   "Build a portfolio today, hold it for N years, see what could happen."

   Every holding gets its own expected return, built from what that company
   actually reports. The page shows those building blocks so the reader can see
   why one holding is expected to do better than another, rather than trusting
   a single unexplained number.
*/

let fcHoldings = [{ticker: "COMI", weight: 40},
                  {ticker: "SWDY", weight: 30},
                  {ticker: "ETEL", weight: 30}];

function viewPortfolioForecast(view) {
  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>Forecast a portfolio</h2>
      <p>Build a portfolio today and see how it might behave over the years
         ahead. Each company is modelled on its own figures — not one blanket
         rate applied to everything.</p>
    </div>

    <div class="callout"><strong>This is a model, not a prediction.</strong>
      It shows what a set of stated assumptions implies. Those assumptions can
      be wrong, and real results will differ — possibly by a wide margin.
      Historical figures on this site are facts; everything on this page is an
      estimate.</div>

    <div class="card">
      <div class="card-head"><h2>Your holdings</h2>
        <p class="sub">Type to search — no scrolling through hundreds of companies.
           Weights are scaled to 100%.</p></div>
      <div id="pf-fc-holdings"></div>
      <div class="form-row" style="margin-top:12px">
        <div class="field"><label>Add a company</label>
          ${tickerSelect("pffc-add", null, {needPrices: true})}</div>
        <div class="field field-btn"><button class="btn btn-ghost" onclick="addFcHolding()">Add</button></div>
      </div>
    </div>

    <div class="card">
      <div class="form-row">
        <div class="field"><label>Starting amount</label>
          <div class="input-money"><span class="prefix">EGP</span>
            <input id="pffc-initial" type="number" value="100000" min="0" step="1000"></div></div>
        <div class="field"><label>Added each month</label>
          <div class="input-money"><span class="prefix">EGP</span>
            <input id="pffc-monthly" type="number" value="0" min="0" step="500"></div></div>
        <div class="field" style="max-width:170px"><label>Hold for</label>
          <select id="pffc-years">
            <option value="1">1 year</option>
            <option value="3" selected>3 years</option>
            <option value="5">5 years</option>
            <option value="10">10 years</option>
          </select></div>
        <div class="field" style="max-width:150px"><label>Inflation % / yr</label>
          <input id="pffc-infl" type="number" value="20" min="0" max="60"></div>
        <div class="field field-btn"><button class="btn" onclick="runPortfolioForecast()">Forecast</button></div>
      </div>
    </div>

    <div id="pffc-results"></div>`;
  renderFcHoldings();
}

function renderFcHoldings() {
  document.getElementById("pf-fc-holdings").innerHTML = fcHoldings.map((h, i) => `
    <div class="form-row" style="margin-bottom:8px">
      <div class="field"><label>Company</label>
        ${tickerSelect("pffc-h" + i, h.ticker, {needPrices: true,
          onSelect: it => { fcHoldings[i].ticker = it.ticker; }})}</div>
      <div class="field" style="max-width:130px"><label>Weight %</label>
        <input type="number" value="${h.weight}" min="0" step="5"
               onchange="fcHoldings[${i}].weight=+this.value"></div>
      <div class="field field-btn"><button class="btn btn-ghost btn-sm"
        onclick="fcHoldings.splice(${i},1);renderFcHoldings()">Remove</button></div>
    </div>`).join("");
  initPickers();
}

function addFcHolding() {
  const t = pickerValue("pffc-add");
  if (!t || fcHoldings.some(h => h.ticker === t)) return;
  fcHoldings.push({ticker: t, weight: 20});
  renderFcHoldings();
}

async function runPortfolioForecast() {
  const box = document.getElementById("pffc-results");
  box.innerHTML = `<div class="spinner">Modelling…</div>`;
  try {
    const r = await post("/api/forecast/portfolio", {
      holdings: fcHoldings.filter(h => h.weight > 0),
      initial: +document.getElementById("pffc-initial").value || 0,
      monthly: +document.getElementById("pffc-monthly").value || 0,
      years: +document.getElementById("pffc-years").value,
      inflation_pct: +document.getElementById("pffc-infl").value || 0,
    });
    renderPortfolioForecast(r, box);
  } catch (e) {
    box.innerHTML = `<div class="card"><div class="error">${esc(e.message)}</div></div>`;
  }
}

function renderPortfolioForecast(r, box) {
  const s = r.scenarios, p = r.percentiles;
  const profitUp = r.projected_profit >= 0;

  box.innerHTML = `
  <div class="card">
    <div class="card-head"><h2>After ${r.years} year${r.years > 1 ? "s" : ""}</h2>
      <p class="sub">Middle estimate, from ${count(r.simulations)} simulated futures.</p></div>

    <div class="k">Projected value</div>
    <p class="big-num ${cls(r.projected_profit)}">${egp(r.projected_value)}</p>
    <p style="font-size:15px;color:var(--ink-2);margin:6px 0 0">
      You put in ${egp(r.total_contributed)}. That is a projected
      ${profitUp ? "gain" : "loss"} of
      <strong style="color:var(--ink)">${egp(Math.abs(r.projected_profit))}</strong>
      (${pct(r.projected_profit_pct)}).</p>

    <div class="stats">
      <div class="stat"><div class="k">Expected return</div>
        <div class="v ${cls(r.expected_return_pct)}">${pct(r.expected_return_pct)}</div>
        <div class="note">per year, before inflation</div></div>
      <div class="stat"><div class="k">Volatility</div>
        <div class="v">${pctPlain(r.volatility_pct)}</div>
        <div class="note">how much it may swing</div></div>
      ${r.diversification_benefit_pct ? `<div class="stat"><div class="k">Diversification</div>
        <div class="v up">−${pctPlain(r.diversification_benefit_pct)}</div>
        <div class="note">less risk than holding these separately</div></div>` : ""}
      <div class="stat"><div class="k">Chance of fewer pounds</div>
        <div class="v ${r.probability_of_loss_pct > 25 ? "down" : ""}">${pctPlain(r.probability_of_loss_pct)}</div>
        <div class="note">below the ${egp(r.total_contributed)} put in</div></div>
      <div class="stat"><div class="k">Chance of losing buying power</div>
        <div class="v ${r.probability_of_real_loss_pct > 40 ? "down" : ""}">${pctPlain(r.probability_of_real_loss_pct)}</div>
        <div class="note">the one that matters</div></div>
      ${r.worst_historical_drawdown_pct != null ? `<div class="stat"><div class="k">Worst past fall</div>
        <div class="v down">${pctPlain(r.worst_historical_drawdown_pct)}</div>
        <div class="note">actually happened to a holding</div></div>` : ""}
    </div>

    ${r.risk_note ? `<div class="callout">${esc(r.risk_note)}</div>` : ""}

    <h4 style="margin:24px 0 10px;font-size:15px">Three scenarios</h4>
    <div class="stats">
      ${[["conservative","Cautious"],["base","Middle"],["optimistic","Optimistic"]].map(([k,l]) =>
        `<div class="stat"><div class="k">${l} (${pctPlain(s[k].annual_return_pct)}/yr)</div>
          <div class="v ${cls(s[k].final - r.total_contributed)}">${egp(s[k].final)}</div>
          <div class="note">${egp(s[k].path[s[k].path.length-1].real)} in today's money</div></div>`).join("")}
    </div>

    <div class="chart-box tall"><canvas id="pffc-chart"></canvas></div>

    <div class="callout info">
      <strong>Where the range comes from.</strong> The cautious and optimistic
      cases are not guesses — they are the middle estimate moved by this
      portfolio's own measured volatility of ${pctPlain(r.volatility_pct)}. A
      steadier portfolio would show a narrower cone; a riskier one, wider.
    </div>

    <h4 style="margin:24px 0 10px;font-size:15px">The full range of outcomes</h4>
    <div class="stats">
      <div class="stat"><div class="k">Worst 10%</div><div class="v">${egp(p.p10)}</div>
        <div class="note">1 in 10 ended below this</div></div>
      <div class="stat"><div class="k">Lower quarter</div><div class="v">${egp(p.p25)}</div></div>
      <div class="stat"><div class="k">Middle</div><div class="v">${egp(p.median)}</div>
        <div class="note">${egp(r.percentiles_real.median)} in today's money</div></div>
      <div class="stat"><div class="k">Upper quarter</div><div class="v">${egp(p.p75)}</div></div>
      <div class="stat"><div class="k">Best 10%</div><div class="v">${egp(p.p90)}</div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-head"><h2>Why each holding is expected to do what it does</h2>
      <p class="sub">Built from each company's own reported figures. Blocks that
         do not apply to a company are left out and the reason given.</p></div>
    ${r.holdings.map(h => `
      <div class="method">
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap">
          <h4 style="margin:0"><a href="/stock/${esc(h.ticker)}">${esc(h.ticker)}</a>
            — ${esc(h.name)}</h4>
          <div style="font-size:14px">
            <span class="muted">${pctPlain(h.weight_pct)} of portfolio</span>
            &nbsp;→&nbsp;
            <strong class="${cls(h.expected_return_pct)}">${pct(h.expected_return_pct)}/yr</strong>
          </div>
        </div>
        <p class="exp" style="margin:8px 0 10px">${esc(h.basis)}</p>
        <table class="tbl" style="font-size:13px">
          <tbody>
            ${h.blocks.map(b => `<tr>
              <td style="width:170px">${esc(b.name)}</td>
              <td style="text-align:right;width:70px;font-weight:600"
                  class="${cls(b.value_pct)}">${pct(b.value_pct)}</td>
              <td style="text-align:left;color:var(--ink-3);white-space:normal">${esc(b.detail)}</td>
            </tr>`).join("")}
            ${h.skipped.map(sk => `<tr>
              <td style="color:var(--ink-3)">not used</td>
              <td></td>
              <td style="text-align:left;color:var(--ink-3);white-space:normal">${esc(sk)}</td>
            </tr>`).join("")}
          </tbody>
        </table>
        <div class="nums" style="margin-top:10px;font-size:12.5px;color:var(--ink-3)">
          <span>P/E <b>${h.pe != null ? mult(h.pe) : "—"}</b></span>
          <span>ROE <b>${h.roe_pct != null ? pctPlain(h.roe_pct) : "—"}</b></span>
          <span>Yield <b>${h.dividend_yield_pct != null ? pctPlain(h.dividend_yield_pct, 2) : "—"}</b></span>
          <span>Volatility <b>${h.volatility_pct != null ? pctPlain(h.volatility_pct) : "—"}</b></span>
        </div>
      </div>`).join("")}
  </div>

  ${r.correlations ? `<div class="card">
    <div class="card-head"><h2>How these holdings move together</h2>
      <p class="sub">Measured from real daily prices. Near 1 means they rise and
         fall together, so holding both adds less protection than it appears.</p></div>
    <div class="table-scroll"><table class="tbl">
      <thead><tr><th></th>${Object.keys(r.correlations).map(t =>
        `<th>${esc(t)}</th>`).join("")}</tr></thead>
      <tbody>${Object.entries(r.correlations).map(([a, row]) => `<tr>
        <td class="tk">${esc(a)}</td>
        ${Object.keys(r.correlations).map(b => {
          const v = row[b];
          const hot = a !== b && v >= 0.6;
          return `<td class="${hot ? "lead" : ""}">${num(v, 2)}</td>`;
        }).join("")}</tr>`).join("")}
      </tbody></table></div>
  </div>` : ""}

  <div class="card">
    <div class="card-head"><h2>How this was worked out</h2></div>
    <p style="color:var(--ink-2);font-size:14.5px;line-height:1.65">${esc(r.method)}</p>
    ${r.simulation_note ? `<p style="color:var(--ink-2);font-size:14.5px;line-height:1.65">
      ${esc(r.simulation_note)}</p>` : ""}
    ${assumptionsBlock(r.assumptions, "Every assumption behind these numbers")}
    <p class="disclaim">${esc(r.disclaimer)}</p>
  </div>`;

  // Chart: three scenario paths plus what was contributed.
  const labels = ["Now", ...s.base.path.map(x => "Year " + x.year)];
  const withStart = arr => [r.initial, ...arr];
  const contribAt = y => r.initial + r.monthly * 12 * y;

  lineChart("pffc-chart", labels, [
    {label: "Optimistic", data: withStart(s.optimistic.path.map(x => x.value)),
     borderColor: TEAL, borderWidth: 2, pointRadius: 0, tension: .2},
    {label: "Middle", data: withStart(s.base.path.map(x => x.value)),
     borderColor: GREEN, borderWidth: 2.5, pointRadius: 0, tension: .2},
    {label: "Cautious", data: withStart(s.conservative.path.map(x => x.value)),
     borderColor: AMBER, borderWidth: 2, pointRadius: 0, tension: .2},
    {label: "Middle, after inflation", data: withStart(s.base.path.map(x => x.real)),
     borderColor: BLUE, borderWidth: 2, pointRadius: 0, borderDash: [5, 4], tension: .2},
    {label: "Money you put in",
     data: [r.initial, ...s.base.path.map(x => contribAt(x.year))],
     borderColor: "#8492a6", borderWidth: 1.5, pointRadius: 0,
     borderDash: [3, 3], tension: 0},
  ], {title: "Projected value — model scenarios, not predictions", xTicks: 12});
}
