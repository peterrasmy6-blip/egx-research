/* EGX Research — how a company compares with the companies most like it.

   A number on its own means little. "Return on equity 35%" is excellent
   against Egyptian banks and ordinary against a market where several companies
   clear 50%. A rank says which, without the reader holding the whole exchange
   in their head.

   The peer group is chosen per measure and stated on every row, because
   "third-cheapest bank" and "third-cheapest company on the exchange" are very
   different claims and this exchange's sectors are small enough that the
   distinction bites constantly.

   No combined score. Adding a value rank to a quality rank gives one
   authoritative-looking number with every trade-off buried inside it, which is
   a recommendation list with extra steps.
*/

function rankBar(pctile, higherBetter) {
  // Green where the company is on the favourable side, red on the other, and
  // deliberately pale in the middle — most companies are unremarkable on most
  // measures and the colour should not suggest otherwise.
  const good = higherBetter ? pctile >= 65 : pctile <= 35;
  const bad = higherBetter ? pctile <= 35 : pctile >= 65;
  const tone = good ? "pk-good" : bad ? "pk-bad" : "pk-mid";
  return `<div class="pk-track" title="${pctile} out of 100">
    <div class="pk-fill ${tone}" style="width:${Math.max(2, pctile)}%"></div>
  </div>`;
}

function peerValue(o) {
  if (o.unit === "EGP") return bigMoney(o.value);
  if (o.unit === "%") return pctPlain(o.value, 2);
  return mult(o.value);
}

function peerMedian(o) {
  if (o.unit === "EGP") return bigMoney(o.median);
  if (o.unit === "%") return pctPlain(o.median, 2);
  return mult(o.median);
}

function peerRanks(p) {
  if (!p) return "";
  if (!p.available) {
    return `<div class="card"><div class="card-head">
      <h2>${esc(t("co.peers", "How it compares with its peers"))}</h2></div>
      <p class="muted">${esc(p.reason)}</p></div>`;
  }

  const headline = [];
  if (p.stands_out.length)
    headline.push(`It stands out on <strong>${p.stands_out.map(esc).join(", ")}</strong>.`);
  if (p.lags.length)
    headline.push(`It looks weak on <strong>${p.lags.map(esc).join(", ")}</strong>.`);
  if (!headline.length)
    headline.push("Nothing about this company is unusual against its peers on these measures.");

  return `<div class="card" id="sec-peers">
    <div class="card-head">
      <h2>${esc(t("co.peers", "How it compares with its peers"))}</h2>
      <p class="sub">${esc(t("co.peers.sub",
        "Ranked against the companies that report the same measure."))}</p></div>

    <p style="font-size:14.5px;color:var(--ink-2);line-height:1.65;margin:0 0 16px">
      ${headline.join(" ")}</p>

    <div class="table-scroll"><table class="tbl">
      <thead><tr>
        <th style="text-align:left">Measure</th>
        <th>This company</th>
        <th>Peer middle</th>
        <th style="text-align:left">Where it sits</th>
        <th style="text-align:left">Compared with</th>
      </tr></thead>
      <tbody>${p.metrics.map(o => `<tr>
        <td style="text-align:left">${esc(o.label)}</td>
        <td style="font-weight:600">${peerValue(o)}</td>
        <td class="muted">${peerMedian(o)}</td>
        <td style="text-align:left;min-width:130px">
          ${rankBar(o.percentile, o.higher_better)}
          <span class="pk-num">${count(o.percentile)} of 100</span></td>
        <td style="text-align:left;font-size:12.5px;color:var(--ink-3)">
          ${count(o.peers)} ${o.basis === "sector"
            ? esc((p.sector || "").toLowerCase()) + " companies"
            : "companies on the exchange"}</td>
      </tr>`).join("")}</tbody>
    </table></div>

    <p class="muted" style="font-size:12.5px;margin-top:12px">${esc(p.note)}</p>
  </div>`;
}

function nearestPeers(list, sector) {
  if (!list || !list.length) return "";
  return `<div class="card" id="sec-nearest">
    <div class="card-head">
      <h2>${esc(t("co.nearest", "The companies closest to it in size"))}</h2>
      <p class="sub">${esc(t("co.nearest.sub",
        "Same sector, nearest by market value — a company twenty times larger faces different costs and different scrutiny."))}</p></div>
    <div class="table-scroll"><table class="tbl">
      <thead><tr><th>${esc(t("label.ticker", "Ticker"))}</th>
        <th style="text-align:left">${esc(t("label.company", "Company"))}</th>
        <th>${esc(t("label.price", "Price"))}</th>
        <th>P/E</th><th>P/B</th>
        <th>${esc(t("label.year1", "1 year"))}</th>
        <th>${esc(t("label.marketvalue", "Market value"))}</th>
        <th style="text-align:left">${esc(t("co.band.liquidity", "Trades"))}</th>
      </tr></thead>
      <tbody>${list.map(c => `<tr onclick="go('/stock/${esc(c.ticker)}')">
        <td class="tk">${esc(c.ticker)}</td>
        <td style="text-align:left;max-width:200px;overflow:hidden;text-overflow:ellipsis">${esc(c.name)}</td>
        <td>${price(c.price)}</td>
        <td>${mult(c.pe)}</td>
        <td>${mult(c.pb)}</td>
        <td class="${cls(c.ret_1y)}">${pct(c.ret_1y)}</td>
        <td>${bigMoney(c.market_cap)}</td>
        <td style="text-align:left">${liquidityBadge(c.liquidity_band)
          || `<span class="muted" style="font-size:12px">${esc(c.liquidity_band || "—")}</span>`}</td>
      </tr>`).join("")}</tbody>
    </table></div>
  </div>`;
}
