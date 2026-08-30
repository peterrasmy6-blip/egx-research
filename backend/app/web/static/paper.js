/* EGX Research — paper portfolios.

   A portfolio you can keep, and be judged against.

   Every other tool here answers a question once and forgets it. That is the
   safest kind of tool and it teaches almost nothing, because the lesson in
   investing is not what you thought on one afternoon — it is what happened
   afterwards, and whether it was skill or the whole market rising.

   So this records what you chose and when, then does the one thing an
   investor almost never does honestly: compares it against the market and
   against inflation. Both comparisons are unflattering more often than not,
   which is exactly why they are worth making.

   No money is involved and nothing is a recommendation. It is a notebook that
   does arithmetic.

   Where it lives
   --------------
   In this browser, and nowhere else. There is no account and no server, so
   nothing is uploaded, nothing is shared, and clearing site data deletes it.
   The page says so rather than letting anyone assume it is backed up.
*/

const PAPER_KEY = "egx-paper-portfolios";
const PAPER_MAX = 12;

function paperLoad() {
  try {
    const raw = localStorage.getItem(PAPER_KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list : [];
  } catch (e) { return []; }
}

function paperSave(list) {
  try {
    localStorage.setItem(PAPER_KEY, JSON.stringify(list.slice(0, PAPER_MAX)));
    return true;
  } catch (e) {
    // A full or disabled store must not fail silently — the whole point is
    // that the record persists.
    return false;
  }
}

function paperId() {
  return "p" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

/* ---------------- valuation of a saved portfolio ---------------- */

/**
 * What a recorded portfolio is worth now, and what the same money would have
 * done in the market instead.
 *
 * The market comparison is the point. Making 25% means nothing until you know
 * the exchange made 40%.
 */
async function paperValue(pf) {
  const out = {holdings: [], invested: 0, value: 0, missing: []};

  for (const h of pf.holdings) {
    let co;
    try {
      co = await api("/api/security/" + encodeURIComponent(h.ticker));
    } catch (e) {
      out.missing.push(h.ticker);
      continue;
    }
    const now = co.price;
    if (now == null || !h.price || !h.shares) {
      out.missing.push(h.ticker);
      continue;
    }
    const cost = h.shares * h.price;
    const value = h.shares * now;
    out.invested += cost;
    out.value += value;
    out.holdings.push({
      ticker: h.ticker, name: co.name, shares: h.shares,
      buy_price: h.price, price: now, cost, value,
      gain: value - cost,
      gain_pct: cost > 0 ? (value / cost - 1) * 100 : null,
      weight_pct: 0,
      liquidity_band: (co.liquidity || {}).band || null,
    });
  }

  for (const h of out.holdings) {
    h.weight_pct = out.value > 0 ? (h.value / out.value) * 100 : 0;
  }
  out.gain = out.value - out.invested;
  out.gain_pct = out.invested > 0 ? (out.value / out.invested - 1) * 100 : null;

  // The market over the same period, from the platform's own composite.
  try {
    const comp = await api("/api/market/composite");
    const pts = (comp && comp.points) || [];
    const start = pts.find(p => p.d >= pf.started_on);
    const end = pts[pts.length - 1];
    if (start && end && start.v > 0) {
      out.market_pct = (end.v / start.v - 1) * 100;
      out.vs_market_pp = out.gain_pct != null
        ? out.gain_pct - out.market_pct : null;
    }
  } catch (e) { /* the comparison is optional, the portfolio is not */ }

  // Inflation over the same period, so "up 20%" can be read honestly.
  const infl = (STATUS && STATUS.inflation) || {};
  if (infl.available && infl.latest_annual_rate_pct != null) {
    const years = (Date.now() - Date.parse(pf.started_on)) / (365.25 * 864e5);
    if (years > 0.08) {
      out.inflation_pct =
        (Math.pow(1 + infl.latest_annual_rate_pct / 100, years) - 1) * 100;
      out.real_gain_pct = out.gain_pct != null
        ? ((1 + out.gain_pct / 100) / (1 + out.inflation_pct / 100) - 1) * 100
        : null;
      out.years = years;
    }
  }
  return out;
}

/* ---------------- the page ---------------- */

let paperEditing = null;

// Row ids must stay unique for the lifetime of the form. Counting the rows in
// the document would reuse an id after a deletion and hand the new row the
// deleted row's picker.
let paperRowSeq = 0;

async function viewPaper(view) {
  const list = paperLoad();

  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>${esc(t("paper.title", "Paper portfolios"))}</h2>
      <p>${esc(t("paper.lede",
        "Write down what you would have bought, and let the market judge it. No money changes hands and nothing here is a recommendation — it is a notebook that does arithmetic, and it will tell you plainly whether you beat the exchange or were simply carried by it."))}</p>
    </div>

    <div class="callout info">
      <strong>${esc(t("paper.storage.title", "This is stored in your browser only."))}</strong>
      ${esc(t("paper.storage.body",
        "There is no account and no server here, so nothing is uploaded and nothing is shared. Clearing your browser data deletes it, and it will not follow you to another device."))}
    </div>

    <div class="card">
      <div class="card-head"><h2>${esc(t("paper.new", "Record a portfolio"))}</h2>
        <p class="sub">${esc(t("paper.new.sub",
          "Enter what you would buy today, or what you bought on an earlier date."))}</p></div>
      <div id="paper-form"></div>
    </div>

    <div id="paper-list"></div>`;

  renderPaperForm();
  await renderPaperList(list);
}

function renderPaperForm() {
  const box = document.getElementById("paper-form");
  const rows = paperEditing ? paperEditing.holdings : [{}];
  paperRowSeq = 0;
  box.innerHTML = `
    <div class="form-row">
      <div class="field"><label>${esc(t("paper.name", "Name it"))}</label>
        <input id="pp-name" type="text" placeholder="${esc(t("paper.name.ph", "e.g. Dividend picks"))}"
               value="${esc(paperEditing ? paperEditing.name : "")}"></div>
      <div class="field"><label>${esc(t("paper.date", "Bought on"))}</label>
        <input id="pp-date" type="date" value="${esc(paperEditing ? paperEditing.started_on : todayISO())}"></div>
    </div>

    <div id="pp-rows">${rows.map(h => paperRow(h)).join("")}</div>

    <div class="form-row" style="margin-top:10px">
      <div class="field field-btn">
        <button class="btn btn-ghost" onclick="addPaperRow()">${esc(t("paper.addrow", "Add another company"))}</button></div>
      <div class="field field-btn">
        <button class="btn" onclick="savePaper()">${esc(t("paper.save", "Save this portfolio"))}</button></div>
      ${paperEditing ? `<div class="field field-btn">
        <button class="btn btn-ghost" onclick="cancelPaper()">${esc(t("paper.cancel", "Cancel"))}</button></div>` : ""}
    </div>
    <p id="pp-error" class="error hidden"></p>`;

  initPickers();
}

function paperRow(h) {
  const i = paperRowSeq++;
  return `<div class="form-row pp-row" data-i="${i}" data-pick="pp-pick-${i}">
    <div class="field"><label>${esc(t("label.company", "Company"))}</label>
      ${tickerSelect("pp-pick-" + i, h.ticker || null, {needPrices: true})}</div>
    <div class="field"><label>${esc(t("paper.shares", "Shares"))}</label>
      <input class="pp-shares" type="number" min="0" step="any" value="${h.shares != null ? h.shares : ""}"></div>
    <div class="field"><label>${esc(t("paper.buyprice", "Price paid"))}</label>
      <input class="pp-price" type="number" min="0" step="any" value="${h.price != null ? h.price : ""}"
             placeholder="${esc(t("paper.buyprice.ph", "leave blank for today's"))}"></div>
    <div class="field field-btn">
      <button class="btn btn-ghost btn-sm" onclick="removePaperRow(${i})">✕</button></div>
  </div>`;
}

function todayISO() { return new Date().toISOString().slice(0, 10); }

function addPaperRow() {
  const rows = document.getElementById("pp-rows");
  rows.insertAdjacentHTML("beforeend", paperRow({}));
  initPickers();
}

function removePaperRow(i) {
  const row = document.querySelector(`.pp-row[data-i="${i}"]`);
  if (row && document.querySelectorAll(".pp-row").length > 1) row.remove();
}

function cancelPaper() { paperEditing = null; renderPaperForm(); }

async function savePaper() {
  const err = document.getElementById("pp-error");
  const show = m => { err.textContent = m; err.classList.remove("hidden"); };
  err.classList.add("hidden");

  const name = document.getElementById("pp-name").value.trim();
  const date = document.getElementById("pp-date").value;
  if (!name) return show(t("paper.err.name", "Give the portfolio a name."));
  if (!date) return show(t("paper.err.date", "Choose a date."));
  if (date > todayISO())
    return show(t("paper.err.future",
      "That date is in the future. This records what you would have bought, not what you will."));

  const holdings = [];
  for (const row of document.querySelectorAll(".pp-row")) {
    const ticker = pickerValue(row.dataset.pick);
    const shares = parseFloat(row.querySelector(".pp-shares").value);
    const priceRaw = row.querySelector(".pp-price").value;
    if (!ticker) continue;
    if (!(shares > 0))
      return show(t("paper.err.shares", "Enter how many shares of each company."));
    const entry = {ticker, shares};
    const price = parseFloat(priceRaw);
    if (priceRaw !== "" && price > 0) entry.price = price;
    holdings.push(entry);
  }
  if (!holdings.length)
    return show(t("paper.err.empty", "Add at least one company."));

  // Fill in any price left blank from the recorded date, so the portfolio has
  // a real cost basis rather than a guess.
  for (const h of holdings) {
    if (h.price) continue;
    try {
      const co = await api("/api/security/" + encodeURIComponent(h.ticker));
      const idx = (co.prices.d || []).findIndex(d => d >= date);
      h.price = idx >= 0 ? co.prices.c[idx] : co.price;
      if (h.price == null) throw new Error("no price");
    } catch (e) {
      return show(`We have no price for ${h.ticker} on or after ${date}, so it cannot be recorded.`);
    }
  }

  const list = paperLoad();
  if (paperEditing) {
    const at = list.findIndex(p => p.id === paperEditing.id);
    if (at >= 0) list[at] = {...paperEditing, name, started_on: date, holdings};
  } else {
    if (list.length >= PAPER_MAX)
      return show(`You can keep ${PAPER_MAX} portfolios in this browser. Delete one first.`);
    list.unshift({id: paperId(), name, started_on: date, holdings,
                  created_on: todayISO()});
  }

  if (!paperSave(list))
    return show(t("paper.err.store",
      "Your browser would not let this be saved — private browsing or full storage. Nothing was recorded."));

  paperEditing = null;
  renderPaperForm();
  await renderPaperList(paperLoad());
}

function editPaper(id) {
  paperEditing = paperLoad().find(p => p.id === id) || null;
  renderPaperForm();
  window.scrollTo({top: 0, behavior: "smooth"});
}

async function deletePaper(id) {
  paperSave(paperLoad().filter(p => p.id !== id));
  await renderPaperList(paperLoad());
}

async function renderPaperList(list) {
  const box = document.getElementById("paper-list");
  if (!list.length) {
    box.innerHTML = `<div class="card"><p class="muted">
      ${esc(t("paper.empty",
        "Nothing recorded yet. Add a portfolio above and it will be valued against the market every time you come back."))}
      </p></div>`;
    return;
  }
  box.innerHTML = `<div class="spinner">${esc(t("label.loading", "Loading…"))}</div>`;

  const cards = [];
  for (const pf of list) {
    const v = await paperValue(pf);
    cards.push(paperCard(pf, v));
  }
  box.innerHTML = cards.join("");
}

function paperCard(pf, v) {
  const beat = v.vs_market_pp != null && v.vs_market_pp > 0;
  return `<div class="card">
    <div class="card-head">
      <h2>${esc(pf.name)}</h2>
      <p class="sub">${esc(t("paper.since", "Recorded"))} ${esc(pf.started_on)}
        · ${count(v.holdings.length)} ${esc(v.holdings.length === 1
            ? t("paper.holding", "holding") : t("paper.holdings", "holdings"))}</p></div>

    <div class="stats">
      <div class="stat"><div class="k">${esc(t("paper.putin", "Put in"))}</div>
        <div class="v">${egp(v.invested)}</div></div>
      <div class="stat"><div class="k">${esc(t("paper.worthnow", "Worth now"))}</div>
        <div class="v ${cls(v.gain)}">${egp(v.value)}</div>
        <div class="note">${pct(v.gain_pct)}</div></div>
      ${v.market_pct != null ? `<div class="stat">
        <div class="k">${esc(t("paper.market", "The market did"))}</div>
        <div class="v ${cls(v.market_pct)}">${pct(v.market_pct)}</div>
        <div class="note ${cls(v.vs_market_pp)}">${
          v.vs_market_pp != null
            ? (v.vs_market_pp > 0 ? "+" : "") + num(v.vs_market_pp, 1) + "pp vs the market"
            : ""}</div></div>` : ""}
      ${v.real_gain_pct != null ? `<div class="stat">
        <div class="k">${esc(t("paper.real", "After inflation"))}</div>
        <div class="v ${cls(v.real_gain_pct)}">${pct(v.real_gain_pct)}</div>
        <div class="note">over ${num(v.years, 1)} years</div></div>` : ""}
    </div>

    ${v.market_pct != null ? `<div class="callout${beat ? " info" : ""}">
      ${beat
        ? `<strong>${esc(t("paper.beat", "Ahead of the market."))}</strong> Over the same period the exchange as a whole returned ${pct(v.market_pct)}, so this selection added ${num(Math.abs(v.vs_market_pp), 1)} percentage points. Over a short period that is as likely to be luck as skill.`
        : `<strong>${esc(t("paper.behind", "Behind the market."))}</strong> The exchange as a whole returned ${pct(v.market_pct)} over the same period. Owning the whole market instead would have done ${num(Math.abs(v.vs_market_pp), 1)} percentage points better — which is the comparison most investors never make.`}
    </div>` : ""}

    <div class="table-scroll"><table class="tbl">
      <thead><tr><th>${esc(t("label.ticker", "Ticker"))}</th>
        <th style="text-align:left">${esc(t("label.company", "Company"))}</th>
        <th>${esc(t("paper.shares", "Shares"))}</th>
        <th>${esc(t("paper.buyprice", "Paid"))}</th>
        <th>${esc(t("label.price", "Now"))}</th>
        <th>${esc(t("paper.gain", "Gain"))}</th>
        <th>${esc(t("paper.weight", "Share of portfolio"))}</th></tr></thead>
      <tbody>${v.holdings.map(h => `<tr onclick="go('/stock/${esc(h.ticker)}')">
        <td class="tk">${esc(h.ticker)}</td>
        <td style="text-align:left;max-width:190px;overflow:hidden;text-overflow:ellipsis">${esc(h.name)}
          ${liquidityBadge(h.liquidity_band)}</td>
        <td>${shares(h.shares)}</td>
        <td>${price(h.buy_price)}</td>
        <td>${price(h.price)}</td>
        <td class="${cls(h.gain)}" style="font-weight:600">${pct(h.gain_pct)}</td>
        <td>${pctPlain(h.weight_pct)}</td>
      </tr>`).join("")}</tbody>
    </table></div>

    ${v.missing.length ? `<div class="callout">
      <strong>${esc(t("paper.missing", "Left out of the total."))}</strong>
      We have no current price for ${v.missing.map(esc).join(", ")}, so
      ${v.missing.length === 1 ? "it is" : "they are"} excluded rather than
      valued at a guess.</div>` : ""}

    <div class="form-row" style="margin-top:12px">
      <div class="field field-btn">
        <button class="btn btn-ghost btn-sm" onclick="editPaper('${esc(pf.id)}')">${esc(t("paper.edit", "Edit"))}</button></div>
      <div class="field field-btn">
        <button class="btn btn-ghost btn-sm" onclick="deletePaper('${esc(pf.id)}')">${esc(t("paper.delete", "Delete"))}</button></div>
    </div>

    <p class="disclaim">${esc(t("paper.disclaim",
      "A record of a hypothetical portfolio, valued at the last close. It is not advice, not a recommendation, and no money is involved."))}</p>
  </div>`;
}
