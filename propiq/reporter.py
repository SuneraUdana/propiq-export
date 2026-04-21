"""PropIQ — Report generator (CSV + interactive HTML digest)"""
import csv, json
from datetime import date
from pathlib import Path
from collections import defaultdict
import numpy as np
from propiq.config import REPORT_DIR, TOP_K, SCORE_ALERT_THRESHOLD

REPORT_DIR.mkdir(parents=True, exist_ok=True)

def _fmt(v):
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return "—"
def _sc(s):
    if s >= 0.90:
        return "#6daa45"
    if s >= 0.70:
        return "#fdab43"
    return "#dd6974"
def _top(records, n=TOP_K):
    return sorted(records, key=lambda x: x.get("invscore", 0), reverse=True)[:n]

def _write_csv(records, path):
    fields = [
        "listingid", "suburb", "address", "saleprice", "landsizesqm",
        "housetype", "yearbuilt", "bedrooms", "bathrooms",
        "material", "walkscore", "schoolrating",
        "yieldproxy", "riskscore", "liquidity", "quality",
        "invscore", "ranksuburb"
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)

def generate_report(records: list[dict]) -> tuple[str, str]:
    today = date.today().isoformat()
    csv_path = REPORT_DIR / f"propiq_report_{today}.csv"
    html_path = REPORT_DIR / f"propiq_report_{today}.html"



    _write_csv(records, csv_path)



    top = _top(records, TOP_K)
    brick_n = sum(1 for r in records if r.get("material") == "brick")
    tree_n = sum(1 for r in records if r.get("tree_flag"))
    alert_n = sum(1 for r in records if r.get("invscore", 0) > SCORE_ALERT_THRESHOLD)



    sub_map = defaultdict(list)
    for r in records:
        suburb = r.get("suburb") or "Unknown"
        sub_map[suburb].append(r)



    sub_rows = ""
    for sub, recs in sorted(
        sub_map.items(),
        key=lambda x: np.mean([r.get("invscore", 0) for r in x[1]]),
        reverse=True
    ):
        prices = [r.get("saleprice") for r in recs if r.get("saleprice") is not None]
        # Calculate averages/medians
        avg_price = np.mean(prices) if prices else None
        avg_score = float(np.mean([r.get("inv_score", 0) for r in recs]))
        
        # Calculate percentages for the last two columns
        bricks = sum(1 for r in recs if r.get("material") == "brick")
        trees = sum(1 for r in recs if r.get("tree_flag"))
        
        # Generate exactly 6 table cells to match the 6 table headers
        sub_rows += f"""<tr>
          <td><b>{sub}</b></td>
          <td>{len(recs)}</td>
          <td>{_fmt(avg_price)}</td>
          <td style="color:{_sc(avg_score)};font-weight:700">{avg_score:.2f}</td>
          <td>{round(bricks/len(recs)*100)}%</td>
          <td>{round(trees/len(recs)*100)}%</td>
        </tr>"""
