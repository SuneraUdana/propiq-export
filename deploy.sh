#!/bin/bash
set -e
echo "Step 1/3: Fixing files..."
python3 fix_files.py

echo ""
echo "Step 2/3: Staging..."
git add app.py seed_data.json .gitignore
git add propiq/reporter.py 2>/dev/null || git add propiq/propiq/reporter.py 2>/dev/null || true

echo ""
echo "Step 3/3: Commit + Push..."
git commit -m "fix: 3-table seed + reporter keys aligned with dashboard"
git push origin main

echo ""
echo "Done! Railway will auto-deploy. Dashboard populates in ~60s."
