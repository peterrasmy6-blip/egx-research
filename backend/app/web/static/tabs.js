/* EGX Research — tabs, and a shared vocabulary for risk colour.

   Tabs
   ----
   The company page had grown to eleven stacked cards. The valuation sat four
   screens below the price, the peer ranking below that, and in testing nobody
   scrolled far enough to find either. Grouping them by the question they
   answer -- what is it worth, how has it done, what does it pay -- puts each
   one screen away instead of four.

   Every panel is written into the document at once and merely hidden, rather
   than built when its tab is clicked. That costs a little markup and buys
   three things: find-in-page still finds text on a tab you are not looking
   at, a crawler that runs no JavaScript still reads all of it, and switching
   tabs cannot fail halfway and leave an empty page.

   Colour
   ------
   One scale, used identically everywhere, so a colour means the same thing on
   every page: green is low risk, amber is middling, red is high. Deliberately
   not the red/green of gains and losses -- green here never means "buy".

   Every coloured thing also carries words. Roughly one man in twelve cannot
   reliably separate these hues, and a risk badge that only works for the
   other eleven is not a risk badge.
*/

/* ---------------- tabs ---------------- */

/**
 * Build a tab strip and its panels.
 *
 * `items` is [{id, label, count, html}]. Panels with no html are dropped
 * rather than rendered empty, so a company with no dividends shows no
 * Dividends tab instead of an empty one.
 */
function tabBlock(items, group) {
  const live = items.filter(t => t.html && t.html.trim());
  if (!live.length) return "";
  const strip = live.map((t, i) => `
    <button class="tab${i === 0 ? " on" : ""}" role="tab"
            id="${group}-t-${t.id}"
            aria-selected="${i === 0 ? "true" : "false"}"
            aria-controls="${group}-p-${t.id}"
            data-group="${group}" data-panel="${t.id}">${esc(t.label)}${
      t.count != null ? `<span class="n">${count(t.count)}</span>` : ""}</button>`).join("");

  const panels = live.map((t, i) => `
    <div class="tabpanel" role="tabpanel" id="${group}-p-${t.id}"
         aria-labelledby="${group}-t-${t.id}"${i === 0 ? "" : " hidden"}>
      ${t.html}
    </div>`).join("");

  return `<div class="tabs" role="tablist">${strip}</div>${panels}`;
}

