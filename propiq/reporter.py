"""PropIQ - Report generator"""
import csv, json
from datetime import date
from pathlib import Path
from collections import defaultdict
import numpy as np
from propiq.config import REPORT_DIR, TOP_K, SCORE_ALERT_THRESHOLD

REPORT_DIR.mkdir(parents=True, exist_ok=True)

def _fmt(v):
    try: return f'${float(v):,.0f}'
    except: return '—'

def _sc(s):
    if s >= 0.90: return '#6daa45'
    if s >= 0.70: return '#fdab43'
    return '#dd6974'

def _top(records, n=TOP_K):
    return sorted(records, key=lambda x: x.get('inv_score', 0), reverse=True)[:n]

def json_report(records, suburb=None, topk=20):
    if not records:
        return {'top_properties':[],'suburb_rankings':[],'total':0,'suburb_filter':suburb}
    sorted_recs = sorted(records, key=lambda r: r.get('inv_score',0), reverse=True)
    score_map = defaultdict(list)
    price_map = defaultdict(list)
    for r in records:
        s = r.get('suburb') or 'Unknown'
        score_map[s].append(r.get('inv_score') or 0)
        p = r.get('sale_price') or 0
        if p: price_map[s].append(p)
    suburb_rankings = []
    for s, sc in score_map.items():
        pr = sorted(price_map[s])
        suburb_rankings.append({
            'suburb':       s,
            'avg_score':    round(sum(sc)/len(sc), 4),
            'count':        len(sc),
            'median_price': pr[len(pr)//2] if pr else 0,
        })
    suburb_rankings.sort(key=lambda x: x['avg_score'], reverse=True)
    return {'top_properties':sorted_recs[:topk],'suburb_rankings':suburb_rankings,
            'total':len(records),'suburb_filter':suburb}

def generate_report(records):
    today = date.today().isoformat()
    csv_path = REPORT_DIR / f'propiq_report_{today}.csv'
    return str(csv_path), str(csv_path)

def market_context(records, suburb=None, top_k=TOP_K):
    return json_report(records, suburb=suburb, topk=top_k)
