#!/usr/bin/env python3
"""
JP RWEE 2026 - KoboToolbox Data Fetcher & Dashboard Generator
==============================================================
Run this script manually whenever you want to update the dashboard.
It pulls data from KoboToolbox, aggregates into summary counts ONLY
(no raw data is saved or published), and writes docs/index.html.

Then run:  bash push_dashboard.sh
to publish the updated HTML to GitHub Pages.

Usage:
    python fetch_kobo_data.py

Requirements:
    pip install requests
"""

import json
import os
import sys
import datetime
import requests

# ─────────────────────────────────────────────
# CONFIG — edit these before running
# ─────────────────────────────────────────────
CONFIG = {
    # Your KoboToolbox API token
    "api_token": "2b3cf243617e5905c7db481b19d2d0100397dc0f",

    # KoboToolbox server (EU instance)
    "kobo_server": "https://eu.kobotoolbox.org",

    # Exact name of the form as it appears in KoboToolbox
    "form_name": "JP RWEE Data Collection - 2026",

    # Where to write the output HTML dashboard
    "output_path": "docs/index.html",

    # Target number of completed surveys per country
    "target_per_country": 400,
}

# ─────────────────────────────────────────────
# FIELD MAPPINGS (from XLSForm survey sheet)
# ─────────────────────────────────────────────

AGENT_FIELDS = {
    "Fiji":     "FijiAgent",
    "Kiribati": "KiribatiAgent",
    "Tonga":    "TongaAgent",
    "Solomon":  "SolsAgent",
}

ADM2_FIELDS = {
    "Fiji":     "ADM2Fiji",
    "Kiribati": "ADM2Kiribati",
    "Tonga":    "ADM2Tonga",
    "Solomon":  "ADM2Solomon",
}

ADM3_FIELDS = {
    "Fiji":     ["ADM3Fiji_Navosa", "ADM3Fiji_Ba"],
    "Kiribati": ["ADM3Kiribati"],
    "Tonga":    ["ADM3Tonga_Eua", "ADM3Tonga_Haapai", "ADM3Tonga_Tongatapu"],
    "Solomon":  ["ADM3Sols_Western"],
}

# Solomon: Guadalcanal and Malaita skip ADM3, go direct to ADM4
ADM3_DIRECT_FIELDS = {
    "Solomon": {
        "Guadalcanal": "ADM4Sols_Guadalcanal",
        "Malaita":     "ADM4Sols_Malaita",
    }
}

COUNTRY_LABELS = {
    "Fiji": "Fiji", "Kiribati": "Kiribati",
    "Tonga": "Tonga", "Solomon": "Solomon Islands",
}

AGENT_LABELS = {
    "Shannon_Chand":        "Shannon Chand",
    "Elina_Seninunukula":   "Elina Seninunukula",
    "TBA":                  "TBA",
    "Francisco":            "Bwebwenteraoi Francisco",
    "Louisa_Karianako":     "Louisa Karianako",
    "Halatono_Fakaosi":     "Halatono Fakaosi",
    "Malia_Taunaholo":      "Malia Taunaholo",
    "Petero_Kini":          "Petero Kini",
    "Adi_Tawakedau":        "Adi Tawakedau",
    "Vakasau_Selo":         "Vakasau Selo",
}

ADM3_LABELS = {
    "Namataku": "Namataku", "Nasikawa": "Nasikawa",
    "Noikoro": "Noikoro", "Navatusila": "Navatusila",
    "Magodro": "Magodro",
    "Nonouti": "Nonouti", "Onotoa": "Onotoa",
    "NorthTabiteuea": "North Tabiteuea", "SouthTabiteuea": "South Tabiteuea",
    "Hahake": "Hahake (Eua)", "Hihifo": "Hihifo (Eua)", "Haano": "Ha'ano",
    "Foa": "Foa", "Lifuka": "Lifuka",
    "Kolofoou": "Kolofo'ou", "Kolomotua": "Kolomotu'a",
    "Gizo": "Gizo", "Kolombangara": "Kolombangara",
    "NewGeorgia": "New Georgia", "Ranonga": "Ranonga",
    "Rendova": "Rendova", "Simbo": "Simbo", "Vella lavella": "Vella Lavella",
    "Guadalcanal": "Guadalcanal", "Malaita": "Malaita",
}


# ─────────────────────────────────────────────
# STEP 1 — Find the form UID on KoboToolbox
# ─────────────────────────────────────────────

