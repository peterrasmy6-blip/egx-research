/* EGX Research — forecast, portfolio, education. */

/* =======================================================================
   FUTURE SCENARIOS + MONTE CARLO
   ======================================================================= */
function viewForecast(view, args) {
  const preset = (args && args[0]) ? decodeURIComponent(args[0]) : "COMI";
  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>Future scenarios</h2>
      <p>These are <strong>not predictions</strong>. They are the arithmetic
         consequences of assumptions you choose. Nobody can forecast the market.</p>
    </div>

    <div class="callout"><strong>Read this first.</strong> Every number on this page
      depends entirely on the return you assume. Change the assumption and the answer
      changes completely. Use these tools to understand <em>ranges</em> and
      <em>uncertainty</em> — not to predict what will happen.</div>

    <div class="card">
      <div class="ranges" id="fc-mode">
        <button class="range on" data-m="scenario">Three scenarios</button>
        <button class="range" data-m="mc">Monte Carlo</button>
      </div>

      <div class="form-row" style="margin-top:18px">
        <div class="field"><label>Starting amount</label>
          <div class="input-money"><span class="prefix">EGP</span>
            <input id="fc-initial" type="number" value="100000" min="0" step="1000"></div></div>
        <div class="field"><label>Added each month</label>
          <div class="input-money"><span class="prefix">EGP</span>
            <input id="fc-monthly" type="number" value="5000" min="0" step="500"></div></div>
        <div class="field" style="max-width:130px"><label>For how many years</label>
          <input id="fc-years" type="number" value="10" min="1" max="40"></div>
        <div class="field" style="max-width:150px"><label>Inflation % / year</label>
          <input id="fc-infl" type="number" value="20" min="0" max="60"></div>
      </div>

      <div id="fc-scenario-inputs" class="form-row" style="margin-top:12px">
        <div class="field"><label>Cautious return % / yr</label>
          <input id="fc-cons" type="number" value="8" step="1"></div>
        <div class="field"><label>Middle return % / yr</label>
          <input id="fc-base" type="number" value="15" step="1"></div>
        <div class="field"><label>Optimistic return % / yr</label>
          <input id="fc-opt" type="number" value="22" step="1"></div>
        <div class="field" style="max-width:170px"><label>Increase contribution % / yr</label>
          <input id="fc-inc" type="number" value="0" min="0" max="50"></div>
      </div>

      <div id="fc-mc-inputs" class="form-row" style="margin-top:12px;display:none">
        <div class="field"><label>Base assumptions on</label>
          ${tickerSelect("fc-ticker", preset)}</div>
        <div class="field" style="max-width:160px"><label>Simulations</label>
          <select id="fc-sims">
            <option value="1000">1,000</option>
            <option value="5000" selected>5,000</option>
            <option value="10000">10,000</option>
          </select></div>
        <div class="field"><label>Target amount (optional)</label>
          <div class="input-money"><span class="prefix">EGP</span>
            <input id="fc-target" type="number" value="2000000" min="0" step="100000"></div></div>
      </div>

      <div class="form-row" style="margin-top:14px">
        <div class="field field-btn"><button class="btn" onclick="runForecast()">Calculate</button></div>
      </div>
      <div id="fc-note" class="muted" style="font-size:13px;margin-top:10px"></div>
    </div>

    <div id="fc-results"></div>`;

  document.querySelectorAll("#fc-mode .range").forEach(b => b.onclick = () => {
    document.querySelectorAll("#fc-mode .range").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    const mc = b.dataset.m === "mc";
    document.getElementById("fc-scenario-inputs").style.display = mc ? "none" : "";
    document.getElementById("fc-mc-inputs").style.display = mc ? "" : "none";
    document.getElementById("fc-results").innerHTML = "";
    document.getElementById("fc-note").textContent = mc
      ? "Monte Carlo measures how volatile the chosen company has actually been, then runs thousands of possible futures with that level of uncertainty."
      : "";
  });
}

async function runForecast() {
  const box = document.getElementById("fc-results");
  const mc = document.querySelector("#fc-mode .range.on").dataset.m === "mc";
  box.innerHTML = `<div class="spinner">Calculating…</div>`;
  const common = {
    initial: +document.getElementById("fc-initial").value || 0,
    monthly: +document.getElementById("fc-monthly").value || 0,
    years: +document.getElementById("fc-years").value || 10,
    inflation_pct: +document.getElementById("fc-infl").value || 0,
  };
  try {
    if (mc) {
      const r = await post("/api/forecast/montecarlo", {
        ...common,
        ticker: pickerValue("fc-ticker"),
        simulations: +document.getElementById("fc-sims").value,
        target: +document.getElementById("fc-target").value || null,
      });
      renderMonteCarlo(r, box);
    } else {
      const r = await post("/api/forecast/scenarios", {
        ...common,
        conservative_pct: +document.getElementById("fc-cons").value,
        base_pct: +document.getElementById("fc-base").value,
        optimistic_pct: +document.getElementById("fc-opt").value,
        annual_increase_pct: +document.getElementById("fc-inc").value || 0,
      });
      renderScenarios(r, box);
    }
  } catch (e) {
    box.innerHTML = `<div class="card"><div class="error">${esc(e.message)}</div></div>`;
  }
}

function renderScenarios(r, box) {
  const s = r.scenarios;
  const names = [["conservative", "Cautious"], ["base", "Middle"], ["optimistic", "Optimistic"]];
  box.innerHTML = `<div class="card">
    <div class="card-head"><h2>After ${r.years} years</h2>
      <p class="sub">If you invest ${egp(r.initial)} now and ${egp(r.monthly)} every month.</p></div>

    <div class="stats">
      ${names.map(([k, label]) => `<div class="stat">
        <div class="k">${label} (${pctPlain(s[k].annual_return_pct)}/yr)</div>
        <div class="v">${egp(s[k].final_nominal)}</div>
        <div class="note">${egp(s[k].final_real)} in today's money</div></div>`).join("")}
    </div>

    <div class="callout"><strong>The two numbers differ for a reason.</strong>
      The first is how many pounds you would have. The second is what those pounds
      could buy, after ${pctPlain(r.inflation_assumption_pct)} yearly inflation.
      In Egypt this gap is large, and it is the second number that determines
      whether you are actually better off.</div>

    <div class="chart-box tall"><canvas id="fc-chart"></canvas></div>

    <h4 style="margin:22px 0 8px;font-size:15px">Where the money comes from (middle case)</h4>
    <div class="stats">
      <div class="stat"><div class="k">You contribute</div>
        <div class="v">${egp(s.base.total_contributed)}</div></div>
      <div class="stat"><div class="k">Investment growth adds</div>
        <div class="v ${cls(s.base.growth_from_returns)}">${egp(s.base.growth_from_returns)}</div></div>
      <div class="stat"><div class="k">Total</div>
        <div class="v">${egp(s.base.final_nominal)}</div></div>
    </div>

    ${assumptionsBlock(r.assumptions)}
    <p class="disclaim">${esc(r.disclaimer)}</p>
  </div>`;

  const yrs = s.base.path.map(p => "Year " + p.year);
  lineChart("fc-chart", yrs, [
    {label: "Optimistic", data: s.optimistic.path.map(p => p.nominal),
     borderColor: TEAL, borderWidth: 2, pointRadius: 0, tension: .2},
    {label: "Middle", data: s.base.path.map(p => p.nominal),
     borderColor: GREEN, borderWidth: 2.5, pointRadius: 0, tension: .2},
    {label: "Cautious", data: s.conservative.path.map(p => p.nominal),
     borderColor: AMBER, borderWidth: 2, pointRadius: 0, tension: .2},
    {label: "Middle, after inflation", data: s.base.path.map(p => p.real),
     borderColor: BLUE, borderWidth: 2, pointRadius: 0, borderDash: [5, 4], tension: .2},
    {label: "Money you put in", data: s.base.path.map(p => p.contributed),
     borderColor: "#8492a6", borderWidth: 1.5, pointRadius: 0, borderDash: [3, 3], tension: 0},
  ], {title: "Projected value — scenarios, not predictions", xTicks: 12});
}

function renderMonteCarlo(r, box) {
  const p = r.percentiles;
  box.innerHTML = `<div class="card">
    <div class="card-head"><h2>${count(r.simulations)} simulated futures</h2>
      <p class="sub">Based on ${esc(r.basis)}.</p></div>

    <div class="callout info">
      <strong>How to read this.</strong> Each simulation is one possible future.
      The figures below show where those futures landed. The median means half
      ended above it and half below — it is not "the expected answer".
    </div>

    <div class="stats">
      <div class="stat"><div class="k">Worst 10%</div><div class="v">${egp(p.p10)}</div>
        <div class="note">1 in 10 ended below this</div></div>
      <div class="stat"><div class="k">Lower quarter</div><div class="v">${egp(p.p25)}</div></div>
      <div class="stat"><div class="k">Median</div><div class="v">${egp(p.median)}</div>
        <div class="note">${egp(r.percentiles_real.median)} in today's money</div></div>
      <div class="stat"><div class="k">Upper quarter</div><div class="v">${egp(p.p75)}</div></div>
      <div class="stat"><div class="k">Best 10%</div><div class="v">${egp(p.p90)}</div>
        <div class="note">1 in 10 ended above this</div></div>
      <div class="stat"><div class="k">Chance of ending with fewer pounds</div>
        <div class="v ${r.probability_of_loss_pct > 25 ? "down" : ""}">${pctPlain(r.probability_of_loss_pct)}</div>
        <div class="note">below the ${egp(r.total_contributed)} you paid in</div></div>
      <div class="stat"><div class="k">Chance of losing purchasing power</div>
        <div class="v ${r.probability_of_real_loss_pct > 40 ? "down" : ""}">${pctPlain(r.probability_of_real_loss_pct)}</div>
        <div class="note">the one that matters</div></div>
      ${r.target ? `<div class="stat"><div class="k">Chance of reaching ${egp(r.target)}</div>
        <div class="v">${pctPlain(r.probability_of_target_pct)}</div></div>` : ""}
    </div>

    ${r.warnings && r.warnings.length ? r.warnings.map(w =>
      `<div class="callout"><strong>About the return assumption.</strong> ${esc(w)}</div>`).join("") : ""}

    <div class="callout info">
      <strong>Two very different questions.</strong>
      Only ${pctPlain(r.probability_of_loss_pct)} of these futures end with fewer
      pounds than you put in — but ${pctPlain(r.probability_of_real_loss_pct)} end
      with less <em>buying power</em>. ${esc(r.real_loss_note || "")}
      In Egypt the second number is the one that tells you whether you actually
      got richer.
    </div>

    <div class="callout"><strong>The spread is the point.</strong>
      The gap between ${egp(p.p10)} and ${egp(p.p90)} is what uncertainty actually
      looks like. Assuming ${pctPlain(r.assumed_annual_return_pct)} a year with
      ${pctPlain(r.assumed_annual_volatility_pct)} volatility, outcomes this far
      apart are entirely normal.</div>

    <div class="chart-box tall"><canvas id="mc-chart"></canvas></div>

    ${r.method_note ? `<div class="callout info">
      <strong>How the randomness is generated.</strong> ${esc(r.method_note)}
      ${r.mean_uncertainty_applied ? `The expected return is treated as
      uncertain too — it is the least precisely known input there is, so the
      range of outcomes is wider than a model that assumes it is exactly
      right.` : ""}</div>` : ""}

    <details class="assump" open><summary>What this model cannot capture</summary>
      <ul>${r.limitations.map(l => `<li>${esc(l)}</li>`).join("")}</ul></details>
    ${assumptionsBlock(r.assumptions)}
    <p class="disclaim">${esc(r.disclaimer)}</p>
  </div>`;

  const paths = r.sample_paths.slice(0, 30);
  const labels = paths.length ? paths[0].map((_, i) => i === 0 ? "Now" : "Year " + i) : [];
  lineChart("mc-chart", labels, paths.map((pth, i) => ({
    label: "", data: pth, borderColor: "rgba(11,107,94,.20)",
    borderWidth: 1, pointRadius: 0, tension: .2,
  })), {
    title: "30 of the simulated futures — each line is one possible path",
    chartOptions: {plugins: {legend: {display: false}}},
  });
}

/* =======================================================================
   PORTFOLIO ANALYSIS
   ======================================================================= */
let pfHoldings = [{ticker: "COMI", value: 50000}, {ticker: "TMGH", value: 30000}];

function viewPortfolio(view) {
  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>Portfolio analysis</h2>
      <p>Enter what you hold and see what it is actually exposed to. This describes
         your portfolio — it does not tell you what to change.</p>
    </div>
    <div class="card">
      <div id="pf-holdings"></div>
      <div class="form-row" style="margin-top:12px">
        <div class="field"><label>Add a holding</label>${tickerSelect("pf-add", null, {funds: "include"})}</div>
        <div class="field field-btn"><button class="btn btn-ghost" onclick="addPf()">Add</button></div>
        <div class="field field-btn"><button class="btn" onclick="runPortfolio()">Analyse</button></div>
      </div>
      <p class="muted" style="font-size:13px;margin-top:12px">
        Nothing you type here is saved or sent anywhere beyond this calculation.</p>
    </div>
    <div id="pf-results"></div>`;
  renderPf();
}

