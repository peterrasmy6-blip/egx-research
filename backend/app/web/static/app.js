/* EGX Research — core: routing, formatting, search, shared helpers.
   All figures come from the API. The browser formats; it does not calculate. */

let UNIVERSE = [];
let SECTORS = [];
let STATUS = null;
const charts = {};

/* ---------------- number formatting ----------------
   One rule for the whole site: every number a person reads gets thousands
   separators, and a sensible number of decimals for what it represents.
   Calculations keep full precision; only the display is rounded.        */

/** Thousands separators with a fixed number of decimals. */
const nf = (n, d = 0) => (n == null || !isFinite(n)) ? "—"
  : Number(n).toLocaleString("en-US", {minimumFractionDigits: d,
                                       maximumFractionDigits: d});

/** Money, whole pounds. For totals people read at a glance. */
const egp = n => (n == null || !isFinite(n)) ? "—" : "EGP " + nf(n, 0);

/** Money to the piastre. For share prices and per-share figures. */
const egp2 = n => (n == null || !isFinite(n)) ? "—" : "EGP " + nf(n, 2);

/**
 * A share price, with decimals matched to its size.
 * Egyptian shares run from about 0.30 to 500 EGP, so a flat 2 decimals loses
 * real information at the low end -- 0.79 and 0.7912 are different prices.
 */
function price(n) {
  if (n == null || !isFinite(n)) return "—";
  const a = Math.abs(n);
  const d = a >= 100 ? 2 : a >= 1 ? 2 : a >= 0.1 ? 3 : 4;
  return "EGP " + nf(n, d);
}

/** A plain number with separators, default 2 decimals. */
const num = (n, d = 2) => nf(n, d);

/** Percentage with a sign, for changes and returns. */
const pct = (n, d = 2) => (n == null || !isFinite(n)) ? "—"
  : (n > 0 ? "+" : "") + nf(n, d) + "%";

/** Percentage without a forced sign, for levels like a yield. */
const pctPlain = (n, d = 1) => (n == null || !isFinite(n)) ? "—" : nf(n, d) + "%";

const cls = n => n == null ? "" : (n > 0 ? "up" : n < 0 ? "down" : "");
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

/**
 * Large money in Egyptian scale.
 * A revenue of 281,049,081,719 is unreadable; "EGP 281.05bn" is not. Both keep
 * separators inside the mantissa so 1,234bn still reads correctly.
 */
