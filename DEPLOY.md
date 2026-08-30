# Putting the website online — free, forever

Your site is now a **static website**: a folder of ordinary files. There is no
server to run and nothing that can start charging you.

Everything is already built and waiting in the **`site`** folder.

The one thing I cannot do for you is **create an account in your name.**
Pick any option below — all are genuinely free with no payment card.

---

## Option 1 — Cloudflare Pages (recommended)

Fast worldwide, free forever, no card, and it handles large files well.

### Step 1 — Make the account
1. Go to **https://dash.cloudflare.com/sign-up**
2. Enter your email and a password. Confirm the email they send you.

### Step 2 — Create the site
1. In the left menu click **Workers & Pages**.
2. Click **Create** → the **Pages** tab → **Upload assets**.
3. Give it a name, for example `egx-research`.
4. Click **Select from computer** → **Upload folder**.
5. Choose the folder `Desktop\Website\site`
   *(the folder itself — not the files inside it)*
6. Your browser will warn that the site wants to upload many files. Click
   **Upload**.
7. Wait for it to finish — about 240 files, a few minutes on a normal connection.
8. Click **Deploy site**.

### Step 3 — Your link
Cloudflare shows a link like:

```
https://egx-research.pages.dev
```

That is the link to send your friends. It works on phones and computers.

---

## Option 2 — Netlify Drop (fastest, no account needed to try)

Genuinely the simplest way to see it live.

1. Go to **https://app.netlify.com/drop**
2. Drag the folder `Desktop\Website\site` onto the page.
3. Wait. It gives you a link immediately.

The link works right away. To **keep** it permanently you will be asked to
create a free account — otherwise it expires after a while.

> Good for testing today, then move to Cloudflare for the permanent link.

---

## Option 3 — GitHub Pages

Best if you also want the automatic daily data updates later.

1. Create a free account at **https://github.com/join**
2. Create a new **public** repository called `egx-research`.
3. On the repository page click **Add file** → **Upload files**.
4. Drag in everything **inside** the `site` folder (`index.html`, the `static`
   folder and the `data` folder).
5. Click **Commit changes**.
6. Go to **Settings** → **Pages** (left menu).
7. Under *Branch*, choose **main** and **/ (root)**, then **Save**.
8. Wait 1–2 minutes. Your link appears at the top of that page:

```
https://<your-username>.github.io/egx-research/
```

---

## Which should you pick?

| | Cloudflare Pages | Netlify Drop | GitHub Pages |
|---|---|---|---|
| Free forever | Yes | Yes (with account) | Yes |
| Payment card | No | No | No |
| Account needed | Yes | To keep the link | Yes |
| Easiest | Medium | **Easiest** | Medium |
| Enables auto-updates later | No | No | **Yes** |

**My suggestion:** try **Netlify Drop** right now to see it working, then set up
**Cloudflare Pages** for the permanent link you share.

---

## Looking at it on your own computer first

You do not need any of the above to use the site yourself.

1. Double-click **START_WEBSITE.bat** in the `Website` folder.
2. Open **http://127.0.0.1:8200**

> Opening `site\index.html` directly by double-clicking will **not** work.
> Browsers block pages from reading local data files for security reasons.
> The `START_WEBSITE.bat` file works around this — use it.

---

## How the data stays current

The site is a **snapshot** of the market on the day it was built. It shows a
banner at the top when the data is more than five days old, so nobody is misled
into thinking prices are live.

To refresh it:

1. Tell me **"update the market data"** — I download the newest prices and
   rebuild the `site` folder.
2. Re-upload the folder using the same steps above.

**To make it automatic and free:** use GitHub Pages (Option 3), then tell me.
A configuration file (`.github/workflows/daily-data.yml`) is already written and
waiting. It refreshes the data every weekday evening after the exchange closes,
at no cost on public repositories.

---

## If something goes wrong

| Problem | Cause | Fix |
|---|---|---|
| Page loads but is blank | Data folder was not uploaded | Upload the whole `site` folder, including `data` |
| "Could not load data" | Same as above | Same as above |
| Upload seems stuck | 227 company files takes a while | Let it finish; the total is about 14 MB |
| Opened `index.html` directly and nothing works | Browsers block local file reads | Use `START_WEBSITE.bat` instead |

If you get an error message, paste it to me and I will fix it.

---

## What is in the `site` folder

| | |
|---|---|
| `index.html` | The page itself |
| `static/` | Design and the calculation engine |
| `data/` | All the market data (227 companies) |
| **Total size** | **about 14 MB** |

Nothing in it phones home, and no data about your visitors is collected.
