"""PropIQ — Report generator"""
import csv, json
from datetime import date
from pathlib import Path
from collections import defaultdict
import numpy as np

try:
    from propiq.config import REPORT_DIR, TOP_K, SCORE_ALERT_THRESHOLD
except Exception:
    REPORT_DIR = Path("reports")
    TOP_K = 20
    SCORE_ALERT_THRESHOLD = 0.85

REPORT_DIR.mkdir(parents=True, exist_ok=True)

def json_report(records: list, suburb=None, topk=20) -> dict:
    if not records:
        return {"top_properties": [], "suburb_rankings": [], "total": 0, "suburb_filter": suburb}

    sorted_recs = sorted(records, key=lambda r: r.get("inv_score", 0), reverse=True)
    top = sorted_recs[:topk]

    score_map: dict = defaultdict(list)
    price_map: dict = defaultdict(list)
    for r in records:
        s = r.get("suburb") or "Unknown"
        score_map[s].append(r.get("inv_score") or 0)
        p = r.get("sale_price") or 0
        if p:
            price_map[s].append(p)

    suburb_rankings = []
    for s, scores in score_map.items():
        prices = sorted(price_map[s])
        median_price = prices[len(prices) // 2] if prices else 0
        avg = round(sum(scores) / len(scores), 4)
        suburb_rankings.append({
            "suburb": s,
            "avg_inv_score": avg,
            "listing_count": len(scores),
            "avg_score": avg,
            "count": len(scores),
            "median_price": median_price,
        })

    suburb_rankings.sort(key=lambda x: x.get("avg_inv_score", 0), reverse=True)

    return {
        "top_properties": top,
        "suburb_rankings": suburb_rankings,
        "total": len(records),
        "suburb_filter": suburb,
    }
