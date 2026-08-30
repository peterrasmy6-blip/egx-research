/* EGX Research — the pages a sceptical reader looks for first.

   Methodology, terms and data sources. These exist because a research platform
   with no institution behind it earns trust one way only: by showing its
   working and being specific about what it cannot do. Every claim on these
   pages is drawn from what the engine actually does, so they stay true as the
   engine changes.
*/

function methodBlock(title, body) {
  return `<div class="card">
    <div class="card-head"><h2>${esc(title)}</h2></div>
    ${body}
  </div>`;
}

async function viewMethodology(view) {
  const ref = await api("/api/reference");
  const v = (ref && ref.valuation_defaults) || {};
  const infl = (STATUS && STATUS.inflation) || {};
  const pc = x => (x == null ? "—" : pctPlain(x * 100));

  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>How this site works out its numbers</h2>
      <p>Every figure here is calculated from raw market prices and company
         filings that we store ourselves. Nothing is copied from another
         site's pre-computed field, and nothing is estimated to fill a gap.
         Where we cannot work something out honestly, the page says so and
         shows a dash.</p>
    </div>

    ${methodBlock("Where the data comes from", `
      <div class="table-scroll"><table class="tbl"><thead><tr>
        <th style="text-align:left">Source</th>
        <th style="text-align:left">What we take from it</th>
        <th style="text-align:left">Known limits</th>
      </tr></thead><tbody>
        <tr><td style="text-align:left">Yahoo Finance</td>
            <td style="text-align:left">Daily prices, dividends, annual financial statements</td>
            <td style="text-align:left">About ten years of history. Statements exist for
              ${count(STATUS.equities_with_statements)} of
              ${count(STATUS.companies_confirmed)} companies. Some corporate
              actions arrive unadjusted, which we detect and handle.</td></tr>
        <tr><td style="text-align:left">stockanalysis.com</td>
            <td style="text-align:left">The roster of EGX ticker codes</td>
            <td style="text-align:left">Disagrees with our second roster; both are filtered
              against a broker's live instrument list.</td></tr>
        <tr><td style="text-align:left">african-markets.com</td>
            <td style="text-align:left">A second, independent roster</td>
            <td style="text-align:left">Carries tickers renamed or delisted years ago.</td></tr>
        <tr><td style="text-align:left">egxbot.com</td>
            <td style="text-align:left">Egyptian fund names and current NAV</td>
            <td style="text-align:left">Publishes 40 funds and no NAV history at all, so
              funds cannot be charted or backtested.</td></tr>
        <tr><td style="text-align:left">World Bank</td>
            <td style="text-align:left">Egyptian consumer price index, for real returns</td>
            <td style="text-align:left">Annual, ending ${esc(String(infl.last_year || "—"))}.
              Values in between are interpolated.</td></tr>
      </tbody></table></div>
      <p class="muted" style="font-size:13.5px;margin-top:12px">
        All of these are free and publicly accessible. This project pays for no
        data, and it does not attempt to get past any site's bot protection —
        which is why the exchange's own pages are not among the sources.</p>`)}

    ${methodBlock("Which companies are included", `
      <p>${count(STATUS.companies_confirmed)} ordinary listed shares. The number
        is smaller than the raw count of things that trade on the exchange, on
        purpose.</p>
      <p>Rights issues, the EGX30 ETF, certificates over other holdings, and
        second share classes of a company already listed are <strong>not</strong>
        counted as companies. A rights issue is a temporary right to subscribe,
        not a business — it has no revenue, no earnings and no balance sheet, and
        treating it as a company would put it on the screener next to real ones.
        A dollar-quoted second class would count the same business twice.</p>
      <p>${count(STATUS.companies_retired)} tickers found in the raw source
        rosters were retired: renamed years ago, no longer on the exchange, or
        never a company at all. None were deleted — each keeps its records and
        the reason it was retired.</p>`)}

    ${methodBlock("Returns, and why we show them twice", `
      <p>Returns are <strong>total returns</strong>: the change in price plus the
        dividends paid, which is what an owner actually received.</p>
      <p>Every return over a year or more is shown twice — once as the number
        the market produced, and once in constant purchasing power. In a country
        where prices have risen the way Egypt's have, the two tell very
        different stories, and only the second answers "am I better off?".
        ${infl.available ? esc(infl.note) : ""}</p>
      <p>Real figures are only shown for periods of a year or more. The price
        index is annual, so a "real" three-month return would be interpolation
        presented as measurement.</p>`)}

    ${methodBlock("How easily a share trades", `
      <p>We measure the average value in pounds changing hands each day over the
        last ${count(90)} sessions, and how many of those sessions the share
        traded at all. Value rather than share count, because a million shares
        at ${egp2(0.4)} and a thousand at ${egp2(400)} are the same trade.</p>
      <p>This matters more on the EGX than almost any ratio. A share can look
        cheap and profitable and still be impossible to sell in any size. Where
        our source publishes prices but no volume, we say so rather than
        guessing — reporting "barely traded" for a company we simply have no
        volume data on would be worse than saying nothing.</p>`)}

    ${methodBlock("Fair value", `
      <p>There is no single fair value, so we never print one. Each company gets
        a range from several methods, chosen to suit the business: banks on book
        equity and the returns they earn on it, property companies on assets,
        operating companies on cash flow and multiples. A cash-flow model is
        never forced onto a bank, where borrowing is raw material rather than
        financing.</p>
      <div class="stats">
        <div class="stat"><div class="k">Risk-free rate</div><div class="v">${pc(v.risk_free_rate)}</div>
          <div class="note">long-dated Egyptian government yield</div></div>
        <div class="stat"><div class="k">Equity risk premium</div><div class="v">${pc(v.equity_risk_premium)}</div>
          <div class="note">demanded above government paper</div></div>
        <div class="stat"><div class="k">Long-run growth</div><div class="v">${pc(v.risk_free_rate - v.terminal_gap)}</div>
          <div class="note">the risk-free rate less ${pc(v.terminal_gap)}</div></div>
        <div class="stat"><div class="k">Corporate tax</div><div class="v">${pc(v.tax_rate)}</div>
          <div class="note">Egyptian rate</div></div>
      </div>
      <p style="margin-top:14px"><strong>The most important thing to understand
        about these numbers.</strong> Run across the whole exchange, this model
        values the typical Egyptian company below its market price. That gap
        belongs to the model, not to any one company: the discount rate is built
        from government yields near 20%, and the market plainly applies a lower
        hurdle to shares — whose earnings rise with inflation, while a treasury
        bill's coupon does not.</p>
      <p>So each company is described by how it compares with the typical company
        on the same model, not by the raw gap. If we reported the raw gap as a
        verdict we would be telling you that most of the exchange is overvalued,
        which is a claim this model cannot support.</p>
      <p>The label is never a recommendation, and the model's estimate of upside
        is deliberately not something you can sort the screener by. A ranked
        list of "most underpriced" is a recommendation list however it is
        captioned.</p>`)}

    ${methodBlock("Forecasts", `
      <p>Every forward-looking figure on this site is a model of what stated
        assumptions imply, not a prediction. Expected returns are built from
        what each company reports — the dividend it pays, how fast its earnings
        have grown, how its valuation compares with its sector — then pulled
        toward a market-wide expectation so recent form is not projected
        forever. Risk uses each holding's measured volatility and the real
        correlations between them.</p>
      <p><strong>Known weakness, stated plainly.</strong> The simulation treats
        each month as independent. Real markets have runs of bad months, and
        Egypt has had several sharp currency devaluations in a decade, which a
        model like this cannot produce. The true chance of a poor outcome is
        therefore somewhat higher than the figures suggest.</p>`)}

    ${methodBlock("What we refuse to do", `
      <ul>
        <li>Fill a gap with an estimate. A missing figure shows a dash, and the
          page explains why it is missing.</li>
        <li>Publish a return measured across a share split our source failed to
          apply backwards. One company appeared to have returned +805% for
          exactly that reason; such returns are withheld, not approximated.</li>
        <li>Publish per-share figures where the price and the accounts are in
          different currencies. That fault once produced a company "undervalued
          by 2,934%".</li>
        <li>Treat a price that leaps and returns within days as a real session.
          Those bars are excluded from every calculation and listed on the
          company's page.</li>
        <li>Tell you what to buy or sell, or rank companies by attractiveness.</li>
      </ul>`)}

    ${methodBlock("How to check any of this", `
      <p>The figures are rebuilt from scratch on every update and checked before
        anything is published. If a check fails, nothing is published and the
        previous version of the site stays online.</p>
      <p>Each company page carries the date of its prices, the date of its last
        financial statements, the source of each, and a data-quality label. If a
        number here disagrees with your broker, those dates are usually the
        reason.</p>`)}

    <p class="muted" style="font-size:13px;margin-top:20px">
      Built ${esc(STATUS.built_on || "—")} · market data to
      ${esc(STATUS.latest_market_date || "—")}</p>`;
}

async function viewTerms(view) {
  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>Terms of use and disclaimer</h2>
      <p>Short, and written to be read rather than to be defensible.</p>
    </div>

    ${methodBlock("What this site is", `
      <p>A free research and financial education tool for the Egyptian Exchange.
        It publishes market data, calculated figures, historical analysis and
        model-based scenarios, together with explanations of what they mean.</p>`)}

    ${methodBlock("What this site is not", `
      <p><strong>It is not investment advice.</strong> Nothing here is a
        recommendation to buy, sell or hold any security, and nothing here takes
        account of your circumstances, your goals, your tax position or how much
        risk you can afford to take. Two people looking at the same page should
        reasonably reach different decisions.</p>
      <p>The operator of this site is not licensed by the Financial Regulatory
        Authority or any other regulator, does not manage money, does not
        receive any fee or commission, and has no relationship with any company
        or fund covered here.</p>
      <p>No part of this site is personalised. It never asks who you are and
        never tailors what it shows to you.</p>`)}

    ${methodBlock("The data may be wrong", `
      <p>The information comes from free public sources. It can be delayed,
        incomplete or simply incorrect, and we have found and documented real
        errors in it. We check for the faults we know how to detect and label
        what we cannot verify, but no amount of checking makes third-party data
        reliable.</p>
      <p>Prices are end-of-day, not live. Do not trade on a figure from this site
        without checking it against your broker.</p>`)}

    ${methodBlock("Models are not forecasts", `
      <p>Fair-value estimates and future scenarios are arithmetic on stated
        assumptions. Different assumptions give different answers, the
        assumptions can be wrong, and past performance does not indicate future
        results. A projection on this site is a description of what a model
        implies — never a statement about what will happen.</p>`)}

    ${methodBlock("Your decisions are yours", `
      <p>You are responsible for your own investment decisions and for any
        outcome that follows from them. If you need advice for your particular
        situation, speak to someone licensed to give it.</p>
      <p>To the extent permitted by law, the operator accepts no liability for
        any loss arising from use of this site or reliance on anything published
        here.</p>`)}

    ${methodBlock("Privacy", `
      <p>This site has no accounts and no login. It does not ask for your name,
        your email address or any other personal information, sets no tracking
        cookies, and stores nothing about you. Anything you build here — a
        portfolio, a scenario — is worked out in your own browser and never
        sent anywhere.</p>`)}

    ${methodBlock("Sources and copyright", `
      <p>Data is read from publicly accessible pages and public APIs, and each
        source is named on the <a href="/methodology" onclick="go('/methodology')">methodology
        page</a>. Figures are recalculated from that raw data rather than
        redistributed. If you own one of these sources and object to its use
        here, it will be removed on request.</p>`)}

    <p class="muted" style="font-size:13px;margin-top:20px">
      Last updated ${esc(STATUS.built_on || "—")}.</p>`;
}


