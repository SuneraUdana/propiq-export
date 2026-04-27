#!/usr/bin/env python3
"""Run from project root: python3 fix_deploy.py"""
import ast, json, subprocess
from pathlib import Path

ROOT = Path(__file__).parent

# 1. reporter.py
rp = ROOT / "propiq" / "reporter.py"
src = rp.read_text() if rp.exists() else ""
if "avg_inv_score" in src and "listing_count" in src:
    print("OK reporter.py has correct keys")
else:
    print("FAIL reporter.py missing avg_inv_score — copy downloaded version to propiq/reporter.py")

# 2. Dockerfile
df = (ROOT / "Dockerfile").read_text() if (ROOT / "Dockerfile").exists() else ""
if 'sh", "-c"' in df:
    print("OK Dockerfile uses sh -c")
else:
    # Auto-fix CMD line
    lines = [('CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]'
              if l.strip().startswith("CMD") else l) for l in df.splitlines()]
    (ROOT / "Dockerfile").write_text("\n".join(lines) + "\n")
    print("FIXED Dockerfile CMD auto-patched")

# 3. app.py syntax
ap = ROOT / "app.py"
try:
    ast.parse(ap.read_text())
    print("OK app.py syntax valid")
except SyntaxError as e:
    print(f"FAIL app.py SyntaxError line {e.lineno}: {e.msg}")

# 4. seed_data.json
sp = ROOT / "seed_data.json"
if sp.exists():
    d = json.loads(sp.read_text())
    recs = d if isinstance(d,list) else d.get("properties",d.get("listings",d.get("top_properties",[])))
    print(f"OK seed_data.json has {len(recs)} records")
else:
    print("WARN seed_data.json not found")

print()
print("Now run:")
print("  git add -A")
print('  git commit -m "fix: reporter keys + Dockerfile PORT"')
print("  git push origin main")
