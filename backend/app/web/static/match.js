/* EGX Research — find companies that match what you are looking for.

   What this is, and what it deliberately is not

   It is a screener that speaks plain English. You say what you are after --
   income, a steadier ride, the ability to sell quickly -- and it turns that
   into filters over measured figures, then shows you everything that clears
   them and tells you exactly which test each one passed.

   It is not a recommendation engine, and the difference is not cosmetic.

   A recommender asks about you -- your age, your savings, your nerve -- and
   returns a shortlist that carries an implicit "this suits you". That is
   personalised investment advice. It needs a licence this project does not
   have, it requires knowing things about a person that a web page cannot
   responsibly hold, and it moves the decision from the reader to the site.

   This asks about the SHARES, never about you. "Which companies pay more than
   5% and have covered it for three years" is a question about the exchange
   with a checkable answer. "Which companies suit a 45-year-old with two
   children" is a question about a person, and the honest answer is that a
   website cannot know.

   So every filter here is a property of a company, the reader chooses which
   ones matter, the workings are shown, and the list is never ordered by how
   good we think anything is -- you pick the sort. What comes back is a set of
   companies that match a description, which is a fact, rather than a set of
   companies that are right for you, which is a judgement nobody here can make.
*/

/* Each goal is a plain-English wish, and the measured tests it becomes.
   Every test names a field the site already publishes, so a reader can check
   any of them on the company's own page. */
const MATCH_GOALS = [
  {
    id: "income",
    label: "Regular income",
    blurb: "Companies that pay a meaningful dividend and have kept paying it.",
    tests: [
      {field: "dividend_yield_pct", op: ">=", value: 4,
       says: "pays at least 4% a year in cash"},
      {field: "payout_ratio_pct", op: "<=", value: 90, optional: true,
       says: "pays out no more than 90% of its profit, so the dividend is covered"},
    ],
  },
  {
    id: "steady",
    label: "A steadier ride",
    blurb: "Less violent price movement than the exchange usually delivers.",
    tests: [
      {field: "volatility_pct", op: "<=", value: 35,
       says: "swings less than 35% a year, against a market where 45% is common"},
      {field: "max_drawdown_pct", op: ">=", value: -55,
       says: "its worst fall on our history stayed above -55%"},
    ],
  },
  {
    id: "sellable",
    label: "Easy to sell",
    blurb: "Enough trades every day that an ordinary order does not move the price.",
    tests: [
      {field: "adtv_90d", op: ">=", value: 5000000,
       says: "trades at least EGP 5m of value a day"},
      {field: "days_traded_90d", op: ">=", value: 60,
       says: "traded on at least 60 of the last 90 sessions"},
    ],
  },
  {
    id: "profitable",
    label: "Consistently profitable",
    blurb: "Earns a real return on the money shareholders have put in.",
    tests: [
      {field: "roe_pct", op: ">=", value: 15,
       says: "earns at least 15% on shareholders' money"},
      {field: "net_margin_pct", op: ">=", value: 5,
       says: "keeps at least 5% of every pound of sales as profit"},
    ],
  },
  {
    id: "growing",
    label: "Growing",
    blurb: "Sales actually increasing, and by more than inflation.",
    tests: [
      {field: "revenue_growth_pct", op: ">=", value: 20,
       says: "grew revenue at least 20% last year, above Egyptian inflation"},
    ],
  },
  {
    id: "cheap",
    label: "Cheaply priced",
    blurb: "Priced low against its own earnings and book value.",
    tests: [
      {field: "pe", op: "<=", value: 10,
       says: "costs no more than 10 years of current profit"},
      {field: "pb", op: "<=", value: 2,
       says: "priced at no more than twice its book value"},
    ],
  },
  {
    id: "lowdebt",
    label: "Little borrowing",
    blurb: "Not depending on lenders to keep going.",
    tests: [
      {field: "debt_to_equity", op: "<=", value: 0.6,
       says: "borrows less than 60p for every pound of shareholders' money"},
    ],
  },
  {
    id: "documented",
    label: "Well documented",
    blurb: "Full accounts available, so the figures can actually be checked.",
    tests: [
      {field: "data_quality", op: "in", value: ["full"],
       says: "has complete published accounts, not just prices"},
    ],
  },
];

