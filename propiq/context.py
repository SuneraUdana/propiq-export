"""PropIQ — LLM context builder for Groq chat."""
from __future__ import annotations
from propiq import storage

def build_system_prompt() -> str:
    rows = storage.fetch_scores(limit=200)
    if not rows:
        return (
            "You are PropIQ, a Melbourne property investment analyst. "
            "No pipeline data exists yet — ask the user to POST /api/pipeline/run first."
        )

    # Build suburb summary
    from collections import defaultdict
    suburb_map = defaultdict(list)
    for r in rows:
        suburb_map[r["suburb"]].append(r)

    suburb_lines = []
    for sub, props in sorted(suburb_map.items(),
                             key=lambda x: sum(p["inv_score"] for p in x[1]) / len(x[1]),
                             reverse=True):
        avg = sum(p["inv_score"] for p in props) / len(props)
        prices = [p["sale_price"] for p in props if p.get("sale_price")]
        med = sorted(prices)[len(prices)//2] if prices else 0
        suburb_lines.append(
            f"  {sub} — avg score {avg:.2f}, {len(props)} listings, median ${med:,.0f}"
        )

    # Top 10 properties by inv_score
    top = sorted(rows, key=lambda r: r["inv_score"], reverse=True)[:10]
    prop_lines = [
        f"  {i+1}. {p['address']}, {p['suburb']} | "
        f"score {p['inv_score']:.2f} | ${p.get('sale_price', 0):,.0f} | "
        f"{p.get('bedrooms', '?')}br {p.get('bathrooms', '?')}ba | "
        f"land {p.get('land_size_sqm', 'N/A')}m2"
        for i, p in enumerate(top)
    ]

    return f"""You are PropIQ, an expert Melbourne property investment analyst AI.
You answer questions grounded strictly in the live scored data below.

=== DATA SUMMARY ===
Total scored properties: {len(rows)}
Suburbs covered: {', '.join(suburb_map.keys())}

=== SUBURB RANKINGS ===
{chr(10).join(suburb_lines)}

=== TOP 10 PROPERTIES BY SCORE ===
{chr(10).join(prop_lines)}

=== RULES ===
- Ground every answer in the data above.
- When recommending, always state: score, price, bedrooms/bathrooms, suburb rank.
- If a suburb or address is not in the data, say so explicitly.
- Be concise, direct, and actionable.
"""
