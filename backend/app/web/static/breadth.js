/* EGX Research — what the market did today.

   An index can rise while most shares fall. Egypt's is concentrated enough
   that a good day for two or three large banks carries the whole number, and a
   reader looking only at the level would conclude the market was healthy on a
   day when four companies in five went down.

   So the headline here is not a level, it is participation: how many companies
   traded, and how many of those went up.
*/

function breadthBar(up, down, flat) {
  const total = up + down + flat || 1;
  const w = n => (n / total * 100).toFixed(1) + "%";
  return `<div class="bd-bar" title="${up} up, ${down} down, ${flat} unchanged">
    <div class="bd-up" style="width:${w(up)}"></div>
    <div class="bd-flat" style="width:${w(flat)}"></div>
    <div class="bd-down" style="width:${w(down)}"></div>
  </div>`;
}

function breadthSummary(b) {
  if (!b || !b.available) return "";
  const broad = b.share_advancing_pct >= 60;
  const narrow = b.share_advancing_pct <= 40;

  return `<div class="card" id="breadth-card">
    <div class="card-head"><h2>What the market did on ${esc(b.session)}</h2>
      <p class="sub">Counting only the companies that actually traded.</p></div>

    <div class="stats">
      <div class="stat"><div class="k">Companies traded</div>
        <div class="v">${count(b.traded)}</div>
        <div class="note">of the whole exchange</div></div>
      <div class="stat"><div class="k">Went up</div>
        <div class="v up">${count(b.advancing)}</div>
        <div class="note">${pctPlain(b.share_advancing_pct)} of those that traded</div></div>
      <div class="stat"><div class="k">Went down</div>
        <div class="v down">${count(b.declining)}</div>
        <div class="note">${count(b.unchanged)} barely moved</div></div>
      <div class="stat"><div class="k">Value traded</div>
        <div class="v">${bigMoney(b.total_value_traded)}</div>
        <div class="note">across the exchange</div></div>
    </div>

    ${breadthBar(b.advancing, b.declining, b.unchanged)}

    <p style="font-size:14px;color:var(--ink-2);margin:12px 0 0;line-height:1.6">
      ${broad
        ? `A <strong>broad</strong> day — most companies that traded went up, so the move was not carried by a handful of large names.`
        : narrow
        ? `A <strong>narrow</strong> day — most companies that traded fell. If an index rose anyway, a few large companies did the lifting.`
        : `A <strong>mixed</strong> day, with roughly as many companies rising as falling.`}
    </p>

    <div class="grid-2" style="margin-top:18px">
      <div>
        <h4 style="font-size:13.5px;margin:0 0 8px;color:var(--ink-2)">Biggest risers</h4>
        <div class="table-scroll"><table class="tbl"><tbody>
          ${b.best.map(m => `<tr onclick="go('/stock/${esc(m.ticker)}')">
            <td class="tk">${esc(m.ticker)}</td>
            <td style="text-align:left;max-width:170px;overflow:hidden;text-overflow:ellipsis">${esc(m.name)}</td>
            <td class="up" style="font-weight:600">${pct(m.change_pct)}</td>
          </tr>`).join("")}
        </tbody></table></div>
      </div>
      <div>
        <h4 style="font-size:13.5px;margin:0 0 8px;color:var(--ink-2)">Biggest fallers</h4>
        <div class="table-scroll"><table class="tbl"><tbody>
          ${b.worst.map(m => `<tr onclick="go('/stock/${esc(m.ticker)}')">
            <td class="tk">${esc(m.ticker)}</td>
            <td style="text-align:left;max-width:170px;overflow:hidden;text-overflow:ellipsis">${esc(m.name)}</td>
            <td class="down" style="font-weight:600">${pct(m.change_pct)}</td>
          </tr>`).join("")}
        </tbody></table></div>
      </div>
    </div>

    ${b.sectors.length ? `
    <h4 style="font-size:13.5px;margin:20px 0 8px;color:var(--ink-2)">By sector</h4>
    <p class="muted" style="font-size:12.5px;margin:0 0 8px">
      The middle company in each sector. Sectors with fewer than three companies
      trading are left out — one company is not a sector.</p>
    <div class="table-scroll"><table class="tbl">
      <thead><tr><th style="text-align:left">Sector</th><th>Middle company</th>
        <th>Up</th><th>Down</th><th>Traded</th></tr></thead>
      <tbody>${b.sectors.map(s => `<tr onclick="go('/sector/${esc(sectorSlug(s.sector))}')">
        <td style="text-align:left">${esc(s.sector)}</td>
        <td class="${cls(s.median_pct)}" style="font-weight:600">${pct(s.median_pct)}</td>
        <td class="up">${count(s.up)}</td>
        <td class="down">${count(s.down)}</td>
        <td>${count(s.companies)}</td>
      </tr>`).join("")}</tbody>
    </table></div>` : ""}

    <p class="muted" style="font-size:12.5px;margin-top:12px">${esc(b.note)}</p>
  </div>`;
}

function participationCard(p) {
  if (!p || !p.available) return "";
  const thin = p.latest_pct < p.average_pct - 10;
  return `<div class="card">
    <div class="card-head"><h2>How much of the exchange is trading</h2>
      <p class="sub">The share of listed companies that traded at all, by session.</p></div>
    <div class="stats">
      <div class="stat"><div class="k">Latest session</div>
        <div class="v">${pctPlain(p.latest_pct)}</div></div>
      <div class="stat"><div class="k">Average</div>
        <div class="v">${pctPlain(p.average_pct)}</div>
        <div class="note">over ${count(p.sessions)} sessions</div></div>
    </div>
    <div class="chart-box" style="height:200px"><canvas id="bd-part"></canvas></div>
    <p class="muted" style="font-size:12.5px;margin-top:8px">${esc(p.note)}
      ${thin ? "Participation is currently well below its own average, so more "
             + "of the prices on screen are carried forward than usual." : ""}</p>
  </div>`;
}

async function viewMarketToday(view) {
  const b = await api("/api/breadth");
  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>The market today</h2>
      <p>How many Egyptian companies actually traded, how many rose, and where
         the money went. An index level cannot tell you any of that — it can go
         up on a day when most shares went down.</p>
    </div>
    ${breadthSummary(b.daily)}
    ${participationCard(b.participation)}`;

  const p = b.participation;
  if (p && p.available) {
    lineChart("bd-part", p.points.map(x => x.d), [{
      label: "Share of companies trading",
      data: p.points.map(x => x.share_pct),
      borderColor: GREEN, borderWidth: 2, tension: .15,
      backgroundColor: "rgba(11,107,94,.06)", fill: true,
    }], {money: false, xTicks: 6});
  }
}
