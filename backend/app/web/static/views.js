/* EGX Research — page views. */

/* =======================================================================
   HOME
   ======================================================================= */
function viewHome(view) {
  const tiles = [
    ["🔍", t("tile.research", "Research a company"), t("tile.research.d", "Prices, profits, ratios and financial statements for every listed Egyptian company."), "/markets"],
    ["⏳", t("tile.whatif", "What if I had invested?"), t("tile.whatif.d", "See what a real investment would actually have done — including dividends and inflation."), "/scenario"],
    ["⚖️", t("tile.value", "Fair value"), t("tile.value.d", "Model estimates of what a company might be worth, with the assumptions shown."), "/markets"],
    ["🎛️", t("tile.screener", "Screener"), t("tile.screener.d", "Filter the whole exchange by value, quality, growth and risk."), "/screener"],
    ["📊", t("tile.compare", "Compare companies"), t("tile.compare.d", "Put several companies side by side on the same measures."), "/compare"],
    ["🧪", t("tile.backtest", "Backtest a portfolio"), t("tile.backtest.d", "Test how a mix of shares would have performed, with rebalancing and costs."), "/backtest"],
    ["🔮", t("tile.forecast", "Future scenarios"), t("tile.forecast.d", "Projections and Monte Carlo simulations — ranges, not predictions."), "/forecast"],
    ["🧭", t("tile.plan", "Forecast a portfolio"), t("tile.plan.d", "Build a portfolio today and model how it might behave over the years ahead."), "/plan"],
    ["🎓", t("tile.learn", "Learn investing"), t("tile.learn.d", "Plain-English explanations of every term used on this site."), "/learn"],
  ];

  const top = [...UNIVERSE].filter(s => s.ret_1y != null)
    .sort((a, b) => b.ret_1y - a.ret_1y);
  const gainers = top.slice(0, 5);
  const losers = top.slice(-5).reverse();
  const biggest = [...UNIVERSE].filter(s => s.market_cap)
    .sort((a, b) => b.market_cap - a.market_cap).slice(0, 8);

  const movers = (rows, label) => `
    <div class="card">
      <div class="card-head"><h2>${label}</h2>
        <p class="sub">Total return over the last year. A badge marks a share
          that trades thinly — on those, a large move can be one small order
          rather than news.</p></div>
      <div class="table-scroll"><table class="tbl"><tbody>
        ${rows.map(s => `<tr onclick="go('/stock/${esc(s.ticker)}')">
          <td class="tk">${esc(s.ticker)}</td>
          <td style="text-align:left;color:var(--ink-2);max-width:200px;overflow:hidden;text-overflow:ellipsis">${esc(s.name.slice(0, 34))}
            ${liquidityBadge(s.liquidity_band) || ""}</td>
          <td>${price(s.price)}</td>
          <td class="${cls(s.ret_1y)}" style="font-weight:600">${pct(s.ret_1y)}${
            s.real_ret_1y != null
              ? `<div class="${cls(s.real_ret_1y)}" style="font-weight:500;font-size:11.5px;opacity:.85">${pct(s.real_ret_1y)} real</div>`
              : ""}</td>
        </tr>`).join("")}
      </tbody></table></div>
    </div>`;

  view.innerHTML = `
    <div class="hero">
      <h1>${esc(t("home.hero", "Understand the Egyptian stock market before you invest in it."))}</h1>
      <p class="lede">${esc(t("home.lede", "Free research, valuation and historical analysis covering the whole Egyptian Exchange. Every number is calculated from real market prices and company filings — never estimated, never invented."))}</p>
    </div>

    ${isRTL() ? `<div class="lang-note">${esc(t("lang.names_note", ""))}</div>` : ""}

    <div class="tiles">
      ${tiles.map(([ic, h, p, r]) => `<div class="tile" onclick="go('${r}')">
        <span class="ic">${ic}</span><h3>${esc(h)}</h3><p>${esc(p)}</p></div>`).join("")}
    </div>

    <div class="callout info" style="margin-top:26px">
      <strong>${esc(t("home.philosophy.title", "Research. Understand. Decide."))}</strong>
      ${esc(t("home.philosophy.body", "This site gives you the information and the tools. It deliberately does not tell you what to buy, sell, or how to divide your money — those decisions depend on your own circumstances and are yours to make."))}
    </div>

    <div class="section-head">
      <h2>${esc(t("home.glance", "The exchange at a glance"))}</h2>
      <p>${count(STATUS.companies_confirmed)} companies tracked ·
         ${count(STATUS.equities_with_prices)} with prices ·
         ${count(STATUS.equities_with_statements)} with financial statements ·
         ${count(STATUS.funds)} funds ·
         data to ${esc(STATUS.latest_market_date || "—")}</p>
      <p class="muted" style="font-size:13px;margin-top:6px">
        Coverage is uneven, so it is worth being plain about it: full
        fundamental analysis — ratios, valuation, statement history — needs
        company filings, and free sources publish those for
        ${count(STATUS.equities_with_statements)} of the
        ${count(STATUS.companies_confirmed)} companies. The rest have prices and
        whatever else we could verify, with the gaps labelled on the page rather
        than filled in.${STATUS.equities_thinly_traded ? `
        ${count(STATUS.equities_thinly_traded)} companies are thinly traded and
        badged as such — on this exchange that matters as much as any ratio.` : ""}</p>
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
      <p style="margin-top:16px"><a href="/markets" onclick="go('/markets')">See all companies →</a></p>
    </div>`;
}

