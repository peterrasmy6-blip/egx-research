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
   sections: ["sec-fund", "sec-risk", "sec-numbers"]},
  {id: "valuation", label: "Valuation",
   sections: ["val-card"]},
  {id: "performance", label: "Performance",
   sections: ["sec-performance", "sec-stress"]},
  {id: "financials", label: "Financials",
   sections: ["sec-financials", "sec-statements"]},
  {id: "dividends", label: "Dividends",
   sections: ["sec-dividends"]},
  {id: "peers", label: "Peers",
   sections: ["sec-peers", "sec-nearest"]},
  {id: "tools", label: "Tools",
   sections: ["sec-tools"]},
];