function matchPasses(row, test) {
  const v = row[test.field];
  if (v == null) return null;                       // unmeasured, not failed
  if (test.op === ">=") return v >= test.value;
  if (test.op === "<=") return v <= test.value;
  if (test.op === "in") return test.value.includes(v);
  return null;
}


/* ---------------- the page ---------------- */

let MATCH_ON = new Set(["income"]);
let MATCH_SORT = "market_cap";

async function viewMatch(view) {
  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>${esc(t("match.title", "Find companies that match what you are looking for"))}</h2>
      <p>${esc(t("match.lede",
        "Pick what matters to you. Every choice becomes a test over published figures, and every company that comes back shows which tests it passed. Nothing here is ordered by how good we think it is."))}</p>
    </div>

    <div class="callout info">
      <strong>${esc(t("match.notadvice.title", "This asks about the shares, never about you."))}</strong>
      ${esc(t("match.notadvice.body",
        "It will not ask your age, your savings or how much risk you can afford, and it will not tell you what suits you. Which companies pay above 4% is a question about the exchange and has a checkable answer. Which companies suit you is a question about your life, and a web page cannot know it. You choose the tests; the list is simply what matched."))}
    </div>

    <div class="card">
      <div class="card-head"><h2>${esc(t("match.what", "What are you looking for?"))}</h2>
        <p class="sub">${esc(t("match.what.sub", "Choose as many as you like. More choices mean fewer companies."))}</p></div>
      <div id="match-goals" class="goalgrid"></div>
    </div>

    <div id="match-out"></div>`;

  renderGoals();
  await runMatch();
}

function renderGoals() {
  document.getElementById("match-goals").innerHTML = MATCH_GOALS.map(g => `
    <button class="goal${MATCH_ON.has(g.id) ? " on" : ""}" type="button"
            onclick="toggleGoal('${g.id}')" aria-pressed="${MATCH_ON.has(g.id)}">
      <span class="gl">${esc(g.label)}</span>
      <span class="gb">${esc(g.blurb)}</span>
    </button>`).join("");
}

function toggleGoal(id) {
  if (MATCH_ON.has(id)) MATCH_ON.delete(id);
  else MATCH_ON.add(id);
  renderGoals();
  runMatch();
}

async function runMatch() {
  const box = document.getElementById("match-out");
  if (!box) return;
  const metrics = await api("/api/metrics");
  const goals = MATCH_GOALS.filter(g => MATCH_ON.has(g.id));

  if (!goals.length) {
    box.innerHTML = `<div class="card"><p class="muted">${esc(t("match.none",
      "Choose at least one thing above and the matching companies appear here."))}</p></div>`;
    return;
  }

  const tests = goals.flatMap(g => g.tests);
  const rows = [];
  let excluded = 0;

  for (const [ticker, m] of Object.entries(metrics)) {
    if (m.units_suspect) continue;
    const row = Object.assign({}, m, {ticker});
    // Derived here: a payout ratio is the dividend divided by the earnings,
    // and both of those are already published.
    row.payout_ratio_pct = (m.dividend_yield_pct != null && m.pe != null && m.pe > 0)
      ? m.dividend_yield_pct * m.pe : null;

    const results = tests.map(x => ({test: x, pass: matchPasses(row, x)}));
    const required = results.filter(r => !r.test.optional);
    // A missing measure is not a pass. A company we cannot check is excluded
    // and counted, never quietly admitted on the strength of a blank.
    if (required.some(r => r.pass !== true)) {
      if (required.some(r => r.pass === null)) excluded++;
      continue;
    }
    row._passed = results.filter(r => r.pass === true).map(r => r.test.says);
    rows.push(row);
  }

  rows.sort((a, b) => {
    const av = a[MATCH_SORT], bv = b[MATCH_SORT];
    if (av == null) return 1;
    if (bv == null) return -1;
    return bv - av;
  });
  box.innerHTML = matchResults(rows, goals, excluded);
}

const MATCH_SORTS = [
  ["market_cap", "Size"], ["dividend_yield_pct", "Dividend yield"],
  ["roe_pct", "Return on equity"], ["revenue_growth_pct", "Revenue growth"],
  ["adtv_90d", "Daily value traded"], ["ret_1y", "Past year"],
];

function matchResults(rows, goals, excluded) {
  const head = `${count(rows.length)} ${rows.length === 1 ? "company matches" : "companies match"}`;

  const empty = `<div class="callout"><strong>Nothing matched.</strong>
      Every test has to pass at once, and on an exchange this size that
      combination may simply not exist. Remove one and try again.</div>`;

  const table = `
    <div class="form-row" style="margin-bottom:12px">
      <div class="field"><label>Order by</label>
        <select id="match-sort" onchange="MATCH_SORT=this.value;runMatch()">
          ${MATCH_SORTS.map(pair => `<option value="${pair[0]}"${
            pair[0] === MATCH_SORT ? " selected" : ""}>${esc(pair[1])}</option>`).join("")}
        </select></div>
    </div>

    <div class="table-scroll"><table class="tbl">
      <thead><tr><th>Ticker</th><th style="text-align:left">Company</th>
        <th>Price</th><th>Yield</th><th>P/E</th><th>ROE</th>
        <th>1 year</th><th style="text-align:left">Trades</th></tr></thead>
      <tbody>${rows.slice(0, 60).map(r => `<tr onclick="go('/stock/${esc(r.ticker)}')">
        <td class="tk">${esc(r.ticker)}</td>
        <td style="text-align:left;max-width:230px">
          <div style="overflow:hidden;text-overflow:ellipsis">${esc(r.name)}</div>
          <div style="font-size:11.5px;color:var(--ink-3)">${
            esc((r._passed || []).slice(0, 2).join(" · "))}</div></td>
        <td>${price(r.price)}</td>
        <td>${pctPlain(r.dividend_yield_pct, 2)}</td>
        <td>${mult(r.pe)}</td>
        <td>${pctPlain(r.roe_pct, 1)}</td>
        <td class="${cls(r.ret_1y)}">${pct(r.ret_1y)}</td>
        <td style="text-align:left">${liquidityBadge(r.liquidity_band)
          || `<span class="muted" style="font-size:12px">${esc(r.liquidity_band || "—")}</span>`}</td>
      </tr>`).join("")}</tbody>
    </table></div>
    ${rows.length > 60 ? `<p class="muted" style="font-size:12.5px;margin-top:10px">
      Showing the first 60 of ${count(rows.length)}.</p>` : ""}`;

  const left = excluded ? `<div class="callout" style="margin-top:14px">
      <strong>${count(excluded)} companies were left out because we could not
      check them.</strong> One of the measures you chose is not published for
      them. They are not failing the test — we simply cannot tell, and a
      blank is not a pass.</div>` : "";

  return `<div class="card">
    <div class="card-head"><h2>${head}</h2>
      <p class="sub">${esc(goals.map(g => g.label.toLowerCase()).join(" · "))}</p></div>

    ${rows.length ? table : empty}
    ${left}

    <div style="margin-top:16px">
      <h4 style="font-size:14px;margin:0 0 8px">What each company here had to clear</h4>
      <ul style="margin:0;padding-inline-start:20px;font-size:13.5px;
                 color:var(--ink-2);line-height:1.8">
        ${goals.flatMap(g => g.tests).map(x => `<li>${esc(x.says)}${
          x.optional ? " <em>(where published)</em>" : ""}</li>`).join("")}
      </ul>
    </div>

    <p class="disclaim">${esc(t("match.disclaim",
      "A list of companies matching a description you chose. It is not a recommendation, it is not ranked by quality, and it says nothing about whether any of these suits you. The thresholds are ours and are written out above so you can disagree with them."))}</p>
  </div>`;
}
