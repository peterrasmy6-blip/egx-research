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
/* Navigation.

   The site moved from hash routes ("#/stock/COMI") to real paths
   ("/stock/COMI"). The reason is not tidiness: a search engine treats
   everything after a "#" as the same page, so all 269 company pages shared one
   URL, one title and one description, and none of them could be found.

   Old hash links still work -- they are rewritten to the real path on arrival,
   so anything already shared or bookmarked keeps working. */
function go(path) {
  // Some hosts serve /stock/COMI/ and some /stock/COMI. Treat them as the same
  // place, or every click on the page you are already on pushes a history
  // entry and the back button stops working properly.
  const same = location.pathname.replace(/\/+$/, "") === path.replace(/\/+$/, "");
  if (!same) history.pushState({}, "", path);
  render();
  document.body.classList.remove("nav-open");
  return false;
}

function currentRoute() {
  // A hash route from an older link wins, and is upgraded to a real path so
  // the address bar and any subsequent share carry the canonical URL.
  if (location.hash && location.hash.length > 2) {
    const clean = location.hash.slice(1);
    history.replaceState({}, "", clean);
  }
  const [path, ...rest] = location.pathname.split("/").filter(Boolean);
  return {name: "/" + (path || ""), args: rest.map(decodeURIComponent)};
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
    "/methodology": viewMethodology,
    "/terms": viewTerms,
    "/sector": viewSector,
    "/funds": viewFunds,
    "/data-quality": viewQuality,
    "/today": viewMarketToday,
    "/paper": viewPaper,
    "/weekly": viewWeekly,
  };
  const fn = routes[name] || viewHome;
  Promise.resolve(fn(view, args)).then(initPickers).catch(e => {
    view.innerHTML = `<div class="card"><div class="error">${esc(e.message)}</div></div>`;
  });
}
// Back and forward must re-render, since the page never actually reloads.
window.addEventListener("popstate", render);

/* ---------------- charts ---------------- */
function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}
/* A vertical line following the cursor.

   Chart.js draws none by default, so reading a value off a decade of daily
   prices meant guessing which point the tooltip belonged to. Registered once
   rather than per chart. */
const crosshairPlugin = {
  id: "crosshair",
  afterDatasetsDraw(chart) {
    const active = chart.tooltip && chart.tooltip.getActiveElements
      ? chart.tooltip.getActiveElements() : [];
    if (!active.length) return;
    const x = active[0].element.x;
    const {top, bottom} = chart.chartArea;
    const c = chart.ctx;
    c.save();
    c.beginPath();
    c.moveTo(x, top);
    c.lineTo(x, bottom);
    c.lineWidth = 1;
    c.strokeStyle = "rgba(15,23,35,.28)";
    c.setLineDash([3, 3]);
    c.stroke();
    c.restore();
  },
};
if (typeof Chart !== "undefined") Chart.register(crosshairPlugin);

function lineChart(id, labels, datasets, opts = {}) {
  const ctx = document.getElementById(id);
  if (!ctx) return;
  destroyChart(id);
  const money = opts.money !== false;
  const fmt = v => money ? egp(v) : nf(v, 2);

  charts[id] = new Chart(ctx, {
    type: "line",
    data: {labels, datasets},
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: {mode: "index", intersect: false},
      // Ten years of daily prices is thousands of points; drawing a dot on
      // each of them turns the line into a smear and slows the page down.
      elements: {point: {radius: 0, hoverRadius: 4, hitRadius: 12}},
      plugins: {
        legend: {display: datasets.length > 1, position: "bottom",
                 labels: {boxWidth: 12, font: {size: 12}, usePointStyle: true}},
        title: opts.title ? {display: true, text: opts.title, align: "start",
                             font: {size: 13, weight: "600"}, color: "#4a5568"} : {display: false},
        tooltip: {
          backgroundColor: "rgba(15,23,35,.92)",
          padding: 10, cornerRadius: 6, displayColors: datasets.length > 1,
          titleFont: {size: 12, weight: "600"}, bodyFont: {size: 12.5},
          callbacks: {
            label: c => (c.dataset.label ? c.dataset.label + ": " : "") + fmt(c.parsed.y),
            // On a price chart, the move since the start of the visible window
            // is usually what the reader actually wants.
            afterBody: items => {
              if (!opts.showChange || !items.length) return "";
              const ds = datasets[items[0].datasetIndex];
              const first = (ds.data || []).find(v => v != null);
              const now = items[0].parsed.y;
              if (first == null || !first || now == null) return "";
              const chg = (now / first - 1) * 100;
              return `${chg >= 0 ? "+" : ""}${chg.toFixed(1)}% since ${labels[0]}`;
            },
          },
        },
      },
      scales: {
        x: {ticks: {maxTicksLimit: opts.xTicks || 8, font: {size: 11}},
            grid: {display: false}},
        y: {
          // A logarithmic scale is the honest default for a long Egyptian
          // price history: on a linear axis a decade of 20%-a-year inflation
          // flattens everything before the last two years into a straight
          // line at the bottom of the chart.
          type: opts.logScale ? "logarithmic" : "linear",
          ticks: {font: {size: 11},
                  callback: v => money ? bigNum(v) : nf(v, 0)},
          grid: {color: "#eef1f4"},
        },
      },
      ...(opts.chartOptions || {}),
    },
  });
}

