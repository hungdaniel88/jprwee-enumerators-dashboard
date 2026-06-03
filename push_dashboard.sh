#!/bin/bash
# ─────────────────────────────────────────────────────
# JP RWEE 2026 — Manual Dashboard Update Script
# Run this whenever you want to publish a fresh update.
#
# Usage:
#   bash push_dashboard.sh
# ─────────────────────────────────────────────────────

set -e  # stop on any error

echo "========================================"
echo "  JP RWEE Dashboard — Manual Update"
echo "========================================"

# Step 1: Pull latest data from Kobo and regenerate HTML
echo ""
echo "[1/2] Fetching data and generating dashboard..."
python fetch_kobo_data.py

# Step 2: Commit and push only the dashboard HTML to GitHub
echo ""
echo "[2/2] Publishing to GitHub Pages..."
git add docs/index.html
git diff --cached --quiet && echo "  No changes since last update." && exit 0
git commit -m "Dashboard update $(date -u '+%Y-%m-%d %H:%M UTC')"
git push

echo ""
echo "  ✅ Done! Dashboard is live at your GitHub Pages URL."
echo "========================================"
