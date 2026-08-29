/* Searchable security picker.

   Replaces every long <select> on the site. With 318 stocks and 40 funds, a
   dropdown is unusable: finding CIB meant scrolling past hundreds of entries.

   Typing "CIB", "Commercial", "comm int" or "bank" all reach the same company,
   because matches are scored rather than merely filtered:

     exact ticker            > ticker starts with the term
     > whole word in name    > name starts with term
     > substring anywhere    > every term matches somewhere (out of order)

   That last rule is what makes "comm int bank" work. Bigger companies break
   ties, so "bank" surfaces CIB before a micro-cap with "bank" in its name.
*/

const Picker = (() => {
  let _seq = 0;

  /** Fold accents and Arabic diacritics so "Sewedy" matches "Séwedy". */
  function norm(s) {
    return String(s || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")     // latin accents
      .replace(/[ً-ٰٟ]/g, "") // arabic harakat
      .replace(/[آأإ]/g, "ا")  // alef forms
      .replace(/ة/g, "ه")        // ta marbuta -> ha
      .replace(/ى/g, "ي")        // alef maqsura -> ya
      .trim();
  }

  function score(item, q) {
    const t = norm(item.ticker), n = norm(item.name),
          a = norm(item.name_ar || ""), s = norm(item.sector || "");
    let best = 0;

    if (t === q) best = 1000;
    else if (t.startsWith(q)) best = 900;
    else if (n.startsWith(q)) best = 700;
    else if (new RegExp("\\b" + q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(n)) best = 600;
    else if (n.includes(q)) best = 400;
    else if (a && a.includes(q)) best = 380;
    else if (t.includes(q)) best = 300;
    else if (s.includes(q)) best = 120;

    // Out-of-order multi-word: "comm int bank" -> CIB.
    if (!best) {
      const parts = q.split(/\s+/).filter(Boolean);
      if (parts.length > 1 &&
          parts.every(p => n.includes(p) || t.includes(p) || a.includes(p))) {
        best = 250;
      }
    }
    if (!best) return 0;

    // Size breaks ties so the obvious answer comes first.
    const cap = item.market_cap || 0;
    return best * 1e6 + Math.min(cap / 1e6, 9e5);
  }

  function search(items, query, limit = 12) {
    const q = norm(query);
    if (!q) {
      return items.slice()
        .sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0))
        .slice(0, limit);
    }
    const hits = [];
    for (const it of items) {
      const sc = score(it, q);
      if (sc) hits.push([sc, it]);
    }
    hits.sort((a, b) => b[0] - a[0]);
    return hits.slice(0, limit).map(h => h[1]);
  }

  /**
   * Attach a searchable picker.
   *
   * opts.items     list to search (defaults to the whole universe)
   * opts.value     initially selected ticker
   * opts.onSelect  called with the chosen item
   * opts.placeholder
   */
  function create(container, opts = {}) {
    const id = "pk" + (++_seq);
    const items = opts.items || (typeof UNIVERSE !== "undefined" ? UNIVERSE : []);
    const el = typeof container === "string"
      ? document.getElementById(container) : container;
    if (!el) return null;

    let selected = null;
    if (opts.value) selected = items.find(i => i.ticker === opts.value) || null;

    el.classList.add("picker");
    el.innerHTML = `
      <input class="picker-input" id="${id}-in" type="text" autocomplete="off"
             spellcheck="false"
             placeholder="${esc(opts.placeholder || "Type a company name or ticker…")}">
      <div class="picker-menu hidden" id="${id}-menu"></div>`;

    const input = el.querySelector(".picker-input");
    const menu = el.querySelector(".picker-menu");
    let cursor = -1, current = [];

    const label = it => `${it.ticker} — ${it.name}`;
    if (selected) input.value = label(selected);

    function render(list) {
      current = list;
      cursor = list.length ? 0 : -1;
      if (!list.length) {
        menu.innerHTML = `<div class="picker-empty">No match. Try a ticker, a
          company name, or a sector like "bank".</div>`;
      } else {
        menu.innerHTML = list.map((it, i) => {
          const isFund = it.asset_type === "fund";
          const right = isFund
            ? `<span class="picker-tag fund">Fund</span>`
            : (it.price != null ? `<span class="picker-px">${egp2(it.price)}</span>` : "");
          return `<div class="picker-item${i === cursor ? " on" : ""}" data-i="${i}">
            <span class="picker-l">
              <span class="picker-tk">${esc(it.ticker.replace(/^FUND-/, ""))}</span>
              <span class="picker-nm">${esc(it.name)}</span>
            </span>
            <span class="picker-r">${right}</span>
          </div>`;
        }).join("");
      }
      menu.classList.remove("hidden");
      menu.querySelectorAll(".picker-item").forEach(node => {
        node.onmousedown = e => { e.preventDefault(); choose(+node.dataset.i); };
      });
    }

    function choose(i) {
      const it = current[i];
      if (!it) return;
      selected = it;
      input.value = label(it);
      menu.classList.add("hidden");
      input.blur();
      if (opts.onSelect) opts.onSelect(it);
    }

    function move(d) {
      if (!current.length) return;
      cursor = (cursor + d + current.length) % current.length;
      menu.querySelectorAll(".picker-item").forEach((n, i) =>
        n.classList.toggle("on", i === cursor));
      const node = menu.querySelector(".picker-item.on");
      if (node) node.scrollIntoView({block: "nearest"});
    }

    input.addEventListener("focus", () => { input.select(); render(search(items, "")); });
    input.addEventListener("input", () => render(search(items, input.value)));
    input.addEventListener("blur", () => setTimeout(() => {
      menu.classList.add("hidden");
      // Restore the last valid choice so the box is never left half-typed.
      if (selected) input.value = label(selected); else input.value = "";
    }, 120));
    input.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "Enter") { e.preventDefault(); choose(cursor); }
      else if (e.key === "Escape") { menu.classList.add("hidden"); input.blur(); }
    });

    return {
      get value() { return selected ? selected.ticker : null; },
      get item() { return selected; },
      set(ticker) {
        const it = items.find(i => i.ticker === ticker);
        if (it) { selected = it; input.value = label(it); }
      },
      focus() { input.focus(); },
    };
  }

  return {create, search, norm, score};
})();