/* =======================================================================
   MARKETS — full universe browser
   ======================================================================= */
let mktState = {sector: null, q: "", sort: "market_cap", desc: true,
                kind: "equity", depth: "any"};

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
      <div class="ranges" id="mkt-depth" style="margin-bottom:12px">
        <button class="range on" data-d="any">Any data</button>
        <button class="range" data-d="priced">Has prices</button>
        <button class="range" data-d="full">Full financials</button>
        <button class="range" data-d="tradeable">Readily tradeable</button>
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
  document.querySelectorAll("#mkt-depth .range").forEach(b => b.onclick = () => {
    document.querySelectorAll("#mkt-depth .range").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    mktState.depth = b.dataset.d;
    renderMarkets();
  });
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
  // Coverage is uneven across the exchange, so let people say what they need
  // rather than making them scroll past companies we hold nothing for.
  if (mktState.depth === "priced") rows = rows.filter(s => s.price != null);
  else if (mktState.depth === "full")
    rows = rows.filter(s => s.data_quality === "full");
  else if (mktState.depth === "tradeable")
    rows = rows.filter(s => s.liquidity_band === "Liquid" ||
                            s.liquidity_band === "Moderate");
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

  const csvRows = rows;
  setTimeout(() => {
    const b = document.getElementById("mkt-csv");
    if (b) b.onclick = () => downloadCSV("egx-companies.csv", csvRows, [
      {label: "Ticker", key: "ticker"},
      {label: "Company", key: "name"},
      {label: "Sector", key: "sector"},
      {label: "Price (EGP)", key: "price"},
      {label: "Day change %", key: "day_change_pct"},
      {label: "1-year return %", key: "ret_1y"},
      {label: "1-year real return %", key: "real_ret_1y"},
      {label: "Market value (EGP)", key: "market_cap"},
      {label: "Liquidity", key: "liquidity_band"},
      {label: "Data quality", key: "data_quality"},
    ]);
  }, 0);

  document.getElementById("mkt-body").innerHTML = `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;
                  gap:12px;flex-wrap:wrap;margin:0 0 14px">
        <p class="muted" style="margin:0;font-size:13.5px">
          Showing ${count(rows.length)} of ${count(UNIVERSE.length)} securities.</p>
        ${csvButton("mkt-csv")}
      </div>
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
          <td class="${cls(s.ret_1y)}" style="font-weight:600">${pct(s.ret_1y)}${
            s.real_ret_1y != null
              ? `<div class="${cls(s.real_ret_1y)}" style="font-weight:500;font-size:11.5px;opacity:.85">${pct(s.real_ret_1y)} real</div>`
              : ""}</td>
          <td>${s.asset_type === 'fund' ? (s.fund && s.fund.risk ? esc(s.fund.risk) : '—') : bigMoney(s.market_cap)}</td>
          <td style="text-align:left">${qualityBadge(s.data_quality)}${
            liquidityBadge(s.liquidity_band)}${
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
/* The five things worth knowing before scrolling.

   The company page is a long, evenly-weighted scroll, and a visitor who does
   not already know what to look for has no way in. This puts the answers to
   the questions people actually arrive with at the top: what did it do for an
   owner, what does the model think, can I get out of it, and how much of this
   is guesswork. Each cell links to the section it summarises. */
/* How long a position would take to unwind, in words a person can act on.

   The raw arithmetic is honest but unreadable at the extremes: one barely
   traded company works out at 209,205 days, which reads as a broken number
   rather than as the warning it is. Past a few months the useful answer is not
   a figure at all. */
function exitPhrase(days) {
  if (days == null) return "cannot be estimated";
  if (days < 1) return "takes under a day to sell";
  if (days <= 20) return `takes about ${count(Math.round(days))} trading day${Math.round(days) === 1 ? "" : "s"} to sell`;
  if (days <= 120) return "takes several months to sell";
  return "could not realistically be sold in one go";
}

function summaryBand(d, v, liq, perf, q) {
  const cell = (label, value, note, href, tone) => `
    <div class="sb-cell${tone ? " " + tone : ""}"${href ? ` onclick="document.getElementById('${href}')?.scrollIntoView({behavior:'smooth'})"` : ""}>
      <div class="sb-k">${label}</div>
      <div class="sb-v">${value}</div>
      <div class="sb-n">${note}</div>
    </div>`;

  const real1y = (d.performance_real || {})["1Y"];
  const oneYear = perf["1Y"] == null ? "—"
    : `<span class="${cls(perf["1Y"])}">${pct(perf["1Y"])}</span>`;
  const realNote = real1y != null
    ? `<span class="${cls(real1y)}">${pct(real1y)}</span> after inflation`
    : "nominal";

  const valueCell = v.available
    ? cell(t("co.band.estimate", "Model estimate"), price(v.base),
           `range ${price(v.bear)}–${price(v.bull)} · ${v.confidence}/100 confidence`,
           "val-card")
    : cell(t("co.band.estimate", "Model estimate"), "—", "not enough data to value this company",
           "val-card");

  const liqCell = liq.band
    ? cell(t("co.band.liquidity", "How easily it trades"), esc(liq.band),
           `${egp(100000)} ${exitPhrase(liq.days_to_exit_100k)}`,
           "sec-numbers",
           liq.band === "Very thin" ? "warn" : "")
    : cell(t("co.band.liquidity", "How easily it trades"), "—", "no volume published", "sec-numbers");

  const ql = {full: "High", partial: "Partial", price_only: "Prices only",
              none: "None"}[q.status] || "Unknown";

  return `<div class="summary-band">
    ${cell(t("co.band.return1y", "1-year return"), oneYear, realNote, "sec-performance")}
    ${valueCell}
    ${liqCell}
    ${cell(t("co.band.yield", "Dividend yield"),
           (d.valuation || {}).dividend_yield_pct != null
             ? pctPlain(d.valuation.dividend_yield_pct, 2) : "—",
           "cash paid on today's price", "sec-numbers")}
    ${cell(t("co.band.data", "Data we hold"), ql,
           q.statement_periods ? `${count(q.statement_periods)} years of accounts`
                               : "no financial statements", "sec-numbers")}
  </div>`;
}

/* The three numbers that matter most for this particular business.

   A beginner faces a grid of a dozen ratios with no way to know which are
   load-bearing. Which ones those are depends on the company: a bank's balance
   sheet is its business, so book value matters and margins do not mean what
   they mean elsewhere; a company that pays no dividend cannot be judged on
   yield. */
function whatToLookAt(d, qual, v) {
  const bank = d.sector === "Banks" || d.sector === "Financial Services";
  const pays = v && v.dividend_yield_pct != null && v.dividend_yield_pct > 0;
  const picks = [];

  if (bank) {
    picks.push(["Return on equity",
      "how much profit a bank makes on the money its shareholders put in. For a bank this is the single most telling number."]);
    picks.push(["Price / book",
      "what you pay for each pound of the bank's own money. Around 1 is ordinary; much more means the market expects it to keep earning well."]);
  } else {
    picks.push(["Price / earnings",
      "roughly how many years of today's profit you are paying for. Lower is cheaper, but cheap often means the market expects trouble."]);
    picks.push(["Net margin",
      "how much of each pound of sales the company actually keeps. A thin margin leaves little room when costs rise."]);
  }
  picks.push(pays
    ? ["Dividend yield",
       "the cash paid out each year as a share of today's price. Real money in your hand, but a very high yield often means the market doubts it will last."]
    : ["Revenue growth",
       "whether the business is getting bigger. This company pays no dividend, so growth is where a return would have to come from."]);

  return "<strong>What should I look at first?</strong> "
    + picks.map(([k, why]) => `<br><strong>${esc(k)}</strong> — ${why}`).join("")
    + "<br><br>And before any of them: check how easily the share trades. A "
    + "company you cannot sell is a problem no ratio will warn you about.";
}

async function viewCompany(view, args) {
  const ticker = decodeURIComponent(args[0] || "COMI");
  const d = await api("/api/security/" + encodeURIComponent(ticker));
  const q = d.data_quality, v = d.valuation || {}, qual = d.quality || {},
        perf = d.performance || {}, risk = d.risk || {}, liq = d.liquidity || {};

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
          ${d.sector ? `<a class="tag" href="/sector/${esc(sectorSlug(d.sector))}"
             onclick="go('/sector/${esc(sectorSlug(d.sector))}');return false"
             title="See every ${esc(d.sector.toLowerCase())} company">${esc(d.sector)}</a>` : ""}
          ${qualityBadge(q.status)}
          ${d.listing_status !== "listed" ? `<span class="badge low">${esc(d.listing_status)}</span>` : ""}
        </div>
      </div>
      <div class="px">
        <div class="p">${price(d.price)}</div>
        <div class="d ${cls(d.day_change_pct)}">${pct(d.day_change_pct)}</div>
        <div class="t">as of ${esc(d.price_date || "—")}${
          q.is_stale ? " · not today's price" : ""}</div>
        ${d.price_is_quote && d.last_session && d.last_session !== d.price_date
          ? `<div class="t" style="color:var(--warn)">${
              d.price_source === "stockanalysis-intraday"
                ? "price while the market is open, not a close"
                : "quoted price, not an official close"} · the last full
              trading session we hold is ${esc(d.last_session)}, so the returns
              and charts below end there</div>`
          : ""}
      </div>
    </div>

    <div id="summary-band-slot"></div>

    ${isBeginner() ? forBeginners(
      `<strong>What am I looking at?</strong> This is one company you could own
       a small piece of. The price above is what one share costs today. Below
       you can see what it did for its owners in the past, what it earns, and
       whether the price looks high or low next to other Egyptian companies.
       Nothing here tells you whether to buy it — that depends on things only
       you know.`) : ""}

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
      nothing instead of a fabricated percentage.
      ${(q.price_breaks || []).length ? `<div style="margin-top:8px">
        The break${q.price_breaks.length > 1 ? "s" : ""} we found:
        ${q.price_breaks.map(b =>
          `<strong>${esc(b.date)}</strong> (${pct(b.move_pct)}, ${esc(b.likely)})`
         ).join("; ")}.</div>` : ""}</div>` : ""}

    ${(q.bad_prints || []).length ? `<div class="callout">
      <strong>${count(q.bad_prints.length)} bad price${q.bad_prints.length > 1 ? "s" : ""}
      removed from this company's history.</strong>
      Our source printed a price that leapt and returned to where it started
      within a few days — something trading does not do. Those bars are left out
      of every calculation and out of the chart, because they would otherwise
      inflate the volatility figure and could set a false 52-week high or low.
      Dates removed: ${q.bad_prints.map(b => esc(b.date)).join(", ")}.</div>` : ""}

    ${d.fund ? `<div class="card" id="sec-fund">
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

    ${peerRanks(d.peers)}
    ${nearestPeers(d.nearest_peers, d.sector)}

    ${stressCard(d.devaluation_stress)}

    ${d.asset_type === "fund" ? "" : `<div class="card" id="sec-performance">
      <div class="card-head"><h2>${esc(t("co.performance", "Performance"))}</h2>
        <p class="sub">${esc(t("co.performance.sub", "Total return including dividends."))}</p></div>
      <div class="stats">
        ${["1W","1M","3M","6M","1Y","3Y","5Y"].map(k => {
          const real = (d.performance_real || {})[k];
          return `<div class="stat"><div class="k">${k}</div>
           <div class="v ${cls(perf[k])}">${pct(perf[k])}</div>
           ${real != null ? `<div class="note ${cls(real)}" style="font-weight:600">${pct(real)} real</div>` : ""}</div>`;
        }).join("")}
      </div>
      ${(d.performance_real && d.performance_real["1Y"] != null) ? `
      <p class="muted" style="font-size:13px;margin:10px 0 0">
        <strong>Real</strong> means after Egyptian inflation — what the money
        would actually buy. Over the last five years prices roughly two-and-a-half
        folded, so a large nominal gain can be a modest real one, and a small
        nominal gain can be a real loss.
        ${STATUS.inflation && STATUS.inflation.available
          ? esc(STATUS.inflation.note) : ""}</p>` : ""}
      <div class="ranges" id="co-ranges">
        ${["1y","3y","5y","max"].map(r =>
          `<button class="range${r === "5y" ? " on" : ""}" data-r="${r}">${r.toUpperCase()}</button>`).join("")}
      </div>
      <div class="chart-box"><canvas id="co-chart"></canvas></div>
      <p class="muted" id="chart-note" style="font-size:12px;margin:6px 0 0"></p>
      ${d.high_52w ? `<p class="muted" style="font-size:13px;margin:0">
        52-week range: ${price(d.low_52w)} – ${price(d.high_52w)}</p>` : ""}
    </div>`}

    ${d.asset_type === "fund" ? "" : riskPanel(d)}

    ${d.asset_type === "fund" ? "" : pricePosition(d.price_position, d.price)}

    <div class="card" id="sec-numbers">
      <div class="card-head"><h2>${esc(t("co.keynumbers", "Key numbers"))}</h2>
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
        ${stat("Daily value traded", liq.adtv_90d != null ? bigMoney(liq.adtv_90d) : null,
               "average over 90 sessions")}
      </div>

      ${liq.band ? `<div class="callout${liq.band === "Very thin" ? " warn" : ""}">
        <strong>How easily this trades: ${esc(liq.band).toLowerCase()}.</strong>
        ${esc(liq.band_note)}
        It traded on ${count(liq.days_traded_90d)} of the last
        ${count(liq.sessions_in_window)} sessions, at an average of
        ${bigMoney(liq.adtv_90d)} a day.${liq.days_to_exit_100k != null ? `
        Taking ${Math.round(liq.participation_pct)}% of a normal day's turnover, a
        position of ${egp(100000)}
        <strong>${exitPhrase(liq.days_to_exit_100k)}</strong>.` : ""}
        </div>` : (liq.no_volume_note ? `<div class="callout">
        <strong>Trading volume unavailable.</strong>
        ${esc(liq.no_volume_note)}</div>` : "")}
      ${isBeginner() ? forBeginners(whatToLookAt(d, qual, v)) : ""}
      ${q.missing && q.missing.length ? `<div class="callout">
        <strong>Not every measure applies.</strong> This company does not report
        ${esc(q.missing.join(", ").replace(/_/g, " "))}. That is normal — banks and
        insurers do not report the same lines as manufacturers. We leave these blank
        rather than substitute a number.</div>` : ""}
    </div>

    <div class="card" id="val-card">
      <div class="card-head"><h2>${esc(t("co.valuation", "What might it be worth?"))}</h2>
        <p class="sub">A model estimate from stated assumptions — not a price target.</p></div>
      <div id="val-body"><p class="muted">Calculating…</p></div>
    </div>

    <div class="card" id="sec-financials">
      <div class="card-head"><h2>Financial history</h2>
        <p class="sub">Straight from the annual statements.</p></div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <div class="ranges" id="fin-freq">
          <button class="range on" data-f="annual">Annual</button>
          <button class="range" data-f="quarterly">Quarterly</button>
        </div>
        <div class="ranges" id="fin-view">
          <button class="range on" data-v="levels">Amounts</button>
          <button class="range" data-v="common">% of revenue</button>
        </div>
      </div>
      <div id="fin-body" style="margin-top:14px"><p class="muted">Loading…</p></div>
    </div>

    <div class="card" id="sec-dividends">
      <div class="card-head"><h2>Dividends</h2>
        <p class="sub">Cash paid per share, by ex-dividend date.</p></div>
      ${dividendRecord(d.dividend_record)}
      <h4 style="font-size:14px;margin:22px 0 8px">Every payment we hold</h4>
      <div id="div-body"><p class="muted">Loading…</p></div>
    </div>

    <div class="card" id="sec-tools">
      <div class="card-head"><h2>Try this company in the tools</h2></div>
      <div class="chips">
        <button class="chip" onclick="go('/scenario/${esc(d.ticker)}')">What if I had invested?</button>
        <button class="chip" onclick="go('/forecast/${esc(d.ticker)}')">Future scenarios</button>
        <button class="chip" onclick="go('/compare/${esc(d.ticker)}')">Compare with others</button>
      </div>
    </div>

    <p class="disclaim">${esc(d.disclaimer)}</p>`;

  // Group the cards into tabs. Done after rendering, so every element keeps
  // the node it was drawn into and the code below that fills charts and
  // tables by id needs no knowledge of the tabs at all.
  groupIntoTabs(view, COMPANY_TABS, "co-" + d.ticker);

  document.querySelectorAll("#co-ranges .range").forEach(b => b.onclick = () => {
    document.querySelectorAll("#co-ranges .range").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    loadPriceChart(d.ticker, b.dataset.r);
  });
  let finFreq = "annual";
  document.querySelectorAll("#fin-freq .range").forEach(b => b.onclick = () => {
    document.querySelectorAll("#fin-freq .range").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    finFreq = b.dataset.f;
    loadFinancials(d.ticker, finFreq);
  });
  document.querySelectorAll("#fin-view .range").forEach(b => b.onclick = () => {
    document.querySelectorAll("#fin-view .range").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    finView = b.dataset.v;
    // Only annual statements are common-sized: a single quarter measured
    // against a full year's revenue would be nonsense.
    if (finView === "common" && finFreq !== "annual") {
      finFreq = "annual";
      document.querySelectorAll("#fin-freq .range").forEach(x =>
        x.classList.toggle("on", x.dataset.f === "annual"));
    }
    loadFinancials(d.ticker, finFreq);
  });

  loadPriceChart(d.ticker, "5y");
  loadFinancials(d.ticker, "annual");
  loadDividends(d.ticker);
  loadValuation(d.ticker);
  // The band needs the model's estimate, which is a separate request from the
  // ratio block above. Render it as soon as that resolves rather than blocking
  // the whole page on it.
  renderSummaryBand(d, liq, perf, q);
}