function bigMoney(n) {
  if (n == null || !isFinite(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e12) return "EGP " + nf(n / 1e12, 2) + "tn";
  if (a >= 1e9)  return "EGP " + nf(n / 1e9, 2) + "bn";
  if (a >= 1e6)  return "EGP " + nf(n / 1e6, 2) + "m";
  if (a >= 1e4)  return "EGP " + nf(n, 0);
  return "EGP " + nf(n, 2);
}

/** Large plain numbers (share counts, volumes, statement lines). */
function bigNum(n) {
  if (n == null || !isFinite(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e12) return nf(n / 1e12, 2) + "tn";
  if (a >= 1e9)  return nf(n / 1e9, 2) + "bn";
  if (a >= 1e6)  return nf(n / 1e6, 2) + "m";
  if (a >= 1e4)  return nf(n, 0);
  return nf(n, a >= 1 ? 0 : 2);
}

/** A count of things: always whole, always separated. */
const count = n => (n == null || !isFinite(n)) ? "—" : nf(Math.round(n), 0);

/** Shares held — fractional amounts matter in a scenario calculation. */
const shares = n => (n == null || !isFinite(n)) ? "—"
  : nf(n, Math.abs(n) >= 1000 ? 0 : 2);

/** A multiple, as in "5.78x". */
const mult = n => (n == null || !isFinite(n)) ? "—" : nf(n, 2) + "x";

/* api() and post() live in api.js — they read pre-built JSON and run
   calculations locally through ENGINE, so the site needs no backend. */

/* ---------------- routing ---------------- */
function go(path) {
  if (location.hash !== "#" + path) location.hash = path;
  else render();
  document.body.classList.remove("nav-open");
  return false;
}

function currentRoute() {
  const h = (location.hash || "#/").slice(1);
  const [path, ...rest] = h.split("/").filter(Boolean);
  return {name: "/" + (path || ""), args: rest};
}

function render() {
  const {name, args} = currentRoute();
  document.querySelectorAll(".mainnav a").forEach(a =>
    a.classList.toggle("on", a.dataset.route === name));
  window.scrollTo(0, 0);
  const view = document.getElementById("view");
  view.innerHTML = '<div class="spinner">Loading…</div>';

  const routes = {
    "/": viewHome,
    "/markets": viewMarkets,
    "/stock": viewCompany,
    "/screener": viewScreener,
    "/compare": viewCompare,
    "/scenario": viewScenario,
    "/backtest": viewBacktest,
    "/forecast": viewForecast,
    "/plan": viewPortfolioForecast,
    "/portfolio": viewPortfolio,
    "/learn": viewLearn,
  };
  const fn = routes[name] || viewHome;
  Promise.resolve(fn(view, args)).then(initPickers).catch(e => {
    view.innerHTML = `<div class="card"><div class="error">${esc(e.message)}</div></div>`;
  });
}
window.addEventListener("hashchange", render);

/* ---------------- charts ---------------- */
function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}
function lineChart(id, labels, datasets, opts = {}) {
  const ctx = document.getElementById(id);
  if (!ctx) return;
  destroyChart(id);
  charts[id] = new Chart(ctx, {
    type: "line",
    data: {labels, datasets},
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: {mode: "index", intersect: false},
      plugins: {
        legend: {display: datasets.length > 1, position: "bottom",
                 labels: {boxWidth: 12, font: {size: 12}, usePointStyle: true}},
        title: opts.title ? {display: true, text: opts.title, align: "start",
                             font: {size: 13, weight: "600"}, color: "#4a5568"} : {display: false},
        tooltip: {callbacks: {label: c => (c.dataset.label ? c.dataset.label + ": " : "") +
                   (opts.money === false ? nf(c.parsed.y, 2) : egp(c.parsed.y))}},
      },
      scales: {
        x: {ticks: {maxTicksLimit: opts.xTicks || 8, font: {size: 11}},
            grid: {display: false}},
        y: {ticks: {font: {size: 11},
                    callback: v => opts.money === false ? nf(v, 0) : bigNum(v)},
            grid: {color: "#eef1f4"}},
      },
      ...(opts.chartOptions || {}),
    },
  });
}

const GREEN = "#0b6b5e", BLUE = "#2b6cb0", AMBER = "#b7791f",
      RED = "#c0392b", PURPLE = "#6b46c1", TEAL = "#0f8a5f";
const SERIES_COLORS = [GREEN, BLUE, AMBER, PURPLE, RED, TEAL];

/* ---------------- shared components ---------------- */
function qualityBadge(q) {
  const map = {full: ["high", "High"], partial: ["partial", "Partial"],
               price_only: ["low", "Prices only"], none: ["none", "Unavailable"]};
  const [c, label] = map[q] || ["none", "Unknown"];
  return `<span class="badge ${c}">Data: ${label}</span>`;
}

function valuationBand(cl) {
  if (!cl) return "";
  const c = cl.includes("under") ? "val-under"
          : cl.includes("over") ? "val-over"
          : cl.includes("fair") ? "val-fair" : "val-none";
  return `<span class="val-band ${c}">${esc(cl)}</span>`;
}

function stockLink(t) { return `#/stock/${encodeURIComponent(t)}`; }

function assumptionsBlock(list, title) {
  if (!list || !list.length) return "";
  return `<details class="assump"><summary>${esc(title || "What this assumes")}</summary>
    <ul>${list.map(a => `<li>${esc(a)}</li>`).join("")}</ul></details>`;
}

/* ---------------- searchable security pickers ----------------
   The site holds 318 stocks and 40 funds. A plain <select> would mean
   scrolling past hundreds of entries to reach CIB, so every selection point
   uses a type-to-search box instead. `tickerSelect` renders the host element;
   `initPickers` wires them up once the surrounding HTML is in the document. */

const PICKERS = {};
const _pendingPickers = [];

/**
 * Render a searchable security field.
 *
 * opts.funds     "only" | "exclude" | "include" (default: exclude)
 * opts.needPrices  require a usable price history (tools that need a series)
 */
function tickerSelect(id, value, opts = {}) {
  _pendingPickers.push({id, value, opts});
  return `<div class="picker-host" id="${id}"></div>`;
}