/* =======================================================================
   SECTOR — a destination for "Egyptian bank stocks"

   These pages exist for two reasons. A reader browsing by industry wants the
   whole peer group on one screen with the same measures, and a search engine
   needs a page that is about a category rather than a company. The second is
   why they are generated as real files at /sector/banks and not only rendered
   here.
   ======================================================================= */
function sectorFromSlug(slug) {
  const norm = x => String(x || "").toLowerCase().replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  const hit = SECTORS.find(s => norm(s.sector) === slug);
  return hit ? hit.sector : null;
}

async function viewSector(view, args) {
  const slug = (args[0] || "").toLowerCase();
  const sector = sectorFromSlug(slug);
  if (!sector) {
    view.innerHTML = `<div class="card"><div class="error">
      We do not have a sector called "${esc(slug)}".
      <a href="/markets" onclick="go('/markets')">Browse all companies</a> instead.
      </div></div>`;
    return;
  }

  const members = UNIVERSE.filter(s => s.sector === sector &&
                                       s.asset_type === "equity");
  const metrics = await api("/api/metrics");
  const rows = members.map(s => ({...s, m: metrics[s.ticker] || {}}))
    .sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));

  const med = key => {
    const xs = rows.map(r => r.m[key]).filter(x => x != null).sort((a, b) => a - b);
    if (!xs.length) return null;
    const n = xs.length;
    return n % 2 ? xs[(n - 1) / 2] : (xs[n / 2 - 1] + xs[n / 2]) / 2;
  };
  const totalCap = rows.reduce((t, r) => t + (r.market_cap || 0), 0);

  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>${esc(sector)} on the Egyptian Exchange</h2>
      <p>${count(rows.length)} listed companies in the
         ${esc(sector.toLowerCase())} sector, worth ${bigMoney(totalCap)}
         between them. The medians
         below are for this sector only — comparing a bank with a cement company
         on the same multiple tells you very little.</p>
    </div>

    <div class="card">
      <div class="stats">
        <div class="stat"><div class="k">Companies</div><div class="v">${count(rows.length)}</div></div>
        <div class="stat"><div class="k">Combined value</div><div class="v">${bigMoney(totalCap)}</div></div>
        <div class="stat"><div class="k">Median P/E</div><div class="v">${mult(med("pe"))}</div>
          <div class="note">of those that report earnings</div></div>
        <div class="stat"><div class="k">Median return on equity</div>
          <div class="v">${med("roe_pct") != null ? pctPlain(med("roe_pct")) : "—"}</div></div>
        <div class="stat"><div class="k">Median dividend yield</div>
          <div class="v">${med("dividend_yield_pct") != null ? pctPlain(med("dividend_yield_pct"), 2) : "—"}</div></div>
        <div class="stat"><div class="k">Median 1-year return</div>
          <div class="v ${cls(med("ret_1y"))}">${pct(med("ret_1y"))}</div></div>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><h2>All ${esc(sector.toLowerCase())} companies</h2>
        <p class="sub">Largest first. Click any row for the full page.</p></div>
      <div class="table-scroll"><table class="tbl">
        <thead><tr>
          <th style="text-align:left">Ticker</th>
          <th style="text-align:left">Company</th>
          <th>Price</th><th>1 year</th><th>P/E</th><th>Yield</th>
          <th>Market value</th><th style="text-align:left">Trades</th>
        </tr></thead>
        <tbody>${rows.map(r => `<tr onclick="go('/stock/${esc(r.ticker)}')">
          <td class="tk">${esc(r.ticker)}</td>
          <td style="text-align:left;max-width:230px;overflow:hidden;text-overflow:ellipsis">${esc(r.name)}</td>
          <td>${price(r.price)}</td>
          <td class="${cls(r.ret_1y)}">${pct(r.ret_1y)}${
            r.real_ret_1y != null ? `<div class="${cls(r.real_ret_1y)}" style="font-size:11.5px;opacity:.85">${pct(r.real_ret_1y)} real</div>` : ""}</td>
          <td>${mult(r.m.pe)}</td>
          <td>${r.m.dividend_yield_pct != null ? pctPlain(r.m.dividend_yield_pct, 2) : "—"}</td>
          <td>${bigMoney(r.market_cap)}</td>
          <td style="text-align:left">${liquidityBadge(r.liquidity_band) || esc(r.liquidity_band || "—")}</td>
        </tr>`).join("")}</tbody>
      </table></div>
    </div>

    <p style="margin-top:18px"><a href="/markets" onclick="go('/markets')">← All companies</a></p>`;
}


/* =======================================================================
   FUNDS

   The weakest area of the platform, and the one beginners reach for first.
   What we can honestly show is a current value, a category, a risk band and a
   trailing return. What we cannot show is a chart, because the only free
   source publishes today's NAV and no history at all.

   That gap is stated on the page rather than papered over, and it closes on
   its own: the platform now records the NAV it sees each day, so the history
   nobody publishes will exist here in a year.
   ======================================================================= */
let fundState = {category: null, risk: null, sort: "return_1y"};

async function viewFunds(view) {
  const funds = UNIVERSE.filter(s => s.asset_type === "fund");
  const cats = [...new Set(funds.map(f => (f.fund || {}).category).filter(Boolean))].sort();
  const risks = ["Low Risk", "Moderate", "High Risk"]
    .filter(r => funds.some(f => (f.fund || {}).risk === r));

  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>Egyptian investment funds</h2>
      <p>${count(funds.length)} funds, with the value of one unit today, what
         they invest in and how much they have moved. A fund spreads your money
         across many holdings, which is usually where a first-time investor
         should look before picking individual shares.</p>
    </div>

    <div class="callout info">
      <strong>What we can and cannot show you here.</strong>
      Our free source publishes each fund's current value and a few trailing
      returns, but no history of daily values. Without that history there is
      nothing to chart, nothing to measure risk from, and no way to run a fund
      through the backtester or the scenario tools. We show what exists and
      leave the rest blank rather than filling it in.
      ${STATUS.funds_nav_days ? `We have been recording these values ourselves
      since ${esc(STATUS.funds_nav_first || "recently")} —
      ${count(STATUS.funds_nav_days)} days so far — so this gap closes over
      time.` : ""}
    </div>

    <div class="card">
      <div class="chips" id="fund-cats"></div>
      <div class="chips" id="fund-risks" style="margin-top:10px"></div>
      <div class="form-row" style="margin-top:14px">
        <div class="field"><label>Sort by</label>
          <select id="fund-sort">
            <option value="return_1y">1-year return</option>
            <option value="ytd">Return so far this year</option>
            <option value="nav">Value of one unit</option>
            <option value="name">Name</option>
          </select></div>
      </div>
    </div>

    <div id="fund-body"></div>`;

  const catBox = document.getElementById("fund-cats");
  catBox.innerHTML = `<button class="chip on" data-c="">All types</button>` +
    cats.map(c => `<button class="chip" data-c="${esc(c)}">${esc(c)} (${count(
      funds.filter(f => (f.fund || {}).category === c).length)})</button>`).join("");
  catBox.querySelectorAll(".chip").forEach(b => b.onclick = () => {
    catBox.querySelectorAll(".chip").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    fundState.category = b.dataset.c || null;
    renderFunds();
  });

  const riskBox = document.getElementById("fund-risks");
  riskBox.innerHTML = `<button class="chip on" data-r="">Any risk level</button>` +
    risks.map(r => `<button class="chip" data-r="${esc(r)}">${esc(r)}</button>`).join("");
  riskBox.querySelectorAll(".chip").forEach(b => b.onclick = () => {
    riskBox.querySelectorAll(".chip").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    fundState.risk = b.dataset.r || null;
    renderFunds();
  });

  document.getElementById("fund-sort").onchange = e => {
    fundState.sort = e.target.value;
    renderFunds();
  };
  renderFunds();
}