async function loadPriceChart(ticker, range) {
  try {
    const px = await api(`/api/security/${encodeURIComponent(ticker)}/prices?range=${range}`);
    if (!px.points || !px.points.length) {
      document.getElementById("co-chart").parentElement.innerHTML =
        `<p class="muted">No price history available for this period.</p>`;
      return;
    }
    // Long windows go on a log scale, where a 20% move is the same distance
    // whatever the price. On a linear axis a decade of Egyptian inflation
    // squashes everything before the last two years flat against the bottom.
    const longWindow = range === "max" || range === "5y";
    lineChart("co-chart", px.points.map(p => p.d), [{
      label: "Price", data: px.points.map(p => p.c),
      borderColor: GREEN, borderWidth: 2, tension: .12,
      backgroundColor: "rgba(11,107,94,.07)", fill: true,
    }], {logScale: longWindow, showChange: true, xTicks: 7});

    const note = document.getElementById("chart-note");
    if (note) {
      note.textContent = longWindow
        ? "Shown on a ratio scale, so the same percentage move is the same "
        + "distance anywhere on the chart."
        : "";
    }
  } catch (e) {}
}

/* What happened to this share the last time the pound was devalued.

   Every forward-looking tool here says the future is uncertain and shows a
   range, which is true and easy to read past. "This fell 40% in March 2024 and
   had not regained that level six months later" is not.

   Egypt has devalued five times in a decade. This is not an imagined tail risk
   for the sake of a stress test — it is the defining event for Egyptian
   investors, and it is already in the price history. So nothing is modelled:
   the falls below are measured. */