function pickerItems(opts = {}) {
  const funds = opts.funds || "exclude";
  return (typeof UNIVERSE === "undefined" ? [] : UNIVERSE).filter(s => {
    const isFund = s.asset_type === "fund";
    if (funds === "only" && !isFund) return false;
    if (funds === "exclude" && isFund) return false;
    // Tools that walk a price series cannot use securities without one.
    if (opts.needPrices && (isFund || s.data_quality === "none")) return false;
    return true;
  });
}

/** Create every picker queued by tickerSelect since the last call. */
function initPickers() {
  while (_pendingPickers.length) {
    const {id, value, opts} = _pendingPickers.shift();
    const host = document.getElementById(id);
    if (!host) continue;
    const items = pickerItems(opts);
    const fallback = value && items.some(i => i.ticker === value)
      ? value : (items[0] ? items[0].ticker : null);
    PICKERS[id] = Picker.create(host, {
      items,
      value: fallback,
      placeholder: opts.placeholder ||
        (opts.funds === "only" ? "Type a fund name…"
                               : "Type a company name or ticker…"),
      onSelect: opts.onSelect,
    });
  }
}

/** The ticker currently chosen in a picker. */
function pickerValue(id) {
  return PICKERS[id] ? PICKERS[id].value : null;
}

/* ---------------- search ---------------- */
let searchTimer;
function initSearch() {
  const input = document.getElementById("search");
  const box = document.getElementById("results");
  input.addEventListener("input", e => {
    clearTimeout(searchTimer);
    const q = e.target.value.trim();
    if (!q) { box.classList.add("hidden"); return; }
    searchTimer = setTimeout(async () => {
      try {
        const rows = await api("/api/search?q=" + encodeURIComponent(q));
        box.innerHTML = rows.length
          ? rows.map(r => `<div class="res-item" onclick="pickStock('${esc(r.ticker)}')">
              <span class="res-l"><span class="res-tk">${esc(r.ticker)}</span>
              <span class="res-nm">${esc(r.name)}</span></span>
              <span class="res-r">${r.price != null ? egp2(r.price) : esc(r.sector || "")}</span>
             </div>`).join("")
          : `<div class="res-item"><span class="muted">No company matches “${esc(q)}”.</span></div>`;
        box.classList.remove("hidden");
      } catch (err) {}
    }, 170);
  });
  document.addEventListener("click", e => {
    if (!e.target.closest(".search-box")) box.classList.add("hidden");
  });
}
function pickStock(t) {
  document.getElementById("results").classList.add("hidden");
  document.getElementById("search").value = "";
  go("/stock/" + t);
}

/* ---------------- boot ---------------- */
async function boot() {
  initSearch();
  try {
    [UNIVERSE, SECTORS, STATUS] = await Promise.all([
      api("/api/securities"), api("/api/sectors"), api("/api/status"),
    ]);
  } catch (e) {
    document.getElementById("view").innerHTML =
      `<div class="card"><div class="error">Could not load data: ${esc(e.message)}</div></div>`;
    return;
  }

  document.getElementById("foot-status").textContent =
    `${STATUS.securities_listed} listed securities · ` +
    `${nf(STATUS.price_rows)} daily prices · ${nf(STATUS.statement_facts)} statement figures · ` +
    `market data to ${STATUS.latest_market_date}. Sources: ${STATUS.sources.join("; ")}.`;
  document.getElementById("foot-disclaimer").textContent = STATUS.disclaimer;

  // A static build is a snapshot taken when it was published. Rather than
  // trusting a stored flag, compare the data date against the visitor's clock
  // so the warning stays truthful however long the page sits unpublished.
  const marketDate = STATUS.latest_market_date;
  if (marketDate) {
    const ageDays = Math.floor(
      (Date.now() - Date.parse(marketDate + "T00:00:00Z")) / 86400000);
    STATUS.market_data_age_days = ageDays;
    STATUS.is_stale = ageDays > 5;
    if (STATUS.is_stale) {
      const b = document.getElementById("stale-banner");
      b.textContent =
        `Market data on this page is from ${marketDate} — ${ageDays} days ago. ` +
        `Prices and figures shown reflect that date, not today.`;
      b.classList.remove("hidden");
    }
  }

  render();
}
