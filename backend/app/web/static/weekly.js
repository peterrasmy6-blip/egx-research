/* EGX Research — the week.

   Built for the reader who checks in on a Friday rather than every morning.

   The order of this page is the argument it makes. Breadth comes first — how
   many companies rose and fell, and the median move — because that is what
   actually happened to the market, and it is the number nobody quotes. The
   largest movers come after, and only among shares liquid enough that the move
   means something.

   Nothing on this page explains why anything moved. That is not modesty: for
   most weekly moves on this exchange there is no public explanation, and
   supplying one would be fiction with a chart beside it.
*/

async function viewWeekly(view) {
  view.innerHTML = `<div class="spinner">${esc(t("label.loading", "Loading…"))}</div>`;
  let d;
  try {
    d = await api("/api/digest");
  } catch (e) {
    view.innerHTML = `<div class="card"><p class="muted">${esc(
      t("weekly.unavailable", "This week's summary could not be loaded."))}</p></div>`;
    return;
  }

  if (!d || !d.available) {
    view.innerHTML = `
      <div class="section-head" style="margin-top:28px">
        <h2>${esc(t("weekly.title", "This week on the Egyptian Exchange"))}</h2></div>
      <div class="card"><p class="muted">${esc(
        (d && d.reason) || "There is not enough recent trading data to summarise a week.")}</p></div>`;
    return;
  }

  const breadthTone = d.rose > d.fell ? "up" : d.fell > d.rose ? "down" : "";

  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>${esc(t("weekly.title", "This week on the Egyptian Exchange"))}</h2>
      <p>${esc(t("weekly.lede",
        "What the market did between the two sessions we hold nearest a week apart, and how many companies took part in it."))}
        <strong>${esc(d.week_start)} → ${esc(d.week_end)}</strong></p>
    </div>

    <div class="card">
      <div class="card-head"><h2>${esc(t("weekly.breadth", "How many took part"))}</h2>
        <p class="sub">${esc(t("weekly.breadth.sub",
          "An index can rise while most shares fall. This is the number that says which happened."))}</p></div>
      <div class="stats">
        <div class="stat"><div class="k">${esc(t("weekly.rose", "Rose"))}</div>
          <div class="v up">${count(d.rose)}</div></div>
        <div class="stat"><div class="k">${esc(t("weekly.fell", "Fell"))}</div>
          <div class="v down">${count(d.fell)}</div></div>
        <div class="stat"><div class="k">${esc(t("weekly.flat", "Unchanged"))}</div>
          <div class="v">${count(d.unchanged)}</div></div>
        <div class="stat"><div class="k">${esc(t("weekly.median", "Median move"))}</div>
          <div class="v ${cls(d.median_change_pct)}">${pct(d.median_change_pct)}</div>
          <div class="note">${esc(t("weekly.median.note", "the middle company, not the average"))}</div></div>
      </div>
      <p class="muted" style="font-size:13px;margin-top:8px">
        ${esc(t("weekly.measured", "Measured across"))} ${count(d.companies_measured)}
        ${esc(t("weekly.companies", "companies with a usable price at both ends of the week."))}
        ${breadthTone === "up"
          ? esc(t("weekly.broad", "More companies rose than fell, so the week was broad rather than carried by a few."))
          : breadthTone === "down"
            ? esc(t("weekly.narrow", "More companies fell than rose. If the market still looks up, a small number of large companies carried it."))
            : ""}
      </p>
    </div>

    ${moverTable(t("weekly.gainers", "Largest rises"), d.gainers)}
    ${moverTable(t("weekly.losers", "Largest falls"), d.losers)}

    ${d.sector_moves.length ? `<div class="card">
      <div class="card-head"><h2>${esc(t("weekly.sectors", "By sector"))}</h2>
        <p class="sub">${esc(t("weekly.sectors.sub",
          "The middle company in each sector reporting at least three. A whole sector moving together is a different week from a few companies moving alone."))}</p></div>
      <div class="table-scroll"><table class="tbl">
        <thead><tr><th style="text-align:left">${esc(t("label.sector", "Sector"))}</th>
          <th>${esc(t("weekly.median", "Median move"))}</th>
          <th>${esc(t("label.companies", "Companies"))}</th></tr></thead>
        <tbody>${d.sector_moves.map(s => `<tr onclick="go('/sector/${encodeURIComponent(s.sector)}')">
          <td style="text-align:left">${esc(s.sector)}</td>
          <td class="${cls(s.median_change_pct)}" style="font-weight:600">${pct(s.median_change_pct)}</td>
          <td>${count(s.companies)}</td></tr>`).join("")}</tbody>
      </table></div></div>` : ""}

    ${d.dividends_upcoming.length ? `<div class="card">
      <div class="card-head"><h2>${esc(t("weekly.dividends", "Going ex-dividend soon"))}</h2>
        <p class="sub">${esc(t("weekly.dividends.sub",
          "Buy on or after the ex-date and you do not receive this dividend. The price normally falls by roughly the amount on that day, so it is a date to know, not an opportunity."))}</p></div>
      <div class="table-scroll"><table class="tbl">
        <thead><tr><th>${esc(t("label.ticker", "Ticker"))}</th>
          <th style="text-align:left">${esc(t("label.company", "Company"))}</th>
          <th>${esc(t("weekly.exdate", "Ex-date"))}</th>
          <th>${esc(t("weekly.pershare", "Per share"))}</th></tr></thead>
        <tbody>${d.dividends_upcoming.map(x => `<tr onclick="go('/stock/${esc(x.ticker)}')">
          <td class="tk">${esc(x.ticker)}</td>
          <td style="text-align:left">${esc(x.name)}</td>
          <td>${esc(x.ex_date)}</td>
          <td>${price(x.amount_per_share)}</td></tr>`).join("")}</tbody>
      </table></div></div>` : ""}

    <div class="callout info">
      <strong>${esc(t("weekly.rss.title", "There is no mailing list."))}</strong>
      ${esc(t("weekly.rss.body",
        "Sending email would mean an account, a service and somewhere to keep your address — none of which this project has. This page is rebuilt whenever the data is, and you can follow it by RSS instead, which asks nothing of you:"))}
      <a href="/feed.xml">/feed.xml</a>
    </div>

    <p class="disclaim">${esc(d.note)}</p>`;
}

function moverTable(title, rows) {
  if (!rows || !rows.length) return "";
  return `<div class="card">
    <div class="card-head"><h2>${esc(title)}</h2>
      <p class="sub">${esc(t("weekly.movers.sub",
        "Only shares that trade enough for the move to mean something. On a thin counter one small order moves the close further than any news would."))}</p></div>
    <div class="table-scroll"><table class="tbl">
      <thead><tr><th>${esc(t("label.ticker", "Ticker"))}</th>
        <th style="text-align:left">${esc(t("label.company", "Company"))}</th>
        <th style="text-align:left">${esc(t("label.sector", "Sector"))}</th>
        <th>${esc(t("weekly.change", "Week"))}</th>
        <th>${esc(t("label.price", "Price"))}</th>
        <th>${esc(t("weekly.adtv", "Traded daily"))}</th></tr></thead>
      <tbody>${rows.map(c => `<tr onclick="go('/stock/${esc(c.ticker)}')">
        <td class="tk">${esc(c.ticker)}</td>
        <td style="text-align:left;max-width:200px;overflow:hidden;text-overflow:ellipsis">${esc(c.name)}</td>
        <td style="text-align:left;font-size:12.5px;color:var(--ink-3)">${esc(c.sector || "—")}</td>
        <td class="${cls(c.change_pct)}" style="font-weight:600">${pct(c.change_pct)}</td>
        <td>${price(c.price)}</td>
        <td>${bigMoney(c.adtv_90d)}</td>
      </tr>`).join("")}</tbody>
    </table></div></div>`;
}
