"""PropIQ — build_system_prompt with optional metadata return."""
from __future__ import annotations
from propiq.storage import fetch_scores, fetch_suburb_summary


def build_system_prompt(return_meta: bool = False):
    records  = fetch_scores(limit=10)
    suburbs  = fetch_suburb_summary()

    top_ids      = [r["listing_id"] for r in records]
    suburbs_list = [s["suburb"] for s in suburbs]

    lines = [
        "You are PropIQ, an expert property investment analyst.",
        "You have access to real-time scored property data. Use it to give grounded, specific advice.",
        "",
        "## Top 10 Scored Properties Right Now",
    ]
    for i, r in enumerate(records, 1):
        lines.append(
            f"{i}. {r.get('address','?')} | {r.get('suburb','?')} "
            f"| score {r.get('inv_score',0):.2f} "
            f"| ${r.get('sale_price',0):,.0f} "
            f"| {r.get('bedrooms','?')}br {r.get('bathrooms','?')}ba"
        )

    lines += ["", "## Suburb Averages"]
    for s in suburbs:
        lines.append(
            f"- {s['suburb']}: avg score {s['avg_score']:.2f}, "
            f"median ${s.get('median_price',0):,.0f}, "
            f"rank {suburbs.index(s)+1}"
        )

    lines += [
        "",
        "Be concise. Always cite property addresses and scores.",
        "If data is missing for a suburb, say so clearly.",
    ]

    prompt = "\n".join(lines)
    if return_meta:
        return prompt, suburbs_list, top_ids
    return prompt