const GREEN = "#0b6b5e", BLUE = "#2b6cb0", AMBER = "#b7791f",
      RED = "#c0392b", PURPLE = "#6b46c1", TEAL = "#0f8a5f";
const SERIES_COLORS = [GREEN, BLUE, AMBER, PURPLE, RED, TEAL];

/* ---------------- reading level ----------------

   Two audiences, one page. Someone who has never bought a share needs fewer
   numbers and more words; someone who has been investing for years finds the
   words in the way. Rather than build two sites, the page carries both and
   hides what the reader has said they do not need.

   Stored per device, never sent anywhere. Beginner is the default because a
   first-time visitor is the one who cannot recover from being confused, while
   an experienced investor will find the switch immediately. */
const LEVELS = ["beginner", "normal", "advanced"];

function readingLevel() {
  try {
    const v = localStorage.getItem("egx-level");
    return LEVELS.includes(v) ? v : "normal";
  } catch (e) { return "normal"; }
}

function setReadingLevel(v) {
  try { localStorage.setItem("egx-level", v); } catch (e) {}
  applyReadingLevel();
  render();
}

function applyReadingLevel() {
  const lvl = readingLevel();
  document.body.dataset.level = lvl;
  document.querySelectorAll("[data-set-level]").forEach(b =>
    b.classList.toggle("on", b.dataset.setLevel === lvl));
}

/** True when the reader has asked for the fuller version. */
const isAdvanced = () => readingLevel() === "advanced";
/** True when the reader has asked for the simpler version. */
const isBeginner = () => readingLevel() === "beginner";

/** A plain-English aside shown only to beginners. */
function forBeginners(text) {
  return `<p class="beginner-note">${text}</p>`;
}

/* ---------------- data export ----------------

   Every table can be taken away. Costs almost nothing to offer and changes
   what the platform is for: a figure you can only look at is a curiosity, a
   figure you can check in your own spreadsheet is research.

   The file is built in the browser and never leaves it. */
function toCSV(rows, columns) {
  const cell = v => {
    if (v == null) return "";
    const s = String(v);
    // A company name containing a comma, a quote or a line break would
    // otherwise shift every following column by one.
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const head = columns.map(c => cell(c.label)).join(",");
  const body = rows.map(r => columns.map(c => cell(
    typeof c.get === "function" ? c.get(r) : r[c.key])).join(","));
  return [head].concat(body).join("\r\n");
}

function downloadCSV(filename, rows, columns) {
  if (!rows || !rows.length) return;
  // A byte-order mark, so Excel opens Arabic company names correctly instead
  // of turning them into mojibake.
  const blob = new Blob(["﻿" + toCSV(rows, columns)],
                        {type: "text/csv;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function csvButton(id, label = "Download CSV") {
  return `<button class="btn btn-ghost btn-sm" id="${id}">${esc(label)}</button>`;
}

/* ---------------- shared components ---------------- */
function qualityBadge(q) {
  const map = {full: ["high", "High"], partial: ["partial", "Partial"],
               price_only: ["low", "Prices only"], none: ["none", "Unavailable"]};
  const [c, label] = map[q] || ["none", "Unknown"];
  return `<span class="badge ${c}">Data: ${label}</span>`;
}

/* How easily a share trades. Shown wherever a company appears in a list,
   because the screener can otherwise hand someone a company they cannot buy
   or, worse, cannot later sell. Only the two thin states are badged -- badging
   every company would turn a warning into wallpaper. */
function liquidityBadge(band) {
  if (band === "Very thin")
    return `<span class="badge liq-thin" title="Barely traded. You may not be able to sell when you want to.">Very thin</span>`;
  if (band === "Thin")
    return `<span class="badge liq-light" title="Lightly traded. A meaningful order may move the price against you.">Thinly traded</span>`;
  return "";
}

function valuationBand(cl) {
  if (!cl) return "";
  const c = cl.includes("cheap") ? "val-under"
          : cl.includes("expensive") ? "val-over"
          : cl.includes("average") ? "val-fair" : "val-none";
  return `<span class="val-band ${c}">${esc(cl)}</span>`;
}

function stockLink(t) { return `/stock/${encodeURIComponent(t)}`; }

/* Must match the slug the exporter writes, or the link 404s for a crawler even
   though the app renders it fine. */
function sectorSlug(name) {
  return String(name || "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

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
  applyLang();
  applyReadingLevel();
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
    `${count(STATUS.companies_confirmed)} EGX companies with market data · ` +
    `${count(STATUS.companies_unconfirmed)} tracked without · ` +
    `${count(STATUS.funds)} funds · ` +
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