/** Wire a tab strip up. Called once the markup is in the document. */
function initTabs(group) {
  const tabs = [...document.querySelectorAll(`.tab[data-group="${group}"]`)];
  if (!tabs.length) return;

  function show(id, focus) {
    for (const tab of tabs) {
      const on = tab.dataset.panel === id;
      tab.classList.toggle("on", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
      const panel = document.getElementById(`${group}-p-${tab.dataset.panel}`);
      // `hidden` rather than a class, so a panel is hidden from a screen
      // reader too and not merely painted out of sight.
      if (panel) panel.hidden = !on;
      if (on && focus) tab.focus();
    }
    // Remember the tab across a reload, but per company: landing on someone
    // else's Dividends tab because that is where you were last is worse than
    // simply starting at the top.
    try { sessionStorage.setItem("tab:" + group, id); } catch (e) {}
  }

  for (const tab of tabs) {
    tab.onclick = () => show(tab.dataset.panel, false);
    // Arrow keys move between tabs, which is how a tab strip is expected to
    // behave and the only way to reach the later ones without a mouse.
    tab.onkeydown = e => {
      const i = tabs.indexOf(tab);
      let next = null;
      if (e.key === "ArrowRight") next = tabs[(i + 1) % tabs.length];
      else if (e.key === "ArrowLeft") next = tabs[(i - 1 + tabs.length) % tabs.length];
      else if (e.key === "Home") next = tabs[0];
      else if (e.key === "End") next = tabs[tabs.length - 1];
      if (next) { e.preventDefault(); show(next.dataset.panel, true); }
    };
  }

  let want = null;
  try { want = sessionStorage.getItem("tab:" + group); } catch (e) {}
  if (want && tabs.some(t => t.dataset.panel === want)) show(want, false);
}

/* ---------------- risk colour ---------------- */

/**
 * A badge saying how risky a measured quantity is, in colour and in words.
 *
 * `level` is "low" | "mid" | "high" | null. Null is not an omission: it means
 * we could not measure it, which is different from measuring it as safe, and
 * the badge says so rather than disappearing.
 */
function riskBadge(level, label, title) {
  const cls = {low: "rk-low", mid: "rk-mid", high: "rk-high"}[level] || "rk-none";
  return `<span class="rk ${cls}"${title ? ` title="${esc(title)}"` : ""}>
    <span class="dot"></span>${esc(label)}</span>`;
}

/** Where a value sits between two bounds, drawn as a mark on a scale. */
function riskScale(value, lo, hi, loLabel, hiLabel) {
  if (value == null || !isFinite(value) || hi <= lo) return "";
  const at = Math.max(0, Math.min(100, ((value - lo) / (hi - lo)) * 100));
  return `<div class="scale"><div class="mark" style="left:${at.toFixed(1)}%"></div></div>
    <div class="scale-lbl"><span>${esc(loLabel)}</span><span>${esc(hiLabel)}</span></div>`;
}

/**
 * Volatility, banded.
 *
 * The cuts are where Egyptian shares actually sit rather than a textbook's:
 * on this exchange a 25% annualised swing is an unusually steady company, and
 * calling that "high risk" against a developed-market scale would label the
 * whole market dangerous and tell a reader nothing.
 */
function volatilityLevel(pct) {
  if (pct == null) return [null, "Not measured"];
  if (pct < 30) return ["low", "Steadier than most"];
  if (pct < 50) return ["mid", "Typical for this market"];
  return ["high", "Swings hard"];
}

/** How concentrated a company's price falls have been. */
function drawdownLevel(pct) {
  if (pct == null) return [null, "Not measured"];
  const d = Math.abs(pct);
  if (d < 30) return ["low", "Shallow worst fall"];
  if (d < 55) return ["mid", "Ordinary worst fall"];
  return ["high", "Deep worst fall"];
}

/** Whether the shares can be sold without moving the price. */
function liquidityLevel(band) {
  if (!band) return [null, "Not measured"];
  if (band === "Liquid") return ["low", "Easy to trade"];
  if (band === "Moderate") return ["mid", "Moderately traded"];
  return ["high", "Hard to sell"];
}

/** How much of the balance sheet is borrowed. */
function leverageLevel(de) {
  if (de == null) return [null, "Not measured"];
  if (de < 0.5) return ["low", "Little borrowing"];
  if (de < 1.5) return ["mid", "Moderate borrowing"];
  return ["high", "Heavily borrowed"];
}

/**
 * How much of the picture we actually have.
 *
 * Listed among the risks on purpose. Not knowing something is a risk you are
 * carrying, and it is the one most easily mistaken for good news, because a
 * page with nothing alarming on it looks reassuring whether the silence means
 * "fine" or "unmeasured".
 */
function dataLevel(status) {
  if (status === "full") return ["low", "Full accounts"];
  if (status === "partial") return ["mid", "Partial accounts"];
  if (status === "price_only") return ["high", "Prices only"];
  return [null, "No data"];
}


/* ---------------- risk at a glance ---------------- */

/**
 * The five risks a reader should weigh, each measured, coloured and named.
 *
 * There is deliberately no total. Adding a liquidity score to a leverage
 * score produces one authoritative-looking number whose trade-offs are buried
 * inside it, and a reader who sees "Risk: 7/10" stops asking which risk. A
 * pensioner who cannot afford a bad month and a buyer holding for a decade
 * face the same five facts and should weigh them completely differently.
 */
function riskPanel(d) {
  const risk = d.risk || {};
  const liq = d.liquidity || {};
  const q = d.data_quality || {};
  const ratios = d.valuation_ratios || {};

  const rows = [
    ["How much the price swings", ...volatilityLevel(risk.volatility_pct),
     risk.volatility_pct == null ? "—" : pctPlain(risk.volatility_pct, 1) + " a year",
     "Measured from daily moves over the past year. A bigger number means a "
     + "wider spread of outcomes in both directions, not that it will fall."],
    ["Worst fall it has had", ...drawdownLevel(risk.max_drawdown_pct),
     risk.max_drawdown_pct == null ? "—" : pct(risk.max_drawdown_pct),
     "Peak to trough, on the history we hold. It has happened once; it can "
     + "happen again."],
    ["How easily you could sell", ...liquidityLevel(liq.band),
     liq.band || "—",
     liq.band_note || "Measured from the value traded each day."],
    ["How much it borrows", ...leverageLevel(ratios.debt_to_equity),
     ratios.debt_to_equity == null ? "—" : mult(ratios.debt_to_equity),
     "Debt against shareholders' money. Borrowing raises returns when trade "
     + "is good and losses when it is not."],
    ["How complete our data is", ...dataLevel(q.status),
     q.label || "—",
     q.detail || "What we hold for this company."],
  ];

  return `<div class="card" id="sec-risk">
    <div class="card-head"><h2>${esc(t("co.risk", "Risk at a glance"))}</h2>
      <p class="sub">${esc(t("co.risk.sub",
        "Five separate risks, each measured from this company's own record. "
        + "They are not added together: a total would hide which one you are "
        + "actually taking."))}</p></div>
    <div class="table-scroll"><table class="tbl">
      <tbody>${rows.map(([name, level, word, value, why]) => `<tr>
        <td style="text-align:left;font-weight:500;min-width:150px">${esc(name)}</td>
        <td style="text-align:left;min-width:118px">${riskBadge(level, word, why)}</td>
        <td style="text-align:left;font-weight:600;white-space:nowrap">${value}</td>
        <td style="text-align:left;font-size:12.5px;color:var(--ink-3)">${esc(why)}</td>
      </tr>`).join("")}</tbody>
    </table></div>
    <p class="disclaim">${esc(t("co.risk.note",
      "Colour is a summary of a measurement, not a rating and not advice. "
      + "Every row says in words what its colour says, because colour alone "
      + "is unreadable to a good number of people."))}</p>
  </div>`;
}


/* ---------------- grouping a rendered page into tabs ---------------- */

/**
 * Move already-rendered cards into tab panels.
 *
 * The page is built exactly as before and regrouped afterwards, rather than
 * the template being cut into pieces. That matters for more than tidiness:
 * every chart, table and button keeps the element it was rendered into, so
 * the code that later fills them by id -- the price chart, the dividend
 * table, the financial-history toggles -- goes on working untouched. Moving a
 * node does not disturb what is inside it.
 *
 * `spec` is [{id, label, sections: [elementId, ...]}]. Sections that are not
 * on the page (a fund has no valuation; a company with no dividends has no
 * dividend card) are skipped, and a tab left with nothing is not rendered.
 */
function groupIntoTabs(root, spec, group) {
  const found = spec.map(t => ({
    ...t,
    nodes: t.sections
      .map(id => root.querySelector("#" + id))
      .filter(Boolean),
  })).filter(t => t.nodes.length);

  if (found.length < 2) return false;   // nothing to gain from one tab

  // Mark where the first card sits BEFORE anything moves. Reading the
  // position afterwards asks the document where a node is that is by then
  // inside a panel and no longer a child of the page, which throws.
  const marker = document.createComment("tabs");
  const first = found[0].nodes[0];
  first.parentNode.insertBefore(marker, first);

  const strip = document.createElement("div");
  strip.className = "tabs";
  strip.setAttribute("role", "tablist");

  const panels = document.createElement("div");

  found.forEach((t, i) => {
    const btn = document.createElement("button");
    btn.className = "tab" + (i === 0 ? " on" : "");
    btn.type = "button";
    btn.setAttribute("role", "tab");
    btn.id = `${group}-t-${t.id}`;
    btn.setAttribute("aria-controls", `${group}-p-${t.id}`);
    btn.setAttribute("aria-selected", i === 0 ? "true" : "false");
    btn.dataset.group = group;
    btn.dataset.panel = t.id;
    btn.textContent = t.label;
    strip.appendChild(btn);

    const panel = document.createElement("div");
    panel.className = "tabpanel";
    panel.setAttribute("role", "tabpanel");
    panel.id = `${group}-p-${t.id}`;
    panel.setAttribute("aria-labelledby", btn.id);
    if (i !== 0) panel.hidden = true;
    for (const node of t.nodes) panel.appendChild(node);
    panels.appendChild(panel);
  });

  // Put the strip and its panels exactly where the first card used to be.
  marker.parentNode.insertBefore(strip, marker);
  marker.parentNode.insertBefore(panels, marker);
  marker.parentNode.removeChild(marker);
  initTabs(group);
  return true;
}

/**
 * How a company's page is divided.
 *
 * By the question being asked, not by where the data came from. "What is it
 * worth" and "what has it done" are different questions and a reader arrives
 * with one of them; putting the model estimate on the same surface as the
 * ten-year price history invites the two to be read as one claim.
 */
const COMPANY_TABS = [
  {id: "overview", label: "Overview",
   sections: ["sec-fund", "sec-risk", "sec-range", "sec-numbers"]},
  {id: "valuation", label: "Valuation",
   sections: ["val-card"]},
  {id: "performance", label: "Performance",
   sections: ["sec-performance", "sec-stress"]},
  {id: "financials", label: "Financials",
   sections: ["sec-financials", "sec-statements"]},
  {id: "dividends", label: "Dividends",
   sections: ["sec-dividends"]},
  {id: "peers", label: "Peers",
   sections: ["sec-benchmark", "sec-peers", "sec-nearest"]},
  {id: "tools", label: "Tools",
   sections: ["sec-tools"]},
];


/* ---------------- what would have to be true ---------------- */

/**
 * The model, read backwards.
 *
 * A fair value invites one question and answers a different one. It tells a
 * reader looking at 139 that the thing is worth 90, and the honest reply --
 * that the model rests on assumptions which could be wrong -- leaves nobody
 * any wiser, because the reader cannot see which assumption is carrying the
 * weight.
 *
 * Turning it around answers the question actually being asked. Instead of
 * assuming a rate and producing a value, assume today's price is right and
 * solve for the rate that would justify it. That converts an argument about a
 * model into a question about a business: the market is paying for a 52%
 * return on equity, and this bank earns 27% -- has it ever done better, and
 * what would have to change?
 *
 * The reader is left to answer that. It is the one part of a valuation where
 * someone who knows the company knows more than the model does.
 */
function impliedBlock(im) {
  if (!im) return "";

  if (!im.available) {
    return `<div class="callout">
      <strong>${esc(t("co.implied.title", "What would have to be true?"))}</strong>
      ${esc(im.note || "")}</div>`;
  }

  const tone = {demanding: "rk-high", "in line": "rk-mid",
                modest: "rk-low"}[im.verdict] || "rk-none";
  const word = {demanding: "Demands more than the record",
                "in line": "In line with the record",
                modest: "Asks less than the record",
                unknown: "No record to compare"}[im.verdict] || im.verdict;

  return `<div class="card" style="margin-top:18px;box-shadow:none;
       border:1px solid var(--line-2);background:var(--surface-2)">
    <div class="card-head">
      <h2 style="font-size:16px">${esc(t("co.implied.title",
        "What would have to be true?"))}</h2>
      <p class="sub">${esc(t("co.implied.sub",
        "The same model read backwards: take today's price as correct, and "
        + "solve for the assumption that would justify it."))}</p></div>

    <div class="stats">
      <div class="stat">
        <div class="k">${esc(t("co.implied.needs", "The price implies"))}</div>
        <div class="v">${pctPlain(im.implied_growth_pct, 1)}</div>
        <div class="note">${esc(im.measure)}, sustained for
          ${count(im.years)} years</div></div>
      <div class="stat">
        <div class="k">${esc(t("co.implied.actual", "It has managed"))}</div>
        <div class="v">${im.actual_growth_pct == null ? "—"
          : pctPlain(im.actual_growth_pct, 1)}</div>
        <div class="note">on the history we hold</div></div>
      <div class="stat">
        <div class="k">${esc(t("co.implied.gap", "The gap"))}</div>
        <div class="v"><span class="rk ${tone}"><span class="dot"></span>${esc(word)}</span></div></div>
    </div>

    <p style="font-size:14px;color:var(--ink-2);line-height:1.65;margin:12px 0 0">
      ${esc(im.note)}</p>
    <p class="disclaim">${esc(t("co.implied.note",
      "This is arithmetic on the price, not a forecast and not a view. It "
      + "says what the market appears to be assuming; whether that assumption "
      + "is reasonable is the part only you can judge."))}</p>
  </div>`;
}


/* ---------------- the dividend record ---------------- */

/**
 * What a dividend record says that a yield does not.
 *
 * A yield is last year's payment over today's price, so it rises when a price
 * falls. The highest yields on any exchange belong to the payments the market
 * least believes will be repeated, which means a reader shopping on yield
 * alone is steered toward the dividends most likely to be cut.
 *
 * Consistency, cover and real growth are all measurable from records already
 * held, and all three say more than the headline number.
 */
function dividendRecord(r) {
  if (!r || !r.available) {
    return `<p class="muted">${esc((r && r.reason)
      || "We hold no record of this company paying a dividend.")}</p>`;
  }

  const cov = r.cover || {};
  const covTone = {comfortable: "rk-low", adequate: "rk-low", thin: "rk-mid",
                   uncovered: "rk-high"}[cov.band] || "rk-none";
  const covWord = {comfortable: "Comfortably covered", adequate: "Covered",
                   thin: "Barely covered",
                   uncovered: "Not covered by profit"}[cov.band] || "Not measured";

  const streakTone = r.consecutive_years >= 5 ? "rk-low"
    : r.consecutive_years >= 3 ? "rk-mid" : "rk-none";

  const realTone = r.real_growth_pct == null ? "rk-none"
    : r.real_growth_pct >= 0 ? "rk-low" : "rk-high";

  const bars = (r.annual || []).slice(-10);
  const peak = Math.max(...bars.map(b => b.total), 0) || 1;

  return `
    <div class="stats">
      <div class="stat"><div class="k">Years it has paid</div>
        <div class="v">${count(r.years_paid)}</div>
        <div class="note">since ${esc(String(r.first_paid).slice(0, 4))}</div></div>
      <div class="stat"><div class="k">Unbroken run</div>
        <div class="v"><span class="rk ${streakTone}"><span class="dot"></span>${
          count(r.consecutive_years)} year${r.consecutive_years === 1 ? "" : "s"}</span></div>
        <div class="note">${r.still_paying ? "most recent " + esc(r.last_paid)
          : "last paid " + esc(r.last_paid) + " — nothing since"}</div></div>
      <div class="stat"><div class="k">Covered by profit</div>
        <div class="v"><span class="rk ${covTone}"><span class="dot"></span>${
          cov.available ? mult(cov.times) : "—"}</span></div>
        <div class="note">${esc(covWord)}</div></div>
      <div class="stat"><div class="k">Growth of the payment</div>
        <div class="v">${r.growth_pct == null ? "—" : pctPlain(r.growth_pct, 1)}</div>
        <div class="note">a year over ${count(r.growth_years || 0)} years</div></div>
      ${r.real_growth_pct != null ? `<div class="stat">
        <div class="k">After inflation</div>
        <div class="v"><span class="rk ${realTone}"><span class="dot"></span>${
          pctPlain(r.real_growth_pct, 1)}</span></div>
        <div class="note">what the payment actually buys</div></div>` : ""}
    </div>

    ${cov.available ? `<div class="callout${
      cov.band === "uncovered" ? "" : " info"}">${esc(cov.note)}</div>` : ""}

    ${r.real_note ? `<p style="font-size:14px;color:var(--ink-2);
      line-height:1.65;margin:12px 0 0">${esc(r.real_note)}</p>` : ""}

    ${(r.gaps || []).length ? `<div class="callout">
      <strong>The run has been broken.</strong> No dividend was recorded ${
        r.gaps.map(g => `between ${g.after} and ${g.resumed}`).join(", ")}.
      A company that has stopped once can stop again.</div>` : ""}

    ${bars.length >= 2 ? `<h4 style="font-size:14px;margin:20px 0 8px">
      Paid each year, per share</h4>
    <div class="divbars">
      ${bars.map(b => `<div class="divbar" title="${b.year}: ${egp2(b.total)}">
        <div class="db-fill" style="height:${Math.max(3, b.total / peak * 100)}%"></div>
        <div class="db-yr">${String(b.year).slice(2)}</div>
      </div>`).join("")}
    </div>` : ""}

    <p class="disclaim">A record of what has been paid, not a promise of what
      will be. Cover and consistency are facts; whether this dividend survives
      next year is a judgement about the business that no measurement here
      can make.</p>`;
}

/* ---------------- where the price sits in its own year ---------------- */

/**
 * The 52-week range, with today's price marked on it.
 *
 * The most self-contained measure on the page: it compares a company only
 * with itself, needing no peer group, no sector median and no model. It also
 * carries no verdict, because it does not support one -- shares sit near
 * their low both when they are cheap and when the business is failing.
 */
function pricePosition(pp, price) {
  if (!pp || !pp.available) return "";
  return `<div class="card" id="sec-range">
    <div class="card-head"><h2>${esc(t("co.range", "Where the price sits in its own year"))}</h2>
      <p class="sub">${esc(t("co.range.sub",
        "Today against this company's own highest and lowest points of the past 12 months."))}</p></div>

    <div class="rangebar">
      <div class="rb-track"><div class="rb-mark" style="left:${pp.position_pct}%"></div></div>
      <div class="rb-ends">
        <span>${price_(pp.low)}<em>12-month low</em></span>
        <span style="text-align:end">${price_(pp.high)}<em>12-month high</em></span>
      </div>
    </div>

    <div class="stats" style="margin-top:14px">
      <div class="stat"><div class="k">Position in the range</div>
        <div class="v">${pctPlain(pp.position_pct, 0)}</div>
        <div class="note">${esc(pp.where)}</div></div>
      <div class="stat"><div class="k">Above its low</div>
        <div class="v up">${pp.from_low_pct == null ? "—" : pct(pp.from_low_pct)}</div></div>
      <div class="stat"><div class="k">Below its high</div>
        <div class="v ${pp.from_high_pct < 0 ? "down" : ""}">${
          pp.from_high_pct == null ? "—" : pct(pp.from_high_pct)}</div></div>
    </div>

    <p class="disclaim">${esc(pp.note)}</p>
  </div>`;
}

// `price` is already a function name in this file; a small alias keeps the
// range card readable without shadowing it.
function price_(v) { return price(v); }

/* ---------------- this company against its sector ---------------- */

/**
 * Every measure set beside the middle of its sector.
 *
 * A ratio on its own tells a newcomer almost nothing. "Return on equity 26%"
 * is excellent against Egyptian banks earning 12% and unremarkable against
 * banks earning 30%, and which of those is true is precisely the fact someone
 * new to the exchange does not have. The median supplies it in one line.
 *
 * The comparison is against the sector where the sector is large enough to
 * mean something, and against the whole exchange where it is not -- and the
 * card says which, because "cheaper than other Egyptian banks" and "cheaper
 * than the exchange" are different claims.
 */
function sectorBenchmark(b, d) {
  if (!b || !b.values || !Object.keys(b.values).length) return "";

  const mine = {
    pe: (d.valuation_ratios || {}).pe,
    pb: (d.valuation_ratios || {}).pb,
    roe_pct: (d.quality || {}).roe_pct,
    net_margin_pct: (d.quality || {}).net_margin_pct,
    dividend_yield_pct: (d.valuation_ratios || {}).dividend_yield_pct,
    revenue_growth_pct: (d.quality || {}).revenue_growth_pct,
    debt_to_equity: (d.valuation_ratios || {}).debt_to_equity,
    volatility_pct: (d.risk || {}).volatility_pct,
  };

  const rows = b.fields.filter(f => b.values[f.key] != null
                                    && mine[f.key] != null);
  if (!rows.length) return "";

  const fmt = (k, v) => (k === "pe" || k === "pb" || k === "debt_to_equity")
    ? mult(v) : pctPlain(v, 1);

  return `<div class="card" id="sec-benchmark">
    <div class="card-head">
      <h2>${esc(t("co.bench", "How it compares with"))} ${esc(b.label.toLowerCase())}</h2>
      <p class="sub">${esc(t("co.bench.sub",
        "Each measure beside the middle company of its group, so a ratio "
        + "arrives with something to be judged against."))}
        ${count(b.companies)} ${b.basis === "sector"
          ? "companies in this sector" : "companies on the exchange"}.</p></div>

    <div class="table-scroll"><table class="tbl">
      <thead><tr>
        <th style="text-align:left">Measure</th>
        <th>This company</th>
        <th>${esc(b.basis === "sector" ? "Sector middle" : "Exchange middle")}</th>
        <th style="text-align:left">Difference</th>
      </tr></thead>
      <tbody>${rows.map(f => {
        const a = mine[f.key], m = b.values[f.key];
        const better = f.higher_better ? a > m : a < m;
        const same = Math.abs(a / (m || 1) - 1) < 0.05;
        const tone = same ? "rk-none" : better ? "rk-low" : "rk-mid";
        const word = same ? "about the same"
          : (better ? "better than" : "worse than") + " the middle";
        return `<tr>
          <td style="text-align:left">${esc(f.label)}</td>
          <td style="font-weight:600">${fmt(f.key, a)}</td>
          <td class="muted">${fmt(f.key, m)}</td>
          <td style="text-align:left"><span class="rk ${tone}">
            <span class="dot"></span>${esc(word)}</span></td>
        </tr>`;
      }).join("")}</tbody>
    </table></div>

    <p class="disclaim">${esc(t("co.bench.note",
      "Better and worse here describe the direction each measure is "
      + "conventionally read in, not whether the company is a better "
      + "investment. A low price-to-earnings is cheaper, and cheap is "
      + "sometimes cheap for a reason."))}</p>
  </div>`;
}