function renderFunds() {
  let rows = UNIVERSE.filter(s => s.asset_type === "fund");
  if (fundState.category)
    rows = rows.filter(f => (f.fund || {}).category === fundState.category);
  if (fundState.risk)
    rows = rows.filter(f => (f.fund || {}).risk === fundState.risk);

  const k = fundState.sort;
  rows.sort((a, b) => {
    if (k === "name") return a.name.localeCompare(b.name);
    const get = x => k === "return_1y" ? x.ret_1y
      : k === "ytd" ? (x.fund || {}).ytd_pct : x.price;
    const av = get(a), bv = get(b);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return bv - av;
  });

  const riskTag = r => r
    ? `<span class="badge ${r === "High Risk" ? "low" : r === "Moderate" ? "partial" : "high"}">${esc(r)}</span>`
    : "";

  document.getElementById("fund-body").innerHTML = `
    <div class="card">
      <div class="card-head"><h2>${count(rows.length)} fund${rows.length === 1 ? "" : "s"}</h2>
        <p class="sub">Returns are as published by the fund, not calculated by us.</p></div>
      <div class="table-scroll"><table class="tbl">
        <thead><tr>
          <th style="text-align:left">Fund</th>
          <th style="text-align:left">Type</th>
          <th>Value of one unit</th>
          <th>This year</th>
          <th>1 year</th>
          <th style="text-align:left">Risk</th>
        </tr></thead>
        <tbody>${rows.map(f => `<tr onclick="go('/stock/${esc(f.ticker)}')">
          <td style="text-align:left;max-width:280px">${esc(f.name)}</td>
          <td style="text-align:left;color:var(--ink-3);font-size:12.5px">${esc((f.fund || {}).category || "—")}</td>
          <td>${egp2(f.price)}</td>
          <td class="${cls((f.fund || {}).ytd_pct)}">${pct((f.fund || {}).ytd_pct)}</td>
          <td class="${cls(f.ret_1y)}" style="font-weight:600">${pct(f.ret_1y)}</td>
          <td style="text-align:left">${riskTag((f.fund || {}).risk)}</td>
        </tr>`).join("")}</tbody>
      </table></div>
      ${rows.length === 0 ? `<p class="muted">No fund matches those filters.</p>` : ""}
    </div>

    <div class="callout">
      <strong>A fund's published return is not the same as yours.</strong>
      The figures above are what the fund reports. They are before any entry or
      exit fee your bank may charge, and they are nominal — in a year when
      Egyptian prices rose by a fifth, a fund returning 15% left its holders
      slightly worse off in what their money buys.
    </div>`;
}
