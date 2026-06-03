# JP RWEE 2026 — Survey Progress Dashboard

Monitoring dashboard for the WFP Joint Programme for Rural Women Economic
Empowerment (JP RWEE) 2026 phone survey across Fiji, Kiribati, Tonga, and
Solomon Islands.

The dashboard is updated **manually** by running a script on your local
machine. Raw data never leaves your computer — only aggregated summary
counts (totals, percentages, counts per district and agent) are published.

---

## Your workflow (once set up)

Whenever you want to refresh the public dashboard:

```bash
# 1. Pull latest data from KoboToolbox & regenerate the HTML
python fetch_kobo_data.py

# 2. Publish the updated HTML to GitHub Pages
bash push_dashboard.sh
```

That's it. The live dashboard updates within seconds of the push.

---

## One-time GitHub setup

### 1. Create a public GitHub repository

Go to [github.com](https://github.com) → **New repository**
- Name: e.g. `jp-rwee-dashboard`
- Visibility: **Public** (required for free GitHub Pages)
- Do **not** tick "Add a README" — you'll push this folder

### 2. Push this folder to GitHub

```bash
cd jp-rwee-dashboard
git init
git add .
git commit -m "Initial setup"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/jp-rwee-dashboard.git
git push -u origin main
```

### 3. Enable GitHub Pages

In your repo → **Settings** → **Pages**
- Source: **Deploy from a branch**
- Branch: `main` / folder: `/docs`
- Click **Save**

Your public dashboard URL will appear at the top of that page:
```
https://YOUR-USERNAME.github.io/jp-rwee-dashboard/
```

> **Note:** No GitHub Actions, no secrets, no scheduled jobs needed.
> The API token stays on your machine only.

---

## Files

| File | Purpose |
|------|---------|
| `fetch_kobo_data.py` | Pulls data from KoboToolbox, aggregates into counts, writes `docs/index.html` |
| `push_dashboard.sh` | Commits and pushes `docs/index.html` to GitHub Pages |
| `docs/index.html` | The generated static dashboard (served by GitHub Pages) |

---

## What counts as "Completed"?

A record is counted as **Completed** when all three conditions are true:
- `Call_Status = answered`
- `RESPConsent = yes`
- Respondent is 18 or older (`RESPAge ≥ 18`, or `RESPIsAdult = yes` for age-grouped responses)

**Target:** 400 completed surveys per country (1,600 total).

---

*Raw survey data is never published. Built for WFP JP RWEE 2026 Pacific.*
