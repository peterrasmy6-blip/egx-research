/* EGX Research — page views. */

/* =======================================================================
   HOME
   ======================================================================= */
function viewHome(view) {
  const tiles = [
    ["🔍", "Research a company", "Prices, profits, ratios and financial statements for every listed Egyptian company.", "/markets"],
    ["⏳", "What if I had invested?", "See what a real investment would actually have done — including dividends and inflation.", "/scenario"],
    ["⚖️", "Fair value", "Model estimates of what a company might be worth, with the assumptions shown.", "/markets"],
    ["🎛️", "Screener", "Filter the whole exchange by value, quality, growth and risk.", "/screener"],
    ["📊", "Compare companies", "Put several companies side by side on the same measures.", "/compare"],
    ["🧪", "Backtest a portfolio", "Test how a mix of shares would have performed, with rebalancing and costs.", "/backtest"],
    ["🔮", "Future scenarios", "Projections and Monte Carlo simulations — ranges, not predictions.", "/forecast"],
    ["🧭", "Forecast a portfolio", "Build a portfolio today and model how it might behave over the years ahead.", "/plan"],
    ["🎓", "Learn investing", "Plain-English explanations of every term used on this site.", "/learn"],
  ];

  const top = [...UNIVERSE].filter(s => s.ret_1y != null)
    .sort((a, b) => b.ret_1y - a.ret_1y);
  const gainers = top.slice(0, 5);
  const losers = top.slice(-5).reverse();
  const biggest = [...UNIVERSE].filter(s => s.market_cap)
    .sort((a, b) => b.market_cap - a.market_cap).slice(0, 8);

  const movers = (rows, label) => `
    <div class="card">
      <div class="card-head"><h2>${label}</h2><p class="sub">Total return over the last year.</p></div>
      <div class="table-scroll"><table class="tbl"><tbody>
        ${rows.map(s => `<tr onclick="go('/stock/${esc(s.ticker)}')">
          <td class="tk">${esc(s.ticker)}</td>
          <td style="text-align:left;color:var(--ink-2);max-width:200px;overflow:hidden;text-overflow:ellipsis">${esc(s.name.slice(0, 34))}</td>
          <td>${price(s.price)}</td>
          <td class="${cls(s.ret_1y)}" style="font-weight:600">${pct(s.ret_1y)}</td>
        </tr>`).join("")}
      </tbody></table></div>
    </div>`;

  view.innerHTML = `
    <div class="hero">
      <h1>Understand the Egyptian stock market before you invest in it.</h1>
      <p class="lede">Free research, valuation and historical analysis covering
        the whole Egyptian Exchange. Every number is calculated from real market
        prices and company filings — never estimated, never invented.</p>
    </div>

    <div class="tiles">
      ${tiles.map(([ic, h, p, r]) => `<div class="tile" onclick="go('${r}')">
        <span class="ic">${ic}</span><h3>${esc(h)}</h3><p>${esc(p)}</p></div>`).join("")}
    </div>

    <div class="callout info" style="margin-top:26px">
      <strong>Research. Understand. Decide.</strong>
      This site gives you the information and the tools. It deliberately does not
      tell you what to buy, sell, or how to divide your money — those decisions
      depend on your own circumstances and are yours to make.
    </div>

    <div class="section-head">
      <h2>The exchange at a glance</h2>
      <p>${count(STATUS.companies_confirmed)} companies with market data · ${count(STATUS.funds)} funds ·
         ${count(STATUS.securities_with_prices)} with price history ·
         ${count(STATUS.securities_with_statements)} with financial statements ·
         data to ${esc(STATUS.latest_market_date || "—")}</p>
      <p class="muted" style="font-size:13px;margin-top:6px">
        Every company here is an ordinary listed share. Rights issues, the
        EGX30 ETF, certificates and second share classes of the same company
        are deliberately not counted as companies — they would double-count a
        business or list something that is not one.
        ${count(STATUS.companies_retired)} tickers that appeared in the raw
        source rosters were retired: renamed years ago, no longer on the
        exchange, or not a company at all. Where a company has no market data
        it is still searchable and marked <em>No data</em>.</p>
    </div>

    <div class="grid-2">
      ${movers(gainers, "Strongest 12 months")}
      ${movers(losers, "Weakest 12 months")}
    </div>

    <div class="card">
      <div class="card-head"><h2>Largest companies</h2>
        <p class="sub">By market value. Size is not the same as quality.</p></div>
      <div class="uni-grid">
        ${biggest.map(s => `<div class="uni" onclick="go('/stock/${esc(s.ticker)}')">
          <div class="tk">${esc(s.ticker)}</div>
          <div class="nm">${esc(s.name)}</div>
          <div class="bot"><span>${bigMoney(s.market_cap)}</span>
            <span class="${cls(s.ret_1y)}">${pct(s.ret_1y)}</span></div>
        </div>`).join("")}
      </div>
      <p style="margin-top:16px"><a href="#/markets" onclick="go('/markets')">See all companies →</a></p>
    </div>`;
}

