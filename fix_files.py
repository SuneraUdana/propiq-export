#!/usr/bin/env python3
"""PropIQ fix_files.py — patches reporter.py, app.py, and writes seed_data.json"""
import json, re, sqlite3
from pathlib import Path

ROOT = Path(__file__).parent

# ── 1. Write reporter.py ──────────────────────────────────────
REPORTER = (
    '"""PropIQ - Report generator"""\n'
    "import csv, json\n"
    "from datetime import date\n"
    "from pathlib import Path\n"
    "from collections import defaultdict\n"
    "import numpy as np\n"
    "from propiq.config import REPORT_DIR, TOP_K, SCORE_ALERT_THRESHOLD\n"
    "\n"
    "REPORT_DIR.mkdir(parents=True, exist_ok=True)\n"
    "\n"
    "def _fmt(v):\n"
    "    try: return f'${float(v):,.0f}'\n"
    "    except: return '—'\n"
    "\n"
    "def _sc(s):\n"
    "    if s >= 0.90: return '#6daa45'\n"
    "    if s >= 0.70: return '#fdab43'\n"
    "    return '#dd6974'\n"
    "\n"
    "def _top(records, n=TOP_K):\n"
    "    return sorted(records, key=lambda x: x.get('inv_score', 0), reverse=True)[:n]\n"
    "\n"
    "def json_report(records, suburb=None, topk=20):\n"
    "    if not records:\n"
    "        return {'top_properties':[],'suburb_rankings':[],'total':0,'suburb_filter':suburb}\n"
    "    sorted_recs = sorted(records, key=lambda r: r.get('inv_score',0), reverse=True)\n"
    "    score_map = defaultdict(list)\n"
    "    price_map = defaultdict(list)\n"
    "    for r in records:\n"
    "        s = r.get('suburb') or 'Unknown'\n"
    "        score_map[s].append(r.get('inv_score') or 0)\n"
    "        p = r.get('sale_price') or 0\n"
    "        if p: price_map[s].append(p)\n"
    "    suburb_rankings = []\n"
    "    for s, sc in score_map.items():\n"
    "        pr = sorted(price_map[s])\n"
    "        suburb_rankings.append({\n"
    "            'suburb':       s,\n"
    "            'avg_score':    round(sum(sc)/len(sc), 4),\n"
    "            'count':        len(sc),\n"
    "            'median_price': pr[len(pr)//2] if pr else 0,\n"
    "        })\n"
    "    suburb_rankings.sort(key=lambda x: x['avg_score'], reverse=True)\n"
    "    return {'top_properties':sorted_recs[:topk],'suburb_rankings':suburb_rankings,\n"
    "            'total':len(records),'suburb_filter':suburb}\n"
    "\n"
    "def generate_report(records):\n"
    "    today = date.today().isoformat()\n"
    "    csv_path = REPORT_DIR / f'propiq_report_{today}.csv'\n"
    "    return str(csv_path), str(csv_path)\n"
    "\n"
    "def market_context(records, suburb=None, top_k=TOP_K):\n"
    "    return json_report(records, suburb=suburb, topk=top_k)\n"
)

reporter_candidates = [
    ROOT / "propiq" / "propiq" / "reporter.py",
    ROOT / "propiq" / "reporter.py",
]
reporter_path = next((p for p in reporter_candidates if p.exists()), reporter_candidates[0])
reporter_path.parent.mkdir(parents=True, exist_ok=True)
reporter_path.write_text(REPORTER)
print(f"[1/4] reporter.py -> {reporter_path}")

