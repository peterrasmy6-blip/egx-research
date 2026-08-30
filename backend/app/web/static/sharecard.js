/* EGX Research — shareable result cards.

   The single most understandable thing this site produces is the answer to
   "what if I had invested?". It is concrete, personal, and instantly legible
   to someone who knows nothing about markets — which makes it the one result
   people actually pass on.

   A pasted screenshot loses everything that makes the number honest: what was
   assumed, over what period, whether dividends were counted, and what it is
   worth in money that still buys the same things. So the card is drawn here,
   with those attached, and the site's own address on it.

   Drawn on a canvas rather than assembled from an image file: nothing to
   download, nothing to host, and it works offline.
*/

const CARD_W = 1200, CARD_H = 630;   // the standard social preview shape

function _roundRect(c, x, y, w, h, r) {
  c.beginPath();
  c.moveTo(x + r, y);
  c.arcTo(x + w, y, x + w, y + h, r);
  c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r);
  c.arcTo(x, y, x + w, y, r);
  c.closePath();
}

function _wrap(c, text, x, y, maxW, lineH, maxLines) {
  const words = String(text).split(/\s+/);
  let line = "", lines = 0;
  for (const w of words) {
    const test = line ? line + " " + w : w;
    if (c.measureText(test).width > maxW && line) {
      c.fillText(line, x, y);
      y += lineH;
      line = w;
      if (++lines >= (maxLines || 99) - 1) break;
    } else {
      line = test;
    }
  }
  if (line) c.fillText(line, x, y);
  return y + lineH;
}

/**
 * Draw a result card.
 *
 * opts: {eyebrow, headline, figures:[{label,value,tone}], footnotes:[...]}
 */
function drawShareCard(canvas, opts) {
  const c = canvas.getContext("2d");
  const INK = "#0f1723", INK2 = "#4a5568", INK3 = "#8492a6";
  const ACCENT = "#0b6b5e", UP = "#137a4e", DOWN = "#c0392b";

  canvas.width = CARD_W;
  canvas.height = CARD_H;

  c.fillStyle = "#ffffff";
  c.fillRect(0, 0, CARD_W, CARD_H);

  // A quiet band of the brand colour rather than a full-bleed background:
  // this has to stay readable as a thumbnail in a chat app.
  c.fillStyle = ACCENT;
  c.fillRect(0, 0, CARD_W, 10);

  // Wordmark
  c.fillStyle = ACCENT;
  _roundRect(c, 64, 56, 62, 34, 7);
  c.fill();
  c.fillStyle = "#ffffff";
  c.font = "700 19px Inter, system-ui, sans-serif";
  c.fillText("EGX", 76, 80);
  c.fillStyle = INK;
  c.font = "600 20px Inter, system-ui, sans-serif";
  c.fillText("Research", 138, 80);

  // Eyebrow
  c.fillStyle = INK3;
  c.font = "600 17px Inter, system-ui, sans-serif";
  c.fillText(String(opts.eyebrow || "").toUpperCase(), 64, 148);

  // Headline
  c.fillStyle = INK;
  c.font = "700 46px Inter, system-ui, sans-serif";
  const afterHead = _wrap(c, opts.headline || "", 64, 205, CARD_W - 128, 56, 2);

  // Figures
  const figs = (opts.figures || []).slice(0, 3);
  const colW = (CARD_W - 128) / Math.max(1, figs.length);
  let fy = Math.max(afterHead + 30, 330);
  figs.forEach((f, i) => {
    const x = 64 + i * colW;
    c.fillStyle = INK3;
    c.font = "600 16px Inter, system-ui, sans-serif";
    c.fillText(String(f.label).toUpperCase(), x, fy);
    c.fillStyle = f.tone === "up" ? UP : f.tone === "down" ? DOWN : INK;
    c.font = "700 42px Inter, system-ui, sans-serif";
    c.fillText(String(f.value), x, fy + 52);
  });

  // Footnotes — the assumptions, which are the whole point of drawing this
  // rather than letting someone screenshot a number on its own.
  c.fillStyle = INK2;
  c.font = "400 18px Inter, system-ui, sans-serif";
  let ny = fy + 116;
  for (const note of (opts.footnotes || []).slice(0, 3)) {
    ny = _wrap(c, note, 64, ny, CARD_W - 128, 26, 2);
    ny += 2;
  }

  // Footer
  c.fillStyle = "#eef1f4";
  c.fillRect(64, CARD_H - 78, CARD_W - 128, 1);
  c.fillStyle = INK3;
  c.font = "500 17px Inter, system-ui, sans-serif";
  c.fillText("egx-research.pages.dev", 64, CARD_H - 44);
  c.textAlign = "right";
  c.fillText("Past results. Not advice.", CARD_W - 64, CARD_H - 44);
  c.textAlign = "left";
  return canvas;
}

/** Build the card and hand it to the visitor as a PNG. */
function downloadShareCard(filename, opts) {
  const canvas = document.createElement("canvas");
  drawShareCard(canvas, opts);
  canvas.toBlob(blob => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, "image/png");
}

function shareCardButton(id, label = "Save as image") {
  return `<button class="btn btn-ghost btn-sm" id="${id}">${esc(label)}</button>`;
}