function stressCard(st) {
  if (!st) return "";
  if (!st.available) {
    return `<div class="card"><div class="card-head">
      <h2>${esc(t("co.stress", "Through Egypt's currency devaluations"))}</h2></div>
      <p class="muted">${esc(st.reason)}</p></div>`;
  }

  const worst = st.episodes.reduce((a, b) =>
    b.worst_fall_pct < a.worst_fall_pct ? b : a);

  return `<div class="card" id="sec-stress">
    <div class="card-head"><h2>${esc(t("co.stress", "Through Egypt's currency devaluations"))}</h2>
      <p class="sub">${esc(t("co.stress.sub", "Measured from real prices — not a modelled shock."))}</p></div>

    <div class="stats">
      <div class="stat"><div class="k">Worst fall</div>
        <div class="v down">${pct(st.worst_fall_pct, 1)}</div>
        <div class="note">during ${esc(worst.name)}</div></div>
      <div class="stat"><div class="k">Typical fall</div>
        <div class="v down">${pct(st.average_fall_pct, 1)}</div>
        <div class="note">across ${count(st.episodes_covered)} of ${count(st.episodes_total)} episodes</div></div>
      <div class="stat"><div class="k">Time to recover</div>
        <div class="v">${st.typical_recovery_days != null
          ? count(st.typical_recovery_days) + " days" : "—"}</div>
        <div class="note">${st.typical_recovery_days != null
          ? "back to the peak it fell from"
          : "did not regain its peak inside any window"}</div></div>
    </div>

    <div class="table-scroll" style="margin-top:14px"><table class="tbl">
      <thead><tr><th style="text-align:left">Episode</th><th>Worst fall</th>
        <th>Over the window</th><th style="text-align:left">Back to its peak</th></tr></thead>
      <tbody>${st.episodes.map(e => `<tr>
        <td style="text-align:left"><strong>${esc(e.name)}</strong>
          <div class="muted" style="font-size:12px">${esc(e.from)} to ${esc(e.to)}</div></td>
        <td class="down">${pct(e.worst_fall_pct, 1)}</td>
        <td class="${cls(e.change_over_window_pct)}">${pct(e.change_over_window_pct, 1)}</td>
        <td style="text-align:left;font-size:13px">${e.days_to_recover != null
          ? count(e.days_to_recover) + " days"
          : `<span class="down">not within this window</span>`}</td>
      </tr>`).join("")}</tbody>
    </table></div>

    ${st.never_recovered.length ? `<div class="callout warn">
      <strong>It did not regain its peak.</strong> In
      ${esc(st.never_recovered.join(", ").replace(/^The /, "the "))}, this share
      had not returned to the level it fell from by the end of the window.
      That is separate from where the window ended overall — a share can finish
      higher than it started and still be well below its peak. A fall you can
      wait out and one you cannot look identical on the day it happens.</div>` : ""}

    <p class="muted" style="font-size:12.5px;margin-top:12px">${esc(st.note)}</p>
  </div>`;
}

