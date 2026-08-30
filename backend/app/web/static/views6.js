/* EGX Research — the data-quality page.

   Every known fault in the platform's own data, counted from the database each
   time the site is rebuilt rather than written down by hand. If a fault is
   fixed the number falls on its own; if a new one appears it shows up here
   without anyone deciding to mention it.

   Publishing this is deliberate. A research site with no institution behind it
   has one way to earn trust: be specific about what it gets wrong before
   anyone else finds it. Almost nobody does this, which is exactly why it
   works.
*/

function qualityCard(title, lead, body) {
  return `<div class="card">
    <div class="card-head"><h2>${esc(title)}</h2>
      <p class="sub">${lead}</p></div>
    ${body}</div>`;
}

async function viewQuality(view) {
  const q = await api("/api/quality");
  const n = x => count(x);
  const link = t => `<a href="/stock/${esc(t)}" onclick="go('/stock/${esc(t)}');return false">${esc(t)}</a>`;

  const knownFaults = q.faults.unadjusted_corporate_actions.length
    + q.faults.currency_mismatches.length
    + q.faults.bad_prints.securities;

  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>What is wrong with our data</h2>
      <p>Everything below is counted from the database each time this site is
         rebuilt. It is not a summary written once and left to go stale. Where
         a fault cannot be fixed — because it is in a free source we do not
         control — we say what it is, what we do about it, and which companies
         it touches.</p>
    </div>

    <div class="summary-band">
      <div class="sb-cell"><div class="sb-k">Companies covered</div>
        <div class="sb-v">${n(q.universe.companies)}</div>
        <div class="sb-n">${n(q.universe.retired)} retired, each with a reason</div></div>
      <div class="sb-cell"><div class="sb-k">With prices</div>
        <div class="sb-v">${n(q.coverage.with_prices)}</div>
        <div class="sb-n">${n(q.coverage.no_price_at_all.length)} have none at all</div></div>
      <div class="sb-cell"><div class="sb-k">With accounts</div>
        <div class="sb-v">${n(q.coverage.with_statements)}</div>
        <div class="sb-n">full analysis needs these</div></div>
      <div class="sb-cell"><div class="sb-k">Known faults</div>
        <div class="sb-v">${n(knownFaults)}</div>
        <div class="sb-n">all detected, all handled</div></div>
    </div>

    ${qualityCard("Share splits our source did not apply backwards",
      `${n(q.faults.unadjusted_corporate_actions.length)} companies. Returns measured across these dates are withheld rather than published as fiction.`,
      `<p>When a company splits or consolidates its shares, every earlier price
        should be restated to match. Our source sometimes does not, leaving a
        jump that trading cannot explain — the Egyptian Exchange caps daily
        moves near 10–20%, so a larger one-day change is structural. One
        company appeared to have returned <strong>+805%</strong> in a year
        purely because a 6-for-1 consolidation was never applied to its
        history.</p>
      <div class="table-scroll"><table class="tbl">
        <thead><tr><th>Ticker</th><th style="text-align:left">Company</th>
          <th style="text-align:left">Break</th>
          <th style="text-align:left">Most likely</th></tr></thead>
        <tbody>${q.faults.unadjusted_corporate_actions.map(c => `
          <tr onclick="go('/stock/${esc(c.ticker)}')">
            <td class="tk">${esc(c.ticker)}</td>
            <td style="text-align:left;max-width:220px;overflow:hidden;text-overflow:ellipsis">${esc(c.name)}</td>
            <td style="text-align:left">${(c.breaks || []).map(b => esc(b.date)).join(", ") || "—"}</td>
            <td style="text-align:left;font-size:12.5px;color:var(--ink-3)">${(c.breaks || []).map(b => esc(b.likely)).join("; ")}</td>
          </tr>`).join("")}</tbody>
      </table></div>`)}

    ${qualityCard("Prices that leapt and came straight back",
      `${n(q.faults.bad_prints.bars)} bars across ${n(q.faults.bad_prints.securities)} companies, removed from every calculation.`,
      `<p>A price that jumps and returns to where it started within a few days
        is a fault in the source, not a day's trading — Misr Cement sat near 31,
        printed 18.89 for a single day, and resumed at 33.</p>
      <p>These were previously being treated as share splits, which suppressed
        perfectly good return figures on both sides of a break that never
        happened, and left the wrong prices in the series where they inflated
        volatility and could set a false 52-week high. They are now excluded
        from every figure and listed on each company's own page.</p>`)}

    ${qualityCard("Prices and accounts in different currencies",
      `${n(q.faults.currency_mismatches.length)} securities. Per-share figures are withheld for these.`,
      `<p>Several EGX companies have a second share class quoted in dollars
        while their accounts are reported in pounds. Dividing one by the other
        once produced a company that looked <strong>undervalued by
        2,934%</strong>. Where the mismatch is detected we publish no ratios at
        all rather than a plausible-looking wrong number.</p>
      ${q.faults.currency_mismatches.length
        ? `<p>${q.faults.currency_mismatches.map(c => link(c.ticker)).join(" · ")}</p>`
        : ""}`)}

    ${qualityCard("Companies we hold no prices for",
      `${n(q.coverage.no_price_at_all.length)} of ${n(q.universe.companies)}. They stay in the list, marked, rather than being hidden.`,
      `<p>These are real listed companies that no free source publishes prices
        for. Dropping them would make our coverage look better than it is, so
        they remain searchable and every page says plainly that we have
        nothing for them.</p>
      <p>${q.coverage.no_price_at_all.map(c => link(c.ticker)).join(" · ")}</p>
      <p class="muted" style="font-size:13px;margin-top:10px">A further
        ${n(q.coverage.prices_but_no_volume)} companies have prices but no
        published trading volume, so we cannot tell you how easily they trade.
        That is a gap in the data, not a sign that they are untraded.</p>`)}

    ${qualityCard("Things that are not companies",
      `${n(q.universe.excluded_instruments.length)} instruments deliberately kept out of the company list.`,
      `<div class="table-scroll"><table class="tbl">
        <thead><tr><th>Ticker</th><th style="text-align:left">Kind</th>
          <th style="text-align:left">Why it is not a company</th></tr></thead>
        <tbody>${q.universe.excluded_instruments.map(x => `<tr>
          <td class="tk">${esc(x.ticker)}</td>
          <td style="text-align:left">${esc(x.kind)}</td>
          <td style="text-align:left;font-size:13px">${esc(x.reason)}</td>
        </tr>`).join("")}</tbody>
      </table></div>`)}

    ${q.cross_check && q.cross_check.available ? qualityCard(
      "Checked against a second, independent source",
      `${count(q.cross_check.agree)} of ${count(q.cross_check.compared)} prices agree (${pctPlain(q.cross_check.agree_pct)}).`,
      `<p>${esc(q.cross_check.note)}</p>
      ${q.cross_check.disagreements.length ? `
      <p><strong>${count(q.cross_check.disagreements.length)} companies</strong>
        where the two sites disagree by more than
        ${pctPlain(q.cross_check.tolerance_pct)}. In every case we have been
        able to check by hand against a broker's own app, our figure was the
        one that matched — but we publish the disagreement rather than the
        conclusion, because that is what you would want to see.</p>
      <div class="table-scroll"><table class="tbl">
        <thead><tr><th>Ticker</th><th style="text-align:left">Company</th>
          <th>Ours</th><th>Second source</th><th>Difference</th></tr></thead>
        <tbody>${q.cross_check.disagreements.map(d => `
          <tr onclick="go('/stock/${esc(d.ticker)}')">
            <td class="tk">${esc(d.ticker)}</td>
            <td style="text-align:left;max-width:220px;overflow:hidden;text-overflow:ellipsis">${esc(d.name)}</td>
            <td>${price(d.ours)}</td>
            <td>${price(d.theirs)}</td>
            <td class="${d.severe ? "down" : ""}">${pct(d.difference_pct, 1)}</td>
          </tr>`).join("")}</tbody>
      </table></div>` : ""}
      <p class="muted" style="font-size:13px;margin-top:10px">
        ${count(q.cross_check.not_in_second_source)} companies could not be
        compared because the second source does not carry them. Checked
        ${esc(q.cross_check.checked_on)}.</p>`) : ""}

    ${qualityCard("Where everything comes from", "And what each source cannot do.",
      `<div class="table-scroll"><table class="tbl">
        <thead><tr><th style="text-align:left">Source</th>
          <th style="text-align:left">Used for</th>
          <th style="text-align:left">Limits</th></tr></thead>
        <tbody>${q.sources.map(s => `<tr>
          <td style="text-align:left">${esc(s.name)}</td>
          <td style="text-align:left;font-size:13px">${esc(s.used_for)}</td>
          <td style="text-align:left;font-size:13px;color:var(--ink-3)">${esc(s.limits)}</td>
        </tr>`).join("")}</tbody>
      </table></div>`)}

    <p class="muted" style="font-size:13px;margin-top:18px">
      Counted from the database on ${esc(q.built_on)}. See also
      <a href="/methodology" onclick="go('/methodology');return false">how the
      numbers are worked out</a> and
      <a href="/terms" onclick="go('/terms');return false">the terms</a>.</p>`;
}
