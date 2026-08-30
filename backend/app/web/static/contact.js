/* EGX Research — contact and corrections.

   Why a site like this needs one

   Everything here rests on data pulled from free public sources, and there is
   a page on this site whose entire job is to list what is wrong with it. That
   page can only ever show the faults we already know how to look for. The
   ones we have not thought of are found by readers, and a reader who finds one
   and has nowhere to send it is a reader who quietly stops trusting the site
   and leaves — taking the correction with them.

   So this page exists to make being told easy, and to say plainly who is on
   the other end: one person, not a company, not a support desk.
*/

const CONTACT_EMAIL = "peterrasmy6@gmail.com";

function mailtoLink(subject) {
  return "mailto:" + CONTACT_EMAIL + "?subject=" + encodeURIComponent(subject);
}

async function viewContact(view) {
  view.innerHTML = `
    <div class="section-head" style="margin-top:28px">
      <h2>${esc(t("contact.title", "Contact and corrections"))}</h2>
      <p>${esc(t("contact.lede",
        "One person builds and runs this site. There is no company behind it, no support desk and no team — which means every message is read, and also that a reply may take a few days."))}</p>
    </div>

    <div class="callout info">
      <strong>${esc(t("contact.found.title", "Found a number that looks wrong?"))}</strong>
      ${esc(t("contact.found.body",
        "Please say so. This site publishes a page listing the faults it knows about in its own data, and that page is incomplete by definition — it can only show what we already know how to detect. A reader who spots something we missed is the only way the rest gets found."))}
    </div>

    <div class="card">
      <div class="card-head"><h2>${esc(t("contact.how", "How to reach me"))}</h2></div>
      <p style="font-size:16px;margin:0 0 18px">
        <a href="mailto:${esc(CONTACT_EMAIL)}" style="font-weight:600">${esc(CONTACT_EMAIL)}</a>
      </p>
      <div class="table-scroll"><table class="tbl">
        <thead><tr>
          <th style="text-align:left">${esc(t("contact.what", "What you want to say"))}</th>
          <th style="text-align:left">${esc(t("contact.helpful", "What helps most"))}</th>
        </tr></thead>
        <tbody>
          <tr><td style="text-align:left"><a href="${mailtoLink("EGX Research — data error")}">${esc(t("contact.r1", "A figure is wrong"))}</a></td>
              <td style="text-align:left">${esc(t("contact.r1h", "The ticker, which number, and what you believe it should be. A link to your source is ideal."))}</td></tr>
          <tr><td style="text-align:left"><a href="${mailtoLink("EGX Research — missing company")}">${esc(t("contact.r2", "A company is missing"))}</a></td>
              <td style="text-align:left">${esc(t("contact.r2h", "The ticker. Some tickers are left out on purpose — rights issues and second share classes are not separate companies — but genuine gaps happen."))}</td></tr>
          <tr><td style="text-align:left"><a href="${mailtoLink("EGX Research — how is this calculated?")}">${esc(t("contact.r3", "How was this calculated?"))}</a></td>
              <td style="text-align:left">${esc(t("contact.r3h", "The page you were on. Most methods are written up under How these numbers are worked out, but if you had to ask, that page has failed and I would like to know."))}</td></tr>
          <tr><td style="text-align:left"><a href="${mailtoLink("EGX Research — something is broken")}">${esc(t("contact.r4", "Something is broken"))}</a></td>
              <td style="text-align:left">${esc(t("contact.r4h", "What you clicked, on a phone or a computer, and which browser."))}</td></tr>
        </tbody>
      </table></div>
    </div>

    <div class="card">
      <div class="card-head"><h2>${esc(t("contact.cannot", "What I cannot do"))}</h2></div>
      <p class="muted" style="font-size:14.5px;line-height:1.7;margin:0">
        ${esc(t("contact.cannot.body",
          "I cannot tell you what to buy or sell, whether a share is a good investment for you, or how to divide your money. Not out of caution — I am not licensed by the Financial Regulatory Authority or anyone else, I do not know your circumstances, and answering would be both useless and against everything this site is for. Questions about the data, the methods and the tools are very welcome."))}
      </p>
    </div>

    <p class="disclaim">${esc(t("contact.privacy",
      "Your email is used to reply to you and nothing else. There is no mailing list, no account and no tracking on this site, so there is nothing to unsubscribe from."))}</p>`;
}