/* Fair value at a range of required returns.

   The discount rate is the assumption everything else rests on, and the one a
   reader is most entitled to disagree with. Rather than ask anyone to take 26%
   on faith, this shows what the same model says at rates either side of it, so
   they can find their own row.

   Where the table is flat, that is information rather than a fault: it means
   the estimate is coming from what the market pays for comparable companies,
   and a multiple has no discount rate in it. */
function sensitivityTable(sv) {
  if (!sv || !sv.available) return "";

  if (sv.rate_insensitive) {
    return `<div class="callout info" style="margin-top:18px">
      <strong>Changing the discount rate would not move this estimate.</strong>
      ${esc(sv.rate_insensitive_note)}</div>`;
  }

  const rows = sv.rows.map(r => `
    <tr class="${r.is_default ? "sv-default" : ""}">
      <td>${pctPlain(r.cost_of_equity_pct)}${r.is_default
        ? ` <span class="sv-tag">ours</span>` : ""}</td>
      <td>${pctPlain(r.long_run_growth_pct)}</td>
      <td>${price(r.base)}</td>
      <td class="muted" style="font-size:12.5px">${price(r.bear)} – ${price(r.bull)}</td>
      <td>${pct(r.upside_pct, 1)}</td>
      <td style="text-align:left;font-size:12.5px">${esc(r.classification)}</td>
    </tr>`).join("");

  return `<div class="sensitivity">
    <h4 style="margin:22px 0 4px;font-size:15px">If you disagree with our discount rate</h4>
    <p class="muted" style="font-size:13px;margin:0 0 12px">${esc(sv.note)}</p>
    <div class="table-scroll"><table class="tbl">
      <thead><tr>
        <th>Required return</th><th>Long-run growth</th><th>Estimate</th>
        <th>Range</th><th>vs price</th>
        <th style="text-align:left">Reads as</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    ${sv.swing_note ? `<p class="callout" style="margin-top:12px">
      <strong>How much this assumption is carrying.</strong>
      ${esc(sv.swing_note)}</p>` : ""}
  </div>`;
}