function renderPf() {
  document.getElementById("pf-holdings").innerHTML = pfHoldings.map((h, i) => `
    <div class="form-row" style="margin-bottom:8px">
      <div class="field"><label>Company or fund</label>
        ${tickerSelect("pf-h" + i, h.ticker, {funds: "include",
          onSelect: it => { pfHoldings[i].ticker = it.ticker; }})}</div>
      <div class="field" style="max-width:190px"><label>Value held</label>
        <div class="input-money"><span class="prefix">EGP</span>
          <input type="number" value="${h.value}" min="0" step="1000"
                 onchange="pfHoldings[${i}].value=+this.value"></div></div>
      <div class="field field-btn"><button class="btn btn-ghost btn-sm"
        onclick="pfHoldings.splice(${i},1);renderPf()">Remove</button></div>
    </div>`).join("");
  initPickers();
}
function addPf() {
  const t = pickerValue("pf-add");
  if (!t || pfHoldings.some(h => h.ticker === t)) return;
  pfHoldings.push({ticker: t, value: 10000}); renderPf();
}

async function runPortfolio() {
  const box = document.getElementById("pf-results");
  box.innerHTML = `<div class="spinner">Analysing…</div>`;
  try {
    const r = await post("/api/portfolio/analyse", pfHoldings.filter(h => h.value > 0));
    box.innerHTML = `<div class="card">
      <div class="k">Total value</div>
      <p class="big-num">${egp(r.total_value)}</p>

      <div class="stats">
        <div class="stat"><div class="k">Holdings</div><div class="v">${r.holdings.length}</div></div>
        <div class="stat"><div class="k">Largest holding</div>
          <div class="v">${pctPlain(r.largest_holding_pct)}</div></div>
        <div class="stat"><div class="k">Largest sector</div>
          <div class="v">${pctPlain(r.largest_sector_pct)}</div></div>
        <div class="stat"><div class="k">Effective holdings</div>
          <div class="v">${num(r.effective_holdings, 1)}</div>
          <div class="note">how many it behaves like</div></div>
      </div>

      <h4 style="margin:22px 0 8px;font-size:15px">What this portfolio contains</h4>
      <div class="table-scroll"><table class="tbl">
        <thead><tr><th>Ticker</th><th style="text-align:left">Company</th>
          <th style="text-align:left">Sector</th><th>Value</th><th>Weight</th></tr></thead>
        <tbody>${r.holdings.map(h => `<tr onclick="go('/stock/${esc(h.ticker)}')">
          <td class="tk">${esc(h.ticker)}</td>
          <td style="text-align:left">${esc(h.name.slice(0, 40))}</td>
          <td style="text-align:left;color:var(--ink-3);font-size:12.5px">${esc(h.sector)}</td>
          <td>${egp(h.value)}</td><td>${pctPlain(h.weight_pct)}</td></tr>`).join("")}</tbody>
      </table></div>

      <h4 style="margin:22px 0 8px;font-size:15px">Sector exposure</h4>
      ${r.sectors.map(s => `<div style="margin-bottom:10px">
        <div style="display:flex;justify-content:space-between;font-size:13.5px">
          <span>${esc(s.sector)}</span><span style="font-weight:600">${pctPlain(s.weight_pct)}</span></div>
        <div class="meter"><i style="width:${Math.min(100, s.weight_pct)}%"></i></div>
      </div>`).join("")}

      <h4 style="margin:22px 0 8px;font-size:15px">What we notice</h4>
      <ul style="color:var(--ink-2);font-size:14.5px;line-height:1.7;margin:0;padding-left:20px">
        ${r.observations.map(o => `<li>${esc(o)}</li>`).join("")}</ul>

      <div class="callout info" style="margin-top:18px">${esc(r.note)}</div>
    </div>`;
  } catch (e) {
    box.innerHTML = `<div class="card"><div class="error">${esc(e.message)}</div></div>`;
  }
}