# ── 2. Patch _do_seed in app.py ───────────────────────────────
NEW_DO_SEED = "\n".join([
    "def _do_seed(seed_path: Path) -> int:",
    "    raw = json.loads(seed_path.read_text())",
    "    records = raw if isinstance(raw, list) else raw.get(",
    "        'properties', raw.get('listings', raw.get('top_properties', [])))",
    "    from propiq.storage import upsert_listings, upsert_enrichments, upsert_scores",
    "    listings, enrichments, scores = [], [], []",
    "    for r in records:",
    "        listings.append({",
    "            'listing_id':    r.get('listing_id'),",
    "            'suburb':        r.get('suburb'),",
    "            'address':       r.get('address'),",
    "            'sale_price':    r.get('sale_price'),",
    "            'land_size_sqm': r.get('land_size_sqm'),",
    "            'house_type':    r.get('house_type'),",
    "            'year_built':    r.get('year_built'),",
    "            'bedrooms':      r.get('bedrooms'),",
    "            'bathrooms':     r.get('bathrooms'),",
    "            'image_url':     r.get('image_url'),",
    "        })",
    "        enrichments.append({",
    "            'listing_id':    r.get('listing_id'),",
    "            'material':      r.get('material'),",
    "            'walk_score':    r.get('walk_score'),",
    "            'school_rating': r.get('school_rating'),",
    "            'nlp_features':  r.get('nlp_features') if isinstance(r.get('nlp_features'), str)",
    "                             else json.dumps(r.get('nlp_features') or {}),",
    "        })",
    "        scores.append({",
    "            'listing_id':  r.get('listing_id'),",
    "            'inv_score':   r.get('inv_score'),",
    "            'yield_proxy': r.get('yield_proxy'),",
    "            'risk_score':  r.get('risk_score'),",
    "            'liquidity':   r.get('liquidity'),",
    "            'quality':     r.get('quality'),",
    "            'rank_suburb': r.get('rank_suburb'),",
    "        })",
    "    upsert_listings(listings)",
    "    upsert_enrichments(enrichments)",
    "    upsert_scores(scores)",
    "    print(f'[seed] {len(scores)} records seeded into 3 tables')",
    "    return len(scores)",
    "",
])

app_path = ROOT / "app.py"
if app_path.exists():
    content = app_path.read_text()
    patched = re.sub(
        r"def _do_seed\(seed_path: Path\).*?(?=\n# ── Static|\n_static = |\napp\.mount)",
        NEW_DO_SEED,
        content, flags=re.DOTALL
    )
    if patched == content:
        print("[2/4] WARNING: _do_seed pattern not matched — appending")
        patched = content.rstrip() + "\n\n" + NEW_DO_SEED
    app_path.write_text(patched)
    print(f"[2/4] app.py patched -> {app_path}")
else:
    print("[2/4] ERROR: app.py not found")

# ── 3. Export seed_data.json from local DB ────────────────────
db_candidates = [
    ROOT / "propiq" / "data" / "propiq.db",
    ROOT / "data" / "propiq.db",
]
db_path = next((p for p in db_candidates if p.exists()), None)
seed_path = ROOT / "seed_data.json"
if db_path:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT l.listing_id, l.suburb, l.address, l.sale_price,
               l.land_size_sqm, l.house_type, l.year_built,
               l.bedrooms, l.bathrooms, l.image_url,
               e.material, e.walk_score, e.school_rating, e.nlp_features,
               s.inv_score, s.yield_proxy, s.risk_score,
               s.liquidity, s.quality, s.rank_suburb, s.scored_at
        FROM listings l
        JOIN enrichments e ON l.listing_id = e.listing_id
        JOIN scores s ON l.listing_id = s.listing_id
        ORDER BY s.inv_score DESC
    """).fetchall()
    conn.close()
    records = [dict(r) for r in rows]
    seed_path.write_text(json.dumps(records, indent=2, default=str))
    print(f"[3/4] seed_data.json -> {len(records)} records")
else:
    print("[3/4] DB not found — seed_data.json skipped (place manually)")

# ── 4. .gitignore ─────────────────────────────────────────────
gi_path = ROOT / ".gitignore"
gi = gi_path.read_text() if gi_path.exists() else ""
lines = [l for l in gi.splitlines() if "seed_data.json" not in l and l != "data/"]
lines += ["data/", "!seed_data.json"]
gi_path.write_text("\n".join(lines) + "\n")
print("[4/4] .gitignore updated")

print("\nAll done. Now run: bash deploy.sh")