/* What the market has actually paid, over the years we hold.

   A model needs assumptions; this needs none. Where the fair-value engine says
   a company screens as expensive, its own trading history can say whether the
   market has ever paid this much for it before -- and the two often disagree,
   which is the useful part. */
function historyBands(h) {
  if (!h) return "";
  if (!h.available) {
    return `<div class="callout" style="margin-top:18px">
      <strong>No history of past valuations for this company.</strong>
      ${esc(h.reason || "")}</div>`;
  }
  const bar = b => {
    const span = b.high - b.low;
    const pos = x => span > 0 ? Math.max(0, Math.min(100, ((x - b.low) / span) * 100)) : 50;
    return `<div class="hb">
      <div class="hb-head">
        <span class="hb-label">${esc(b.label)}</span>
        <span class="hb-now">${b.current != null ? mult(b.current) : "—"} today</span>
      </div>
      <div class="hb-track">
        <div class="hb-median" style="left:${pos(b.median)}%" title="usually around ${b.median}"></div>
        ${b.current != null ? `<div class="hb-cur" style="left:${pos(b.current)}%"></div>` : ""}
      </div>
      <div class="hb-ends"><span>${mult(b.low)}</span><span>${mult(b.high)}</span></div>
    </div>`;
  };
  const notes = Object.values(h.ratios)
    .map(b => historySentence(b)).filter(Boolean);
  return `<div class="history-bands">
    <h4 style="margin:22px 0 4px;font-size:15px">What the market has paid before</h4>
    <p class="muted" style="font-size:13px;margin:0 0 12px">
      Measured, not modelled — no assumptions involved.</p>
    ${Object.values(h.ratios).map(bar).join("")}
    ${notes.map(n => `<p style="font-size:13.5px;margin:10px 0 0">${esc(n)}</p>`).join("")}
    <p class="muted" style="font-size:12.5px;margin-top:10px">${esc(h.note)}</p>
  </div>`;
}

