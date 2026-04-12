"""PropIQ — Report generator (CSV + interactive HTML digest)"""
import csv, json
from datetime import date
from pathlib import Path
from propiq.config import REPORT_DIR, TOP_K, SCORE_ALERT_THRESHOLD

REPORT_DIR.mkdir(parents=True, exist_ok=True)

def _fmt(v):
    try: return f"${float(v):,.0f}"
    except: return "—"

def _sc(s):
    if s>=0.90: return "#6daa45"
    if s>=0.70: return "#fdab43"
    return "#dd6974"

def _top(records, n=TOP_K):
    return sorted(records, key=lambda x: x.get("inv_score",0), reverse=True)[:n]

def _write_csv(records, path):
    fields = ["listing_id","suburb","address","sale_price","land_size_sqm",
              "house_type","year_built","bedrooms","bathrooms",
              "material","material_conf","tree_flag","ndvi_score",
              "suburb_income","walk_score","school_rating",
              "yield_proxy","risk_score","liquidity","quality",
              "inv_score","rank_suburb","agent_name","agency","agent_phone"]
    with open(path,"w",newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(records)

def generate_report(records):
    today     = date.today().isoformat()
    csv_path  = REPORT_DIR / f"propiq_report_{today}.csv"
    html_path = REPORT_DIR / f"propiq_report_{today}.html"
    _write_csv(records, csv_path)

    top = _top(records, TOP_K)
    brick_n = sum(1 for r in records if r.get("material")=="brick")
    tree_n  = sum(1 for r in records if r.get("tree_flag"))
    alert_n = sum(1 for r in records if r.get("inv_score",0) > SCORE_ALERT_THRESHOLD)

    from collections import defaultdict
    import numpy as np
    sub_map = defaultdict(list)
    for r in records: sub_map[r["suburb"]].append(r)
    sub_rows = ""
    for sub, recs in sorted(sub_map.items(),
                            key=lambda x: np.mean([r.get("inv_score",0) for r in x[1]]), reverse=True):
        prices  = [r["sale_price"] for r in recs if r.get("sale_price")]
        scores  = [r.get("inv_score",0) for r in recs]
        bricks  = sum(1 for r in recs if r.get("material")=="brick")
        trees   = sum(1 for r in recs if r.get("tree_flag"))
        sc      = float(np.mean(scores))
        sub_rows += f"""<tr><td><b>{sub}</b></td><td>{len(recs)}</td>
          <td>{_fmt(np.median(prices) if prices else 0)}</td>
          <td style="color:{_sc(sc)};font-weight:700">{sc:.4f}</td>
          <td>{round(bricks/len(recs)*100)}%</td>
          <td>{round(trees/len(recs)*100)}%</td></tr>"""

    prop_rows = ""
    for i,r in enumerate(_top(records,TOP_K),1):
        s = r.get("inv_score",0)
        nlp = r.get("nlp_features",{})
        if isinstance(nlp,str):
            try: nlp=json.loads(nlp)
            except: nlp={}
        feats = " · ".join(f for f,k in [("☀ Solar","solar"),("🏊 Pool","pool"),
                           ("🔨 Reno","renovation"),("🏛 Period","period_style")] if nlp.get(k))
        prop_rows += f"""<tr>
          <td style="color:var(--primary);font-weight:700">#{i}</td>
          <td><b>{r.get("suburb","")}</b><br><small>{r.get("address","")}</small></td>
          <td>{_fmt(r.get("sale_price"))}</td>
          <td>{int(r.get("land_size_sqm") or 0):,} m²</td>
          <td>{"🧱 Brick" if r.get("material")=="brick" else "🪵 WB"}</td>
          <td>{"🌳" if r.get("tree_flag") else "—"}</td>
          <td style="font-size:.7rem;color:var(--muted)">{feats or "—"}</td>
          <td><span style="background:{_sc(s)};color:#fff;padding:.15rem .5rem;
              border-radius:9999px;font-size:.75rem;font-weight:700">{s:.4f}</span></td>
          <td style="font-size:.75rem">{r.get("agent_name","")}</td>
        </tr>"""

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PropIQ — Investment Digest {today}</title>
<style>
:root{{--bg:#111110;--surf:#1c1b19;--surf2:#242321;--border:#333230;
  --text:#d4d3d0;--muted:#797876;--primary:#4f98a3;
  --font:'Inter',system-ui,sans-serif}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:var(--font);font-size:14px;padding:2rem}}
.header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:2rem}}
.logo{{font-size:1.2rem;font-weight:700;color:var(--primary)}}
.kpi-row{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.75rem;margin-bottom:2rem}}
.kpi{{background:var(--surf);border:1px solid var(--border);border-radius:.75rem;padding:1rem}}
.kv{{font-size:1.6rem;font-weight:700;color:var(--primary)}}
.kl{{font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}
h2{{font-size:.85rem;font-weight:700;border-left:3px solid var(--primary);
    padding-left:.625rem;margin:1.5rem 0 .75rem;text-transform:uppercase;letter-spacing:.06em}}
.tw{{overflow-x:auto;border-radius:.75rem;border:1px solid var(--border);margin-bottom:1.5rem}}
table{{width:100%;border-collapse:collapse}}
th{{background:var(--surf2);padding:.5rem .75rem;text-align:left;
    font-size:.67rem;text-transform:uppercase;letter-spacing:.07em;
    color:var(--muted);border-bottom:1px solid var(--border)}}
td{{padding:.55rem .75rem;border-bottom:1px solid color-mix(in oklch,var(--border) 60%,transparent);font-size:.8rem}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:var(--surf2)}}
</style></head><body>
<div class="header">
  <div class="logo">🏠 PropIQ — Weekly Digest {today}</div>
  <small style="color:var(--muted)">Melbourne VIC · {len(records)} properties</small>
</div>
<div class="kpi-row">
  <div class="kpi"><div class="kv">{len(records)}</div><div class="kl">Analysed</div></div>
  <div class="kpi"><div class="kv">{alert_n}</div><div class="kl">High-Score Alerts</div></div>
  <div class="kpi"><div class="kv">{brick_n}</div><div class="kl">Brick</div></div>
  <div class="kpi"><div class="kv">{len(records)-brick_n}</div><div class="kl">Weatherboard</div></div>
  <div class="kpi"><div class="kv">{tree_n}</div><div class="kl">Tree Flags</div></div>
</div>
<h2>Top {TOP_K} Investment Opportunities</h2>
<div class="tw"><table><thead><tr>
  <th>#</th><th>Location</th><th>Price</th><th>Land</th>
  <th>Material</th><th>Tree</th><th>Features</th><th>Score</th><th>Agent</th>
</tr></thead><tbody>{prop_rows}</tbody></table></div>
<h2>Suburb Intelligence</h2>
<div class="tw"><table><thead><tr>
  <th>Suburb</th><th>Listings</th><th>Median Price</th>
  <th>Avg Score</th><th>Brick%</th><th>Tree%</th>
</tr></thead><tbody>{sub_rows}</tbody></table></div>
</body></html>"""

    with open(html_path,"w") as f: f.write(html)
    print(f"[reporter] HTML → {html_path}")
    print(f"[reporter] CSV  → {csv_path}")
    return str(html_path)