def get_form_uid(server, token, form_name):
    url = f"{server}/api/v2/assets/"
    headers = {"Authorization": f"Token {token}"}
    params = {"format": "json", "q": form_name}

    print(f"[1/4] Searching for form: '{form_name}' ...")
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        sys.exit(f"ERROR: Could not connect to {server}.\nCheck your internet connection and server URL.")
    except requests.exceptions.HTTPError as e:
        sys.exit(f"ERROR: API returned {resp.status_code}. Check your API token.\n{e}")

    data = resp.json()
    results = data.get("results", [])

    for asset in results:
        if asset.get("name", "").strip() == form_name.strip():
            uid = asset["uid"]
            print(f"       Found — UID: {uid}")
            return uid

    if results:
        print("WARNING: No exact name match. Forms found on your account:")
        for a in results[:10]:
            print(f"  - \"{a.get('name')}\"  (uid={a.get('uid')})")
        sys.exit("Update CONFIG['form_name'] to match one of the names above exactly.")

    sys.exit("ERROR: No forms found. Check your API token and server URL.")


# ─────────────────────────────────────────────
# STEP 2 — Download all submissions
# ─────────────────────────────────────────────

def fetch_all_submissions(server, token, uid):
    headers = {"Authorization": f"Token {token}"}
    url = f"{server}/api/v2/assets/{uid}/data/"
    records = []

    print(f"[2/4] Downloading submissions ...")
    while url:
        resp = requests.get(url, headers=headers,
                            params={"format": "json", "limit": 500}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("results", [])
        records.extend(batch)
        total = data.get("count", len(records))
        print(f"       {len(records)} / {total} records ...")
        url = data.get("next")

    print(f"       Download complete — {len(records)} total records.")
    return records


# ─────────────────────────────────────────────
# STEP 3 — Aggregate into summary counts only
# ─────────────────────────────────────────────

def get_adm3(record, country):
    for field in ADM3_FIELDS.get(country, []):
        val = record.get(field, "")
        if val and str(val).strip():
            return str(val).strip()
    if country == "Solomon":
        adm2 = record.get("ADM2Solomon", "")
        if adm2 in ADM3_DIRECT_FIELDS.get("Solomon", {}):
            return adm2
    return "Unknown"


def get_agent(record, country):
    field = AGENT_FIELDS.get(country)
    if field:
        val = record.get(field, "") or ""
        return AGENT_LABELS.get(val, val) if val else "Unknown"
    return "Unknown"


def aggregate(records):
    print(f"[3/4] Aggregating {len(records)} records ...")

    summary = {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_records": len(records),
        "countries": {}
    }

    for country in AGENT_FIELDS:
        summary["countries"][country] = {
            "label": COUNTRY_LABELS[country],
            "total_calls": 0,
            "answered": 0,
            "no_answer": 0,
            "completed": 0,
            "refused": 0,
            "callback": 0,
            "target": CONFIG["target_per_country"],
            "adm3": {},
            "agents": {},
        }

    for rec in records:
        country = rec.get("Country", "")
        if country not in summary["countries"]:
            continue

        cs = summary["countries"][country]
        call_status = rec.get("Call_Status", "")
        consent     = rec.get("RESPConsent", "")
        agent       = get_agent(rec, country)
        adm3_raw    = get_adm3(rec, country)
        adm3_label  = ADM3_LABELS.get(adm3_raw, adm3_raw)

        answered = (call_status == "answered")
        cs["total_calls"] += 1
        cs["answered"]    += 1 if answered else 0
        cs["no_answer"]   += 1 if not answered else 0

        # Completed = answered + consented + adult
        resp_age   = rec.get("RESPAge")
        resp_adult = rec.get("RESPIsAdult", "")
        try:
            age_ok = int(resp_age) >= 18
        except (TypeError, ValueError):
            age_ok = (resp_adult == "yes")

        completed = answered and consent == "yes"  and age_ok
        refused   = answered and consent == "no"
        callback  = answered and consent == "later"

        cs["completed"] += 1 if completed else 0
        cs["refused"]   += 1 if refused   else 0
        cs["callback"]  += 1 if callback  else 0

        # ADM3 bucket
        if adm3_label not in cs["adm3"]:
            cs["adm3"][adm3_label] = {"total_calls":0,"answered":0,"no_answer":0,"completed":0}
        a3 = cs["adm3"][adm3_label]
        a3["total_calls"] += 1
        a3["answered"]    += 1 if answered  else 0
        a3["no_answer"]   += 1 if not answered else 0
        a3["completed"]   += 1 if completed else 0

        # Agent bucket
        if agent not in cs["agents"]:
            cs["agents"][agent] = {"total_calls":0,"answered":0,"no_answer":0,"completed":0}
        ag = cs["agents"][agent]
        ag["total_calls"] += 1
        ag["answered"]    += 1 if answered  else 0
        ag["no_answer"]   += 1 if not answered else 0
        ag["completed"]   += 1 if completed else 0

    for country in summary["countries"].values():
        country["adm3"]   = dict(sorted(country["adm3"].items(),   key=lambda x: x[1]["completed"], reverse=True))
        country["agents"] = dict(sorted(country["agents"].items(), key=lambda x: x[1]["completed"], reverse=True))

    return summary


# ─────────────────────────────────────────────
# STEP 4 — Generate static HTML dashboard
# ─────────────────────────────────────────────

def generate_html(summary):
    gen   = summary["generated_at"]
    total = summary["total_records"]
    target_total = CONFIG["target_per_country"] * 4

    country_order = ["Fiji", "Kiribati", "Tonga", "Solomon"]
    flag_map = {"Fiji":"🇫🇯","Kiribati":"🇰🇮","Tonga":"🇹🇴","Solomon":"🇸🇧"}

    total_completed = sum(
        summary["countries"].get(c, {}).get("completed", 0) for c in country_order
    )
    overall_pct = round(total_completed / target_total * 100) if target_total else 0

    country_cards = ""
    country_tabs  = ""
    tab_contents  = ""

    for i, country in enumerate(country_order):
        if country not in summary["countries"]:
            continue
        c    = summary["countries"][country]
        flag = flag_map[country]
        label = c["label"]
        pct  = min(round(c["completed"] / c["target"] * 100) if c["target"] else 0, 100)

        country_cards += f"""
        <div class="country-card" onclick="showTab('{country}')">
            <div class="card-flag">{flag}</div>
            <div class="card-label">{label}</div>
            <div class="card-stat">{c['completed']}<span class="card-target">/{c['target']}</span></div>
            <div class="progress-bar-wrap">
                <div class="progress-bar" style="width:{pct}%"></div>
            </div>
            <div class="card-pct">{pct}% complete</div>
            <div class="card-sub">✅ {c['answered']} answered &nbsp;·&nbsp; 📵 {c['no_answer']} no answer</div>
        </div>"""

        active = "active" if i == 0 else ""
        country_tabs += f'<button class="tab-btn {active}" onclick="showTab(\'{country}\')" id="tab-{country}">{flag} {label}</button>'

        adm3_rows = ""
        for area, stats in c["adm3"].items():
            a_pct = min(round(stats["completed"] / c["target"] * 100) if c["target"] else 0, 100)
            adm3_rows += f"""
                <tr>
                    <td>{area}</td>
                    <td class="num">{stats['total_calls']}</td>
                    <td class="num">{stats['answered']}</td>
                    <td class="num">{stats['no_answer']}</td>
                    <td class="num complete">{stats['completed']}</td>
                    <td class="pct-cell">
                        <div class="mini-bar-wrap"><div class="mini-bar" style="width:{a_pct}%"></div></div>
                        <span>{a_pct}%</span>
                    </td>
                </tr>"""
        if not adm3_rows:
            adm3_rows = '<tr><td colspan="6" class="empty">No data yet</td></tr>'

        agent_rows = ""
        for agent_name, stats in c["agents"].items():
            agent_rows += f"""
                <tr>
                    <td>{agent_name}</td>
                    <td class="num">{stats['total_calls']}</td>
                    <td class="num">{stats['answered']}</td>
                    <td class="num">{stats['no_answer']}</td>
                    <td class="num complete">{stats['completed']}</td>
                </tr>"""
        if not agent_rows:
            agent_rows = '<tr><td colspan="5" class="empty">No data yet</td></tr>'

        hidden = "" if i == 0 else "hidden"
        tab_contents += f"""
        <div class="tab-content {hidden}" id="content-{country}">
            <h2>{flag} {label} &mdash; Progress Overview</h2>
            <div class="stats-row">
                <div class="stat-box"><div class="stat-num">{c['total_calls']}</div><div class="stat-lbl">Total Calls</div></div>
                <div class="stat-box green"><div class="stat-num">{c['completed']}</div><div class="stat-lbl">Completed</div></div>
                <div class="stat-box blue"><div class="stat-num">{c['answered']}</div><div class="stat-lbl">Answered</div></div>
                <div class="stat-box grey"><div class="stat-num">{c['no_answer']}</div><div class="stat-lbl">No Answer</div></div>
                <div class="stat-box orange"><div class="stat-num">{c['refused']}</div><div class="stat-lbl">Refused</div></div>
                <div class="stat-box yellow"><div class="stat-num">{c['callback']}</div><div class="stat-lbl">Callback</div></div>
            </div>
            <h3>By District (ADM3)</h3>
            <table>
                <thead><tr><th>District</th><th>Calls</th><th>Answered</th><th>No Answer</th><th>Completed</th><th>Progress</th></tr></thead>
                <tbody>{adm3_rows}</tbody>
            </table>
            <h3>By Enumerator</h3>
            <table>
                <thead><tr><th>Agent</th><th>Calls</th><th>Answered</th><th>No Answer</th><th>Completed</th></tr></thead>
                <tbody>{agent_rows}</tbody>
            </table>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JP RWEE Enumerator Dashboard</title>
<style>
  :root {{
    --bg:#f4f6fb; --card:#ffffff; --primary:#0057a8; --green:#1a9e5f;
    --blue:#0d6efd; --orange:#e07000; --yellow:#b8860b; --grey:#6c757d;
    --text:#1a2233; --subtext:#5a6474; --border:#dde3ef;
    --progress:#0057a8; --progress-bg:#dde3ef; --radius:10px;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }}
  header {{ background:var(--primary); color:#fff; padding:18px 28px 14px; border-bottom:3px solid #003d80; }}
  header h1 {{ font-size:1.35rem; font-weight:700; letter-spacing:.3px; }}
  header p  {{ font-size:.85rem; opacity:.85; margin-top:3px; }}
  .meta {{ font-size:.78rem; opacity:.7; margin-top:6px; }}
  .overall {{ background:var(--card); padding:18px 28px; border-bottom:1px solid var(--border);
              display:flex; align-items:center; gap:28px; flex-wrap:wrap; }}
  .overall-label {{ font-size:.9rem; color:var(--subtext); }}
  .overall-num {{ font-size:1.6rem; font-weight:700; color:var(--primary); }}
  .overall-bar-wrap {{ flex:1; min-width:200px; background:var(--progress-bg); border-radius:6px; height:14px; }}
  .overall-bar {{ background:var(--primary); height:14px; border-radius:6px; transition:width .6s ease; }}
  .country-cards {{ display:flex; gap:16px; padding:20px 28px; flex-wrap:wrap; }}
  .country-card {{ background:var(--card); border:1.5px solid var(--border); border-radius:var(--radius);
                   padding:16px 18px; flex:1; min-width:180px; cursor:pointer;
                   transition:box-shadow .2s; box-shadow:0 1px 4px rgba(0,0,0,.06); }}
  .country-card:hover {{ box-shadow:0 4px 14px rgba(0,87,168,.15); border-color:var(--primary); }}
  .card-flag {{ font-size:1.8rem; }}
  .card-label {{ font-size:.82rem; color:var(--subtext); margin-top:2px; }}
  .card-stat {{ font-size:1.7rem; font-weight:700; color:var(--green); margin-top:4px; }}
  .card-target {{ font-size:1rem; color:var(--subtext); font-weight:400; }}
  .progress-bar-wrap {{ background:var(--progress-bg); border-radius:4px; height:8px; margin:8px 0 4px; }}
  .progress-bar {{ background:var(--progress); height:8px; border-radius:4px; transition:width .6s; }}
  .card-pct {{ font-size:.78rem; color:var(--subtext); }}
  .card-sub {{ font-size:.75rem; color:var(--subtext); margin-top:6px; line-height:1.5; }}
  .tabs {{ padding:0 28px; border-bottom:2px solid var(--border); background:var(--card);
           display:flex; flex-wrap:wrap; gap:4px; }}
  .tab-btn {{ padding:10px 18px; font-size:.88rem; border:none; background:transparent;
              cursor:pointer; border-bottom:3px solid transparent; color:var(--subtext);
              font-weight:500; margin-bottom:-2px; transition:all .15s; }}
  .tab-btn.active, .tab-btn:hover {{ color:var(--primary); border-bottom-color:var(--primary); }}
  .tab-content {{ padding:24px 28px; }}
  .tab-content.hidden {{ display:none; }}
  .tab-content h2 {{ font-size:1.15rem; color:var(--primary); margin-bottom:16px; }}
  .tab-content h3 {{ font-size:.95rem; color:var(--subtext); margin:22px 0 10px;
                     text-transform:uppercase; letter-spacing:.5px; font-weight:600; }}
  .stats-row {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:6px; }}
  .stat-box {{ background:var(--card); border:1.5px solid var(--border); border-radius:var(--radius);
               padding:12px 16px; text-align:center; min-width:90px; flex:1; }}
  .stat-box.green  {{ border-color:var(--green);  }}
  .stat-box.blue   {{ border-color:var(--blue);   }}
  .stat-box.orange {{ border-color:var(--orange); }}
  .stat-box.yellow {{ border-color:var(--yellow); }}
  .stat-box.grey   {{ border-color:var(--grey);   }}
  .stat-num {{ font-size:1.5rem; font-weight:700; color:var(--primary); }}
  .stat-box.green  .stat-num {{ color:var(--green);  }}
  .stat-box.blue   .stat-num {{ color:var(--blue);   }}
  .stat-box.orange .stat-num {{ color:var(--orange); }}
  .stat-box.yellow .stat-num {{ color:var(--yellow); }}
  .stat-box.grey   .stat-num {{ color:var(--grey);   }}
  .stat-lbl {{ font-size:.72rem; color:var(--subtext); margin-top:2px;
               text-transform:uppercase; letter-spacing:.4px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card);
           border-radius:var(--radius); overflow:hidden;
           box-shadow:0 1px 4px rgba(0,0,0,.06); font-size:.88rem; }}
  thead {{ background:#eef2fa; }}
  th {{ padding:10px 14px; text-align:left; font-weight:600; color:var(--subtext);
        font-size:.78rem; text-transform:uppercase; letter-spacing:.4px;
        border-bottom:1.5px solid var(--border); }}
  td {{ padding:9px 14px; border-bottom:1px solid var(--border); }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:#f7f9ff; }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .complete {{ font-weight:700; color:var(--green); text-align:right; }}
  .empty {{ text-align:center; color:var(--subtext); font-style:italic; padding:20px; }}
  .pct-cell {{ display:flex; align-items:center; gap:8px; }}
  .mini-bar-wrap {{ flex:1; background:var(--progress-bg); border-radius:3px; height:7px; min-width:60px; }}
  .mini-bar {{ background:var(--progress); height:7px; border-radius:3px; }}
  .pct-cell span {{ font-size:.78rem; color:var(--subtext); white-space:nowrap; }}
  footer {{ text-align:center; padding:16px; font-size:.78rem; color:var(--subtext);
            border-top:1px solid var(--border); background:var(--card); margin-top:20px; }}
  @media (max-width:600px) {{
    .country-cards, .tab-content {{ padding:12px 14px; }}
    .tabs, header {{ padding:14px 14px 10px; }}
  }}
</style>
</head>
<body>
<header>
  <h1>JP RWEE Enumerator Dashboard</h1>
  <p>Joint Programme for Rural Women Economic Empowerment · WFP Pacific</p>
  <div class="meta">Last updated: {gen} &nbsp;·&nbsp; {total} total records pulled from KoboToolbox</div>
</header>
<div class="overall">
  <div>
    <div class="overall-label">Overall Progress (all 4 countries)</div>
    <div class="overall-num">{total_completed} <span style="font-size:1rem;font-weight:400;color:var(--subtext)">/ {target_total} target</span></div>
  </div>
  <div class="overall-bar-wrap"><div class="overall-bar" style="width:{overall_pct}%"></div></div>
  <div style="font-size:1.1rem;font-weight:700;color:var(--primary)">{overall_pct}%</div>
</div>
<div class="country-cards">{country_cards}</div>
<div class="tabs">{country_tabs}</div>
{tab_contents}
<footer>
  Dashboard updated manually · Raw survey data is not published ·
  Built for WFP JP RWEE 2026 Pacific
</footer>
<script>
function showTab(country) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  const content = document.getElementById('content-' + country);
  const btn = document.getElementById('tab-' + country);
  if (content) content.classList.remove('hidden');
  if (btn) btn.classList.add('active');
}}
</script>
</body>
</html>"""
    return html


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    token  = CONFIG["api_token"]
    server = CONFIG["kobo_server"].rstrip("/")
    output = CONFIG["output_path"]

    print("=" * 55)
    print("  JP RWEE 2026 — KoboToolbox Dashboard Generator")
    print("=" * 55)

    uid     = get_form_uid(server, token, CONFIG["form_name"])
    records = fetch_all_submissions(server, token, uid)
    summary = aggregate(records)

    print(f"[4/4] Writing dashboard → {output} ...")
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(generate_html(summary))

    print()
    print("  Summary:")
    for country, c in summary["countries"].items():
        pct = round(c["completed"] / c["target"] * 100) if c["target"] else 0
        print(f"    {COUNTRY_LABELS[country]:20s}  {c['completed']:3d}/{c['target']} completed  ({pct}%)")
    print()
    print(f"  ✅ Dashboard written to: {output}")
    print(f"     Run 'bash push_dashboard.sh' to publish to GitHub Pages.")
    print("=" * 55)


if __name__ == "__main__":
    main()