function historySentence(b) {
  if (b.current == null || b.percentile == null) return null;
  const p = b.percentile;
  const where = p <= 20 ? "near the cheapest it has been"
    : p <= 40 ? "below its usual level"
    : p < 60 ? "about where it usually trades"
    : p < 80 ? "above its usual level"
    : "near the most expensive it has been";
  return `At ${b.current}, its ${b.label.toLowerCase()} is ${where} across the `
    + `${b.periods} years we hold — the range is ${b.low} to ${b.high}, `
    + `usually around ${b.median}.`;
}

async function renderSummaryBand(d, liq, perf, q) {
  const slot = document.getElementById("summary-band-slot");
  if (!slot) return;
  let model = {};
  try {
    model = await api(`/api/security/${encodeURIComponent(d.ticker)}/valuation`);
  } catch (e) {
    model = {available: false};
  }
  slot.outerHTML = summaryBand(d, model, liq, perf, q);
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

    // Evidence first, label last. The range and the confidence are what the
    // model actually produced; the words at the end only describe them. Leading
    // with a verdict invites the reader to take the verdict and skip the range,
    // which is the opposite of what this page is for.
    body.innerHTML = `
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
        <div class="stat"><div class="k">${esc(t("co.currentprice", "Current price"))}</div><div class="v">${price(v.price)}</div></div>
        <div class="stat"><div class="k">Model estimate (base)</div><div class="v">${price(v.base)}</div>
          <div class="note">range ${price(v.bear)} – ${price(v.bull)}</div></div>
        <div class="stat"><div class="k">${esc(t("co.difference", "Difference"))}</div>
          <div class="v">${pct(v.upside_pct, 1)}</div>
          <div class="note">vs the model's base case${
            v.upside_vs_market_pct != null
              ? `<br>${pct(v.upside_vs_market_pct, 1)} vs the typical company`
              : ""}</div></div>
        <div class="stat"><div class="k">${esc(t("label.confidence", "Confidence"))}</div><div class="v">${v.confidence}/100</div>
          <div class="note">${v.method_spread_pct != null ? `methods differ by ${pctPlain(v.method_spread_pct)}` : "based on data coverage"}</div></div>
      </div>

      <div class="vsummary">
        ${valuationBand(v.classification)}
        <span>${esc(v.classification_note)}</span>
      </div>

      ${impliedBlock(v.implied)}

      <div class="callout info"><strong>Why these methods?</strong> ${esc(v.rationale)}</div>

      ${v.rate_note ? `<div class="callout"><strong>Why Egyptian shares can look
        expensive.</strong> ${esc(v.rate_note)}</div>` : ""}

      ${sensitivityTable(v.sensitivity)}

      ${historyBands(v.history)}

      <h4 class="adv-only" style="margin:22px 0 10px;font-size:15px">How each method sees it</h4>
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
          <li>Long-run growth: ${pctPlain(v.assumptions.terminal_growth * 100)} a year — not a free choice, but the risk-free rate less ${pctPlain(v.assumptions.terminal_gap * 100)}. A mature company grows a little slower than the economy, and the government bond yield is the standard measure of the economy's nominal growth.</li>
          <li>Cost of debt: ${pctPlain(v.assumptions.cost_of_debt * 100)}; tax rate ${pctPlain(v.assumptions.tax_rate * 100)}.</li>
        </ul>
        <p style="margin-top:8px">Using a European discount rate of 8% instead of
        ${pctPlain(v.assumptions.risk_free_rate * 100)} would roughly double every
        valuation on this site — and every one of them would be wrong.</p>
        ${v.market_median_upside_pct != null ? `
        <p style="margin-top:8px"><strong>How this model is calibrated.</strong>
        Run across the whole exchange, it values the typical Egyptian company
        ${pctPlain(Math.abs(v.market_median_upside_pct))} below its market price.
        That gap belongs to the model, not to any one company: the discount rate
        is built from Egyptian government yields near 20%, and the market plainly
        applies a lower hurdle to shares — whose earnings rise with inflation,
        while a treasury bill's coupon does not. So the label above compares this
        company with the typical company on the same model, rather than treating
        the shared gap as a verdict on each one in turn. The raw figure is shown
        beside it either way.</p>` : ""}
      </details>

      <p class="disclaim">${esc(v.disclaimer)}</p>`;
  } catch (e) {
    body.innerHTML = `<div class="callout">Fair value could not be calculated: ${esc(e.message)}</div>`;
  }
}