/* =======================================================================
   MARKETS — full universe browser
   ======================================================================= */
let mktState = {sector: null, q: "", sort: "market_cap", desc: true, kind: "equity"};

function viewMarkets(view) {
  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>All Egyptian Exchange companies</h2>
      <p>Every listed company we could discover from public sources. Companies
         with incomplete data are kept in the list and labelled, not hidden.</p>
    </div>
    <div class="card">
      <div class="form-row">
        <div class="field"><label>Filter by name or ticker</label>
          <input id="mkt-q" type="text" placeholder="e.g. bank, CIB, real estate"></div>
        <div class="field"><label>Sort by</label>
          <select id="mkt-sort">
            <option value="market_cap">Market value</option>
            <option value="ret_1y">1-year return</option>
            <option value="ticker">Ticker</option>
            <option value="name">Name</option>
          </select></div>
      </div>
      <div class="ranges" id="mkt-kind" style="margin-bottom:12px">
        <button class="range on" data-k="equity">Shares</button>
        <button class="range" data-k="fund">Funds</button>
        <button class="range" data-k="all">Everything</button>
      </div>
      <div class="chips" id="mkt-sectors"></div>
    </div>

    <div class="card" id="composite-card">
      <div class="card-head"><h2>How the market has moved</h2>
        <p class="sub">Loading…</p></div>
      <div id="composite-body"></div>
    </div>

    <div id="mkt-body"></div>`;

  const chips = document.getElementById("mkt-sectors");
  chips.innerHTML = `<button class="chip on" data-s="">All sectors</button>` +
    SECTORS.map(s => `<button class="chip" data-s="${esc(s.sector)}">${esc(s.sector)} (${count(s.count)})</button>`).join("");
  chips.querySelectorAll(".chip").forEach(c => c.onclick = () => {
    chips.querySelectorAll(".chip").forEach(x => x.classList.remove("on"));
    c.classList.add("on");
    mktState.sector = c.dataset.s || null;
    renderMarkets();
  });
  document.getElementById("mkt-q").oninput = e => {
    mktState.q = e.target.value.toLowerCase(); renderMarkets();
  };
  document.getElementById("mkt-sort").onchange = e => {
    mktState.sort = e.target.value; renderMarkets();
  };
  document.querySelectorAll("#mkt-kind .range").forEach(b => b.onclick = () => {
    document.querySelectorAll("#mkt-kind .range").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    mktState.kind = b.dataset.k;
    renderMarkets();
  });
  renderMarkets();
  loadComposite();
}

async function loadComposite() {
  const card = document.getElementById("composite-card");
  const body = document.getElementById("composite-body");
  if (!body) return;
  try {
    const [c, note] = await Promise.all([
      api("/api/market/composite?years=7"),
      api("/api/market/indices-note"),
    ]);
    if (!c.available) {
      body.innerHTML = `<div class="callout">${esc(c.reason)}</div>`;
      return;
    }
    card.querySelector(".sub").textContent =
      `${c.members} companies, equally weighted, ${c.start_date} to ${c.end_date}.`;

    body.innerHTML = `
      <div class="callout"><strong>This is not the EGX30.</strong>
        ${esc(note.explanation)} ${esc(note.what_we_did_instead)}</div>

      <div class="stats">
        <div class="stat"><div class="k">Total change</div>
          <div class="v ${cls(c.total_return_pct)}">${pct(c.total_return_pct)}</div>
          <div class="note">over ${c.years} years</div></div>
        <div class="stat"><div class="k">Per year</div>
          <div class="v ${cls(c.cagr_pct)}">${pct(c.cagr_pct)}</div>
          <div class="note">before inflation</div></div>
        <div class="stat"><div class="k">Volatility</div>
          <div class="v">${pctPlain(c.volatility_pct)}</div></div>
        <div class="stat"><div class="k">Worst fall</div>
          <div class="v down">${pctPlain(c.max_drawdown_pct)}</div>
          <div class="note">peak to trough</div></div>
      </div>

      <div class="chart-box"><canvas id="comp-chart"></canvas></div>

      <details class="assump" open>
        <summary>What this reference does and does not tell you</summary>
        <ul>${c.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul>
        <p style="margin-top:8px"><strong>Method.</strong> ${esc(c.method)}</p>
      </details>`;

    lineChart("comp-chart", c.points.map(p => p.d), [{
      label: "Market reference (starts at 1,000)",
      data: c.points.map(p => p.v), borderColor: GREEN, borderWidth: 2,
      pointRadius: 0, tension: .1,
      backgroundColor: "rgba(11,107,94,.07)", fill: true,
    }], {money: false, title: "Broad EGX market reference — built from our own data"});
  } catch (e) {
    body.innerHTML = `<div class="callout">Market reference unavailable: ${esc(e.message)}</div>`;
  }
}

function renderMarkets() {
  let rows = UNIVERSE.filter(s =>
    mktState.kind === "all" ? true : s.asset_type === mktState.kind);
  if (mktState.sector) rows = rows.filter(s => s.sector === mktState.sector);
  if (mktState.q) rows = rows.filter(s =>
    s.ticker.toLowerCase().includes(mktState.q) ||
    s.name.toLowerCase().includes(mktState.q) ||
    (s.sector || "").toLowerCase().includes(mktState.q));

  const k = mktState.sort;
  rows.sort((a, b) => {
    if (k === "ticker") return a.ticker.localeCompare(b.ticker);
    if (k === "name") return a.name.localeCompare(b.name);
    const av = a[k], bv = b[k];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return bv - av;
  });

  document.getElementById("mkt-body").innerHTML = `
    <div class="card">
      <p class="muted" style="margin:0 0 14px;font-size:13.5px">
        Showing ${count(rows.length)} of ${count(UNIVERSE.length)} securities.</p>
      <div class="table-scroll"><table class="tbl">
        <thead><tr><th>Ticker</th><th style="text-align:left">Company</th>
          <th style="text-align:left">Sector</th><th>Price</th><th>Day</th>
          <th>1 year</th><th>Market value / risk</th><th style="text-align:left">Data</th></tr></thead>
        <tbody>${rows.map(s => `<tr onclick="go('/stock/${esc(s.ticker)}')">
          <td class="tk">${esc(s.ticker.replace(/^FUND-/, ""))}${
            s.asset_type === "fund" ? ' <span class="picker-tag fund">Fund</span>' : ""}</td>
          <td style="text-align:left;max-width:250px;overflow:hidden;text-overflow:ellipsis">${esc(s.name)}</td>
          <td style="text-align:left;color:var(--ink-3);font-size:12.5px">${esc(s.sector || "—")}</td>
          <td>${price(s.price)}</td>
          <td class="${cls(s.day_change_pct)}">${pct(s.day_change_pct)}</td>
          <td class="${cls(s.ret_1y)}" style="font-weight:600">${pct(s.ret_1y)}</td>
          <td>${s.asset_type === 'fund' ? (s.fund && s.fund.risk ? esc(s.fund.risk) : '—') : bigMoney(s.market_cap)}</td>
          <td style="text-align:left">${qualityBadge(s.data_quality)}${
            s.price == null
              ? ' <span class="badge none" title="Listed, but no free source carries its prices">No data</span>'
              : ""}</td>
        </tr>`).join("")}</tbody>
      </table></div>
    </div>`;
}

/* =======================================================================
   COMPANY PAGE
   ======================================================================= */
async function viewCompany(view, args) {
  const ticker = decodeURIComponent(args[0] || "COMI");
  const d = await api("/api/security/" + encodeURIComponent(ticker));
  const q = d.data_quality, v = d.valuation || {}, qual = d.quality || {},
        perf = d.performance || {}, risk = d.risk || {};

  const stat = (k, val, note) => `<div class="stat"><div class="k">${k}</div>
    <div class="v">${val == null ? "—" : val}</div>
    ${note ? `<div class="note">${note}</div>` : ""}</div>`;

  view.innerHTML = `
    <button class="back" onclick="history.back()">← Back</button>
    <div class="co-head">
      <div>
        <h1>${esc(d.name)}</h1>
        <div class="muted">${esc(d.ticker)} · Egyptian Exchange${d.isin ? " · " + esc(d.isin) : ""}</div>
        <div class="co-tags">
          ${d.sector ? `<span class="tag">${esc(d.sector)}</span>` : ""}
          ${qualityBadge(q.status)}
          ${d.listing_status !== "listed" ? `<span class="badge low">${esc(d.listing_status)}</span>` : ""}
        </div>
      </div>
      <div class="px">
        <div class="p">${price(d.price)}</div>
        <div class="d ${cls(d.day_change_pct)}">${pct(d.day_change_pct)}</div>
        <div class="t">as of ${esc(d.price_date || "—")}${q.is_stale ? " · not today's price" : ""}</div>
      </div>
    </div>

    ${d.price == null ? `<div class="callout">
      <strong>No market data available for this company.</strong>
      It is a listed EGX company, but no free source carries its prices — so we
      have no prices, no ratios and no valuation for it. That does not mean it
      cannot be traded; it means this site has nothing to show you about it.
      </div>` : ""}


    ${q.note ? `<div class="callout"><strong>${esc(q.label)} data.</strong> ${esc(q.note)}</div>` : ""}

    ${q.units_suspect ? `<div class="callout">
      <strong>Per-share figures are not shown for this security.</strong>
      Its quoted price and its published accounts do not appear to be in the
      same currency — several Egyptian companies have a second share class
      quoted in US dollars while filing their accounts in pounds. Dividing one
      by the other would produce a spectacular but meaningless bargain, so we
      show nothing instead.</div>` : ""}

    ${q.price_integrity === "discontinuous" ? `<div class="callout">
      <strong>Some long-term returns are hidden for this company.</strong>
      Its price history contains a jump that trading cannot explain — the
      Egyptian Exchange limits daily moves to roughly 10–20%, so a bigger
      one-day change is a share split or consolidation that our data source
      did not apply to the earlier history. Returns measured across
      ${esc(q.price_safe_from || "that date")} would be wrong, so we show
      nothing instead of a fabricated percentage.</div>` : ""}

    ${d.fund ? `<div class="card">
      <div class="card-head"><h2>Fund details</h2>
        <p class="sub">Published by ${esc(d.data_quality.source)}.</p></div>
      <div class="stats">
        <div class="stat"><div class="k">Current value (NAV)</div>
          <div class="v">${price(d.fund.nav)}</div><div class="note">per unit</div></div>
        <div class="stat"><div class="k">This year</div>
          <div class="v ${cls(d.fund.ytd_pct)}">${pct(d.fund.ytd_pct)}</div></div>
        <div class="stat"><div class="k">Past year</div>
          <div class="v ${cls(d.fund.return_1y_pct)}">${pct(d.fund.return_1y_pct)}</div></div>
        <div class="stat"><div class="k">Since it started</div>
          <div class="v ${cls(d.fund.since_inception_pct)}">${pct(d.fund.since_inception_pct)}</div></div>
        <div class="stat"><div class="k">Type</div>
          <div class="v" style="font-size:15px">${esc(d.fund.fund_type || "—")}</div></div>
        <div class="stat"><div class="k">Risk band</div>
          <div class="v" style="font-size:15px">${esc(d.fund.risk || "—")}</div></div>
      </div>
      <div class="callout"><strong>What this fund cannot do here.</strong>
        Our free source publishes this fund's current value and its recent
        returns, but not a history of daily values. Without that history the
        what-if calculator, backtesting and Monte Carlo have nothing to work
        from, so they are not offered for funds. Shares have full histories and
        can use all of those tools.</div>
    </div>` : ""}

    ${d.asset_type === "fund" ? "" : `<div class="card">
      <div class="card-head"><h2>Performance</h2>
        <p class="sub">Total return including dividends.</p></div>
      <div class="stats">
        ${["1W","1M","3M","6M","1Y","3Y","5Y"].map(k =>
          `<div class="stat"><div class="k">${k}</div>
           <div class="v ${cls(perf[k])}">${pct(perf[k])}</div></div>`).join("")}
      </div>
      <div class="ranges" id="co-ranges">
        ${["1y","3y","5y","max"].map(r =>
          `<button class="range${r === "5y" ? " on" : ""}" data-r="${r}">${r.toUpperCase()}</button>`).join("")}
      </div>
      <div class="chart-box"><canvas id="co-chart"></canvas></div>
      ${d.high_52w ? `<p class="muted" style="font-size:13px;margin:0">
        52-week range: ${price(d.low_52w)} – ${price(d.high_52w)}</p>` : ""}
    </div>`}

    <div class="card">
      <div class="card-head"><h2>Key numbers</h2>
        <p class="sub">Calculated from this company's own filings${q.latest_statement ? ` (latest: ${esc(q.latest_statement)})` : ""}.</p></div>
      <div class="stats">
        ${stat("Market value", bigMoney(d.market_cap), "what the whole company is worth")}
        ${stat("Price / earnings", mult(v.pe), "years of profit you pay for")}
        ${stat("Price / book", mult(v.pb), "price vs accounting value")}
        ${stat("Earnings per share", v.eps != null ? price(v.eps) : null, "profit per share")}
        ${stat("Dividend yield", v.dividend_yield_pct != null ? pctPlain(v.dividend_yield_pct, 2) : null, "cash paid ÷ price")}
        ${stat("Return on equity", qual.roe_pct != null ? pctPlain(qual.roe_pct) : null, "profit on shareholders' money")}
        ${stat("Net margin", qual.net_margin_pct != null ? pctPlain(qual.net_margin_pct) : null, "profit per pound of sales")}
        ${stat("Revenue growth", qual.revenue_growth_pct != null ? pct(qual.revenue_growth_pct, 1) : null, "latest year")}
        ${stat("Debt / equity", mult(qual.debt_to_equity), "borrowing vs own money")}
        ${stat("Volatility", risk.volatility_pct != null ? pctPlain(risk.volatility_pct) : null, "how much it swings")}
        ${stat("Worst fall", risk.max_drawdown_pct != null ? pctPlain(risk.max_drawdown_pct) : null, "biggest historic drop")}
        ${stat("EV / EBITDA", mult(v.ev_ebitda), "value vs operating profit")}
      </div>
      ${q.missing && q.missing.length ? `<div class="callout">
        <strong>Not every measure applies.</strong> This company does not report
        ${esc(q.missing.join(", ").replace(/_/g, " "))}. That is normal — banks and
        insurers do not report the same lines as manufacturers. We leave these blank
        rather than substitute a number.</div>` : ""}
    </div>

    <div class="card" id="val-card">
      <div class="card-head"><h2>What might it be worth?</h2>
        <p class="sub">A model estimate from stated assumptions — not a price target.</p></div>
      <div id="val-body"><p class="muted">Calculating…</p></div>
    </div>

    <div class="card">
      <div class="card-head"><h2>Financial history</h2>
        <p class="sub">Straight from the annual statements.</p></div>
      <div class="ranges" id="fin-freq">
        <button class="range on" data-f="annual">Annual</button>
        <button class="range" data-f="quarterly">Quarterly</button>
      </div>
      <div id="fin-body" style="margin-top:14px"><p class="muted">Loading…</p></div>
    </div>

    <div class="card">
      <div class="card-head"><h2>Dividends</h2>
        <p class="sub">Cash paid per share, by ex-dividend date.</p></div>
      <div id="div-body"><p class="muted">Loading…</p></div>
    </div>

    <div class="card">
      <div class="card-head"><h2>Try this company in the tools</h2></div>
      <div class="chips">
        <button class="chip" onclick="go('/scenario/${esc(d.ticker)}')">What if I had invested?</button>
        <button class="chip" onclick="go('/forecast/${esc(d.ticker)}')">Future scenarios</button>
        <button class="chip" onclick="go('/compare/${esc(d.ticker)}')">Compare with others</button>
      </div>
    </div>

    <p class="disclaim">${esc(d.disclaimer)}</p>`;

  document.querySelectorAll("#co-ranges .range").forEach(b => b.onclick = () => {
    document.querySelectorAll("#co-ranges .range").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    loadPriceChart(d.ticker, b.dataset.r);
  });
  document.querySelectorAll("#fin-freq .range").forEach(b => b.onclick = () => {
    document.querySelectorAll("#fin-freq .range").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    loadFinancials(d.ticker, b.dataset.f);
  });

  loadPriceChart(d.ticker, "5y");
  loadFinancials(d.ticker, "annual");
  loadDividends(d.ticker);
  loadValuation(d.ticker);
}

async function loadPriceChart(ticker, range) {
  try {
    const px = await api(`/api/security/${encodeURIComponent(ticker)}/prices?range=${range}`);
    if (!px.points || !px.points.length) {
      document.getElementById("co-chart").parentElement.innerHTML =
        `<p class="muted">No price history available for this period.</p>`;
      return;
    }
    lineChart("co-chart", px.points.map(p => p.d), [{
      label: "Price", data: px.points.map(p => p.c),
      borderColor: GREEN, borderWidth: 2, pointRadius: 0, tension: .12,
      backgroundColor: "rgba(11,107,94,.07)", fill: true,
    }]);
  } catch (e) {}
}

async function loadValuation(ticker) {
  const body = document.getElementById("val-body");
  try {
    const v = await api(`/api/security/${encodeURIComponent(ticker)}/valuation`);
    if (!v.available) {
      body.innerHTML = `<div class="callout"><strong>Fair value not available.</strong>
        ${esc(v.reason)}</div>
        ${v.rationale ? `<p class="muted" style="font-size:13.5px">${esc(v.rationale)}</p>` : ""}`;
      return;
    }
    const lo = Math.min(v.bear, v.price) * 0.92, hi = Math.max(v.bull, v.price) * 1.08;
    const posOf = x => ((x - lo) / (hi - lo)) * 100;

    body.innerHTML = `
      <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-bottom:6px">
        ${valuationBand(v.classification)}
        <span class="muted" style="font-size:13.5px">${esc(v.classification_note)}</span>
      </div>

      <div class="vrange">
        <div class="vbar">
          <div class="vmark above" style="left:${posOf(v.bear)}%"><span>Bear ${price(v.bear)}</span></div>
          <div class="vmark below" style="left:${posOf(v.base)}%"><span>Base ${price(v.base)}</span></div>
          <div class="vmark above" style="left:${posOf(v.bull)}%"><span>Bull ${price(v.bull)}</span></div>
          <div class="vmark price below" style="left:${posOf(v.price)}%"><span>Price ${price(v.price)}</span></div>
        </div>
        <div class="vlabels"><span>${price(lo)}</span><span>${price(hi)}</span></div>
      </div>

      <div class="stats">
        <div class="stat"><div class="k">Current price</div><div class="v">${price(v.price)}</div></div>
        <div class="stat"><div class="k">Model estimate (base)</div><div class="v">${price(v.base)}</div>
          <div class="note">range ${price(v.bear)} – ${price(v.bull)}</div></div>
        <div class="stat"><div class="k">Difference</div>
          <div class="v ${cls(v.upside_pct)}">${pct(v.upside_pct, 1)}</div>
          <div class="note">vs the model's base case</div></div>
        <div class="stat"><div class="k">Confidence</div><div class="v">${v.confidence}/100</div>
          <div class="note">${v.method_spread_pct != null ? `methods differ by ${pctPlain(v.method_spread_pct)}` : "based on data coverage"}</div></div>
      </div>

      <div class="callout info"><strong>Why these methods?</strong> ${esc(v.rationale)}</div>

      ${v.rate_note ? `<div class="callout"><strong>Why Egyptian shares can look
        expensive.</strong> ${esc(v.rate_note)}</div>` : ""}

      <h4 style="margin:22px 0 10px;font-size:15px">How each method sees it</h4>
      ${v.methods.map(m => `<div class="method">
        <h4>${esc(m.method)}</h4>
        <p class="exp">${esc(m.explanation)}</p>
        <div class="nums">
          <span>Bear <b>${price(m.per_share.bear)}</b></span>
          <span>Base <b>${price(m.per_share.base)}</b></span>
          <span>Bull <b>${price(m.per_share.bull)}</b></span>
        </div></div>`).join("")}

      ${v.methods_skipped && v.methods_skipped.length ? `<div class="callout">
        <strong>Methods we could not use.</strong>
        ${v.methods_skipped.map(s => `${esc(s[0])} — ${esc(s[1])}`).join("; ")}.
        We leave these out rather than force a model that does not fit.</div>` : ""}

      <details class="assump"><summary>Confidence: why ${v.confidence}/100</summary>
        <ul>${v.confidence_reasons.map(r => `<li>${esc(r)}</li>`).join("")}</ul></details>

      <details class="assump"><summary>The assumptions behind these numbers</summary>
        <ul>
          <li>Risk-free rate: ${pctPlain(v.assumptions.risk_free_rate * 100)} — long-dated Egyptian government yield. This is the single most important input.</li>
          <li>Equity risk premium: ${pctPlain(v.assumptions.equity_risk_premium * 100)} above government paper.</li>
          <li>Long-run growth: ${pctPlain(v.assumptions.terminal_growth * 100)} a year, roughly long-run inflation plus real growth.</li>
          <li>Cost of debt: ${pctPlain(v.assumptions.cost_of_debt * 100)}; tax rate ${pctPlain(v.assumptions.tax_rate * 100)}.</li>
        </ul>
        <p style="margin-top:8px">Using a European discount rate of 8% instead of
        ${pctPlain(v.assumptions.risk_free_rate * 100)} would roughly double every
        valuation on this site — and every one of them would be wrong.</p>
      </details>

      <p class="disclaim">${esc(v.disclaimer)}</p>`;
  } catch (e) {
    body.innerHTML = `<div class="callout">Fair value could not be calculated: ${esc(e.message)}</div>`;
  }
}

async function loadFinancials(ticker, freq) {
  const body = document.getElementById("fin-body");
  body.innerHTML = `<p class="muted">Loading…</p>`;
  try {
    const f = await api(`/api/security/${encodeURIComponent(ticker)}/fundamentals?frequency=${freq}`);
    if (!f.available) {
      body.innerHTML = `<div class="callout"><strong>Not available.</strong> ${esc(f.reason)}</div>`;
      return;
    }
    const h = f.history.slice(0, 6);
    const m = n => n == null ? "—" : bigNum(n);
    const p = n => n == null ? "—" : nf(n * 100, 1) + "%";
    const rows = [
      ["Revenue", h.map(x => m(x.values.revenue))],
      ["Revenue growth", h.map(x => p(x.growth?.revenue))],
      ["Operating profit", h.map(x => m(x.values.operating_income))],
      ["Net profit", h.map(x => m(x.values.net_income))],
      ["Net margin", h.map(x => p(x.margins.net_margin))],
      ["Return on equity", h.map(x => p(x.returns.roe))],
      ["Earnings per share", h.map(x => x.eps == null ? "—" : nf(x.eps, 2))],
      ["Total assets", h.map(x => m(x.values.total_assets))],
      ["Total equity", h.map(x => m(x.values.total_equity))],
      ["Total debt", h.map(x => m(x.values.total_debt))],
      ["Operating cash flow", h.map(x => m(x.values.operating_cf))],
      ["Free cash flow", h.map(x => m(x.values.free_cash_flow))],
    ];
    body.innerHTML = `<div class="table-scroll"><table class="tbl">
      <thead><tr><th>Figures in ${esc(f.currency)}</th>
        ${h.map(x => `<th>${esc(freq === "annual" ? x.period_end.slice(0, 4) : x.period_end)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map(([l, vals]) =>
        `<tr><td>${esc(l)}</td>${vals.map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}
      </tbody></table></div>
      <p class="muted" style="font-size:12.5px;margin-top:12px">
        A dash means the company does not report that line — not that the value is zero.
        Source: ${esc(f.source)}.</p>
      <div class="chart-box" style="height:250px"><canvas id="fin-chart"></canvas></div>`;

    const rev = h.slice().reverse();
    lineChart("fin-chart", rev.map(x => x.period_end.slice(0, freq === "annual" ? 4 : 10)), [
      {label: "Revenue", data: rev.map(x => x.values.revenue), borderColor: GREEN,
       borderWidth: 2, pointRadius: 3, tension: .1},
      {label: "Net profit", data: rev.map(x => x.values.net_income), borderColor: BLUE,
       borderWidth: 2, pointRadius: 3, tension: .1},
    ], {title: "Revenue and profit over time"});
  } catch (e) {
    body.innerHTML = `<div class="error">${esc(e.message)}</div>`;
  }
}

async function loadDividends(ticker) {
  const body = document.getElementById("div-body");
  try {
    const d = await api(`/api/security/${encodeURIComponent(ticker)}/dividends`);
    if (!d.count) {
      body.innerHTML = `<p class="muted">This company has not paid a cash dividend
        in the period we hold data for.</p>`;
      return;
    }
    const recent = d.dividends.slice(0, 14);
    body.innerHTML = `<div class="table-scroll"><table class="tbl">
      <thead><tr><th style="text-align:left">Ex-dividend date</th><th>Per share</th></tr></thead>
      <tbody>${recent.map(x => `<tr><td style="text-align:left">${esc(x.ex_date)}</td>
        <td>${price(x.amount)}</td></tr>`).join("")}</tbody></table></div>
      <p class="muted" style="font-size:12.5px;margin-top:10px">
        Showing ${count(recent.length)} of ${count(d.count)} recorded payments.</p>`;
  } catch (e) {
    body.innerHTML = `<div class="error">${esc(e.message)}</div>`;
  }
}
