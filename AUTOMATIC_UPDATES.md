# Automatic daily updates

Set this up once and the website updates itself every trading day, for ever,
free. Neither you nor Claude has to touch it again.

---

## First, an honest limit

**Live, second-by-second prices are not possible for free.** I tested this
directly rather than guessing:

| What I asked the free source for | What came back |
|---|---|
| 5-minute prices | daily closes only |
| 15-minute prices | daily closes only |
| Hourly prices | daily closes only |
| Daily prices | ✅ works properly |

Worse, the source's "current price" field for Egyptian shares is broken — it
reports CIB at EGP 81.20 stamped **July 2024**, two years out of date. The site
deliberately ignores that field rather than showing you a stale number dressed
up as live.

Real-time Egyptian prices need a paid exchange feed, which breaks the EGP 0
rule.

**So the ceiling is: updated automatically after every trading day.** That is
what this sets up.

---

## What you get

The Egyptian Exchange closes at **14:30 Cairo**. The robot starts trying
**15 minutes later** and keeps trying until it genuinely has that day's close:

| Attempt | Cairo time | After the close |
|---|---|---|
| 1st | **14:45** | 15 minutes |
| 2nd | 15:15 | 45 minutes |
| 3rd | 16:00 | 1½ hours |
| 4th | 17:30 | 3 hours |
| 5th | 20:00 | 5½ hours |

Whichever attempt first finds the real close publishes the site. Every later
attempt that day sees the data is already live and **stops within seconds** —
no wasted work, no republishing.

Why several attempts instead of one? Because there is no way to know in advance
exactly when the free data source publishes a given day's close. Guessing one
time would mean either publishing too early and getting nothing, or waiting
hours longer than necessary. Trying repeatedly gets you the close as soon as it
exists.

Each time it runs, the robot:

1. Downloads the latest closing prices for every Egyptian company
2. Removes phantom bars — the source invents zero-volume prices on public
   holidays, which would otherwise make the site claim the market traded
3. Recalculates every ratio, risk figure and fair-value estimate
4. Rebuilds the website
5. **Runs 155 tests** — if the maths breaks, it stops
6. **Runs a safety check** — if the data looks wrong, it stops
7. **Checks it is genuinely newer** than what is already live, and that the
   market has actually shut — so a half-finished session is never published as
   though it were the close
8. Publishes to Cloudflare

Once a week (Sundays) it also refreshes company accounts and checks for newly
listed or delisted companies.

**If anything fails, nothing is published** and your current site stays online
untouched. A broken update can never replace a working site.

### On a holiday

Every attempt looks, finds no new session, and quietly stops. Nothing is
published and nothing is reported as broken. The site keeps showing the last
real trading day — correctly labelled with that date.

## Setup — about 15 minutes, once

You need a free GitHub account. Everything else is already written.

### Step 1 — GitHub account

1. Go to **https://github.com/join**
2. Pick a username, enter your email and a password, confirm the email.

### Step 2 — Create the repository

1. Go to **https://github.com/new**
2. Repository name: `egx-research`
3. Choose **Public**
   *(this matters — free unlimited automation only applies to public repos)*
4. Click **Create repository**.

> **Is public safe?** Yes. The repository holds the website code and public
> market data. There are no passwords in it, and nothing personal.

### Step 3 — Upload the project

On the new empty repository page:

1. Click **uploading an existing file**
2. Open `C:\Users\<you>\Desktop\Website`
3. Select and drag in these, **but not the `site` folder and not `data`**:
   - the `backend` folder
   - the `.github` folder
   - `requirements.txt`
   - all the `.md` files
4. Click **Commit changes**.

> The `site` folder is left out on purpose — the robot rebuilds it every time.
> The `data` folder is left out because the database is large and gets cached
> automatically instead.

> If the `.github` folder is hidden on your computer: in File Explorer click
> **View** → tick **Hidden items**.

### Step 4 — Create a Cloudflare token

This is what lets GitHub publish to Cloudflare on your behalf.

1. Go to **https://dash.cloudflare.com/profile/api-tokens**
2. Click **Create Token**
3. Find **"Edit Cloudflare Workers"** and click **Use template**
4. Scroll down, click **Continue to summary**, then **Create Token**
5. **Copy the token now** — it is shown only once.

You also need your Account ID:

6. Go to **https://dash.cloudflare.com** → **Workers & Pages**
7. On the right under *Account details*, copy the **Account ID**
   (yours is `6cbdb4d4e3a76ef2b9eee46ee5d3b4a5`)

### Step 5 — Give GitHub the two values

1. In your GitHub repository, click **Settings** (top right of the repo)
2. Left menu → **Secrets and variables** → **Actions**
3. Click **New repository secret**, twice:

| Name | Value |
|---|---|
| `CLOUDFLARE_API_TOKEN` | the token you copied |
| `CLOUDFLARE_ACCOUNT_ID` | `6cbdb4d4e3a76ef2b9eee46ee5d3b4a5` |

Type the names **exactly** as written.

> These are stored encrypted. GitHub will never show them again, and they are
> hidden from the logs. Do not paste the token into a chat — including to me.

### Step 6 — Test it

1. In your repository click the **Actions** tab
2. Click **"Update EGX data and deploy"** on the left
3. Click **Run workflow** → leave the mode as `daily` → **Run workflow**
4. Watch it run — a green tick means it worked

The first run will say *"No cached database found — doing a full rebuild"* and
take around an hour, because it downloads ten years of history from scratch.
**Every run after that takes about five minutes.**

That's it. It now runs by itself.

---

## Checking on it later

- **Actions** tab in your repository → every run is listed with a green tick or
  a red cross.
- Each run posts a summary: the market data date, how many companies, how many
  price records.
- GitHub emails you automatically if a run fails.

## Turning it off

Actions tab → the workflow → the `...` menu → **Disable workflow**.

## If a run fails

Click the failed run and read the red step. Common causes:

| Message | Meaning | Fix |
|---|---|---|
| `refusing to deploy` | The safety check caught bad data | Usually the data source having a bad day. It will retry tomorrow; your live site is untouched |
| `Authentication error` | Token wrong or expired | Redo Steps 4 and 5 |
| `market data is N days old` | Source has been failing for a while | Send me the log |

Paste any failure to me and I will fix it.

---

## What this costs

**EGP 0.** GitHub Actions is unlimited for public repositories. Cloudflare Pages
is free. No payment card is involved anywhere.