/* Statements as a share of revenue.

   Levels answer "how big is it". Shares answer "what shape is it", which is
   usually the more useful question and the only one that survives comparison
   between a company earning billions and one earning millions. The trend
   column says whether each share is widening or being squeezed across the
   years we hold, in percentage points, because that is the comparison a reader
   would make by eye anyway. */
let finView = "levels";

function commonSizedTable(cs, source) {
  const years = cs.periods.map(p => String(p).slice(0, 4));
  const grp = (g, title) => {
    if (!g.lines.length) return "";
    return `<tr class="cs-group"><td colspan="${years.length + 2}">${esc(title)}</td></tr>`
      + g.lines.map(L => {
        const cells = L.is_base
          ? L.levels.map(v => `<td>${bigNum(v)}</td>`)
          : (L.shares || []).map(v => `<td>${v == null ? "—" : pctPlain(v)}</td>`);
        // Percentage points, not percent: this is the change in a share, so
        // pct() would render "+0.8%pp".
        const trend = L.trend
          ? `<td class="${cls(L.trend.change_pp)}">${
              (L.trend.change_pp > 0 ? "+" : "") + nf(L.trend.change_pp, 1)}pp</td>`
          : `<td>—</td>`;
        return `<tr${L.is_base ? ' class="cs-base"' : ""}>
          <td style="text-align:left">${esc(L.label)}${
            L.is_base ? ` <span class="muted" style="font-size:11.5px">(the base)</span>` : ""}</td>
          ${cells.join("")}${L.is_base ? "<td>—</td>" : trend}</tr>`;
      }).join("");
  };

  return `<div class="table-scroll"><table class="tbl cs-table">
      <thead><tr><th style="text-align:left">Share of the base</th>
        ${years.map(y => `<th>${esc(y)}</th>`).join("")}
        <th>Change</th></tr></thead>
      <tbody>
        ${grp(cs.income, "Income statement — share of revenue")}
        ${grp(cs.balance, "Balance sheet — share of total assets")}
        ${grp(cs.cashflow, "Cash flow — share of revenue")}
      </tbody></table></div>
    <p class="muted" style="font-size:12.5px;margin-top:12px">${esc(cs.note)}
      Source: ${esc(source)}.</p>
    ${cs.missing.length ? `<p class="muted" style="font-size:12.5px">
      Not reported by this company: ${esc(cs.missing.join(", ").toLowerCase())}.</p>` : ""}`;
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
    if (finView === "common" && f.common_sized && f.common_sized.available) {
      body.innerHTML = commonSizedTable(f.common_sized, f.source);
      return;
    }

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