/* =======================================================================
   LEARN
   ======================================================================= */
async function viewLearn(view) {
  const [g, l, q] = await Promise.all([
    api("/api/education/glossary"),
    api("/api/education/lessons"),
    api("/api/education/questionnaire"),
  ]);

  const cats = [...new Set(g.terms.map(t => t.category))];

  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>Learn investing</h2>
      <p>Plain English, no jargon. Everything explained here is used somewhere on this site.</p>
    </div>

    <div class="ranges" id="ln-tabs">
      <button class="range on" data-t="lessons">Guides</button>
      <button class="range" data-t="glossary">Dictionary</button>
      <button class="range" data-t="quiz">Know your risk</button>
    </div>

    <div id="ln-lessons" style="margin-top:20px">
      ${l.lessons.map(x => `<div class="lesson">
        <h3>${esc(x.title)}</h3>
        <div class="meta">${x.minutes} minute read</div>
        ${x.body.map(par => `<p>${esc(par)}</p>`).join("")}
      </div>`).join("")}
    </div>

    <div id="ln-glossary" class="hidden" style="margin-top:20px">
      ${cats.map(c => `
        <h3 style="margin:22px 0 12px;font-size:17px">${esc(c)}</h3>
        <div class="gloss">${g.terms.filter(t => t.category === c).map(t => `
          <div class="gterm"><h4>${esc(t.term)}</h4>
            <p class="s">${esc(t.short)}</p><p class="l">${esc(t.long)}</p></div>`).join("")}
        </div>`).join("")}
    </div>

    <div id="ln-quiz" class="hidden" style="margin-top:20px">
      <div class="callout info">${esc(q.note)}</div>
      <div id="quiz-body">
        ${q.questions.map((qq, i) => `<div class="quiz-q">
          <div class="qt">${i + 1}. ${esc(qq.question)}</div>
          ${qq.options.map(o => `<label class="quiz-opt">
            <input type="radio" name="${esc(qq.id)}" value="${o.value}"
                   onchange="selectOpt(this)">
            <span>${esc(o.text)}</span></label>`).join("")}
        </div>`).join("")}
      </div>
      <button class="btn" onclick="submitQuiz()">See my risk profile</button>
      <div id="quiz-result"></div>
    </div>`;

  document.querySelectorAll("#ln-tabs .range").forEach(b => b.onclick = () => {
    document.querySelectorAll("#ln-tabs .range").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    ["lessons", "glossary", "quiz"].forEach(t =>
      document.getElementById("ln-" + t).classList.toggle("hidden", t !== b.dataset.t));
  });
}

function selectOpt(input) {
  const group = input.closest(".quiz-q");
  group.querySelectorAll(".quiz-opt").forEach(o => o.classList.remove("sel"));
  input.closest(".quiz-opt").classList.add("sel");
}

async function submitQuiz() {
  const answers = {};
  document.querySelectorAll("#quiz-body input[type=radio]:checked")
    .forEach(i => answers[i.name] = +i.value);
  const box = document.getElementById("quiz-result");
  try {
    const r = await post("/api/education/questionnaire", {answers});
    if (!r.complete) {
      box.innerHTML = `<div class="callout" style="margin-top:18px">${esc(r.reason)}</div>`;
      return;
    }
    const s = r.scores, meaning = r.score_meaning;
    box.innerHTML = `<div class="card" style="margin-top:20px">
      <div class="k">Your profile</div>
      <p class="big-num" style="font-size:30px">${esc(r.profile)}</p>
      <p style="color:var(--ink-2);font-size:15px;margin:4px 0 20px">${esc(r.summary)}</p>

      ${Object.entries(s).filter(([k]) => k !== "overall").map(([k, v]) => `
        <div style="margin-bottom:14px">
          <div style="display:flex;justify-content:space-between;font-size:13.5px">
            <span>${esc(k.replace(/_/g, " "))}</span>
            <span style="font-weight:600">${v == null ? "—" : v + "/100"}</span></div>
          <div class="meter"><i style="width:${v || 0}%"></i></div>
          <div class="muted" style="font-size:12.5px">${esc(meaning[k] || "")}</div>
        </div>`).join("")}

      <h4 style="margin:22px 0 8px;font-size:15px">What this tends to mean</h4>
      <ul style="color:var(--ink-2);font-size:14.5px;line-height:1.7;margin:0;padding-left:20px">
        ${r.what_this_means.map(m => `<li>${esc(m)}</li>`).join("")}</ul>

      ${r.tensions.length ? `<div class="callout" style="margin-top:18px">
        <strong>Worth thinking about.</strong>
        <ul style="margin:8px 0 0;padding-left:18px">
          ${r.tensions.map(t => `<li style="margin:6px 0">${esc(t)}</li>`).join("")}</ul>
      </div>` : ""}

      <h4 style="margin:22px 0 8px;font-size:15px">Where to go next</h4>
      <ul style="color:var(--ink-2);font-size:14.5px;line-height:1.7;margin:0;padding-left:20px">
        ${r.next_steps.map(t => `<li>${esc(t)}</li>`).join("")}</ul>

      <p class="disclaim">${esc(r.disclaimer)}</p>
    </div>`;
    box.scrollIntoView({behavior: "smooth", block: "start"});
  } catch (e) {
    box.innerHTML = `<div class="error" style="margin-top:18px">${esc(e.message)}</div>`;
  }
}
