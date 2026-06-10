# Deploying ARTIS

ARTIS is a monthly trend-intelligence app for a luxury interior-design firm. It
researches what designers are doing and what clients are asking for, scores every
trend against your firm's content blueprint, and publishes a website. Everything
runs in the cloud — **no servers and no database to manage.**

You need three things, all free to start:

1. A **GitHub account** (hosts the code, your blueprint, and the data)
2. A **Vercel account** (serves the website) — sign in with GitHub
3. An **Anthropic API key** — https://console.anthropic.com (this is the only paid part; it powers the AI analysis)

Total setup time: ~15 minutes.

---

## Step 1 — Get your own copy of the code

On the template repo, click **“Use this template” → “Create a new repository.”**
Name it whatever you like (e.g. `my-firm-trends`) and make it **Private**
(your blueprint and strategy data live here).

> Keep it private — the repo holds your firm's content blueprint and generated strategy.

---

## Step 2 — Create an Anthropic API key

1. Go to https://console.anthropic.com → **API Keys → Create Key**
2. Copy the key (starts with `sk-ant-…`). You'll paste it in Steps 3 and 5.

---

## Step 3 — Add the key to GitHub Actions (runs the monthly pipeline)

In **your** new repo: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | your `sk-ant-…` key |

That's the only secret the pipeline needs — GitHub provides the rest automatically.

---

## Step 4 — Deploy the website to Vercel

1. Go to https://vercel.com → **Add New → Project → Import** your repo
2. Settings:
   - **Framework Preset:** Other
   - **Root Directory:** `./` (default)
   - **Build/Output:** leave empty (it's static + functions)
3. Click **Deploy.** You'll get a live URL like `your-firm-trends.vercel.app`.

---

## Step 5 — Let the website accept blueprint uploads

The site's **“Add Client”** tab lets you upload a blueprint; it commits the file to
your repo. That needs a token:

1. **Create a token:** GitHub → Settings → Developer settings → **Fine-grained tokens →
   Generate new token.** Repository access = **only your repo**; Permissions →
   **Contents: Read and write.** Copy it (`github_pat_…`).
2. In **Vercel → your project → Settings → Environment Variables**, add:

   | Name | Value |
   |------|-------|
   | `GITHUB_TOKEN` | the `github_pat_…` token |
   | `GITHUB_REPO` | `your-username/your-repo` |
   | `ANTHROPIC_API_KEY` | your `sk-ant-…` key |

3. **Redeploy** (Deployments → ⋯ → Redeploy) so the variables take effect.

> Optional: set `UPLOAD_TOKEN` to any random string to password-gate uploads — the
> “Add Client” tab has an access-code field that sends it.

---

## Step 6 — Add your firm's blueprint

The repo ships with **Doniphan Moore** as a demo so the app isn't empty. Replace it
with your own:

- **Easiest:** on the live site, open **Explore → Add Client**, upload your
  `*.md` content blueprint. It lands in `blueprints/` in your repo.
- **Or** in GitHub, delete `blueprints/DoniphanMoore-internal-blueprint-v6.md` and
  add your own `.md` file to `blueprints/`.

(A blueprint is a Markdown document describing the firm's identity, convictions,
voice, and content rules — see the demo file for the structure.)

---

## Step 7 — Run it

GitHub → **Actions** tab → **ARTIS monthly run** → **Run workflow.**

It takes ~30–40 minutes (the AI analysis is the long part). When it finishes it
commits fresh data, and Vercel auto-redeploys — your live site updates with this
month's trends, strategy, and holiday recommendations for each blueprint.

After this first manual run, it repeats **automatically on the 1st of each month.**

---

## What you get, every month
- **Overview** — what designers are doing + what clients are asking for
- **Explore** — every professional + demand trend, searchable
- **By Client** — for each firm: a brand brief, every trend scored Lead/Watch/Skip
  with a fit %, a likely opinion in the firm's voice, and the holidays worth speaking on
- A branded **PDF/HTML trend report** and a versioned **monthly archive** in `data/`

---

## Costs
- GitHub + Vercel: free tiers are plenty for this.
- Anthropic API: pay-as-you-go. A monthly run is a few dollars of API usage per
  blueprint (more blueprints = more cost, since every trend is scored per firm).

## Troubleshooting
- **A workflow step failed:** open the run in the Actions tab, read the red error.
  The usual first-run culprit is a missing `ANTHROPIC_API_KEY` secret (Step 3).
- **Upload says “server not configured”:** `GITHUB_TOKEN`/`GITHUB_REPO` aren't set in
  Vercel, or you didn't redeploy after adding them (Step 5).
- **Site shows old data:** Vercel redeploys on each run's commit; hard-refresh
  (Ctrl/Cmd+Shift+R).

## Local development (optional)
You don't need this to deploy. To preview locally: `python serve.py` → open
`http://localhost:8800/`. The pipeline can run locally too — see `pipeline/` and
copy `.env.example` to `.env` with your keys.
