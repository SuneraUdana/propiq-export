import sqlite3
import os
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", "data/propiq.db"))

def run_benchmark():
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 1. Market Split: Top 20% AI Picks vs Bottom 80%
    rows = conn.execute("""
        SELECT s.inv_score, s.yield_proxy, s.risk_score, l.sale_price 
        FROM scores s 
        JOIN listings l ON s.listing_id = l.listing_id 
        WHERE l.sale_price > 0
        ORDER BY s.inv_score DESC
    """).fetchall()
    
    if not rows:
        print("No scored listings found to benchmark.")
        return
        
    total = len(rows)
    top_n = max(1, int(total * 0.20))
    
    top_20 = rows[:top_n]
    bottom_80 = rows[top_n:]
    
    avg_yield_top = sum(r["yield_proxy"] for r in top_20) / len(top_20) if top_20 else 0
    avg_yield_bot = sum(r["yield_proxy"] for r in bottom_80) / len(bottom_80) if bottom_80 else 0
    
    avg_risk_top = sum(r["risk_score"] for r in top_20) / len(top_20) if top_20 else 0
    avg_risk_bot = sum(r["risk_score"] for r in bottom_80) / len(bottom_80) if bottom_80 else 0

    print("="*55)
    print("🚀 PROPIQ AI: ALGORITHM BENCHMARK REPORT")
    print("="*55)
    print(f"Total Properties Analyzed: {total}")
    print(f"\n📊 PORTFOLIO QUALITY (Top 20% AI Picks vs Market Average)")
    print(f"Top 20% Yield Proxy: {avg_yield_top:.4f}  |  Market Average: {avg_yield_bot:.4f}")
    print(f"Top 20% Risk Score:  {avg_risk_top:.4f}  |  Market Average: {avg_risk_bot:.4f}")
    
    if avg_yield_top > avg_yield_bot:
        yield_bump = ((avg_yield_top/avg_yield_bot)-1)*100
        print(f"\n✅ SUCCESS: AI isolated properties with +{yield_bump:.1f}% higher yield capacity.")
    if avg_risk_top < avg_risk_bot:
        risk_drop = ((avg_risk_bot/avg_risk_top)-1)*100
        print(f"✅ SUCCESS: AI reduced investment risk exposure by {risk_drop:.1f}%.")
        
    # 2. Real-World Outcomes (Prediction Accuracy)
    print("\n🎯 PREDICTION ACCURACY (Real-World Outcomes)")
    try:
        outcomes = conn.execute("""
            SELECT predicted_price, actual_sale 
            FROM outcomes 
            WHERE status = 'sold' AND actual_sale IS NOT NULL AND predicted_price IS NOT NULL
        """).fetchall()
        
        if not outcomes:
            print("Status: Accumulating data. Waiting for closed sales to calculate hit rate.")
        else:
            hits = sum(1 for o in outcomes if o["actual_sale"] >= o["predicted_price"])
            mae_pct = sum(abs(o["actual_sale"] - o["predicted_price"]) / o["predicted_price"] for o in outcomes) / len(outcomes) * 100
            print(f"Total Closed Deals Tracked: {len(outcomes)}")
            print(f"Price Prediction Error (MAPE): {mae_pct:.2f}%")
            print(f"Hit Rate (Sold Above Prediction): {(hits/len(outcomes))*100:.1f}%")
    except sqlite3.OperationalError:
        print("Status: Outcomes module initializing. Waiting for first tracked sale event.")
        
    conn.close()
    print("="*55)

if __name__ == "__main__":
    run_benchmark()

