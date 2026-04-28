import re
with open("app.py", "r") as f:
    content = f.read()

correct_seed = """def _do_seed(seed_path: Path) -> int:
    raw = json.loads(seed_path.read_text())
    records = raw if isinstance(raw, list) else raw.get(
        "properties", raw.get("listings", raw.get("top_properties", [])))
    
    from propiq.storage import upsert_listings, upsert_enrichments, upsert_scores
    listings, enrichments, scores = [], [], []
    
    for r in records:
        listings.append({
            "listing_id": r.get("listing_id"), "suburb": r.get("suburb"),
            "address": r.get("address"), "sale_price": r.get("sale_price"),
            "land_size_sqm": r.get("land_size_sqm"), "house_type": r.get("house_type"),
            "year_built": r.get("year_built"), "bedrooms": r.get("bedrooms"),
            "bathrooms": r.get("bathrooms"), "image_url": r.get("image_url"),
        })
        enrichments.append({
            "listing_id": r.get("listing_id"), "material": r.get("material"),
            "walk_score": r.get("walk_score"), "school_rating": r.get("school_rating"),
            "nlp_features": r.get("nlp_features", "{}") if isinstance(r.get("nlp_features"), str) else json.dumps(r.get("nlp_features") or {})
        })
        scores.append({
            "listing_id": r.get("listing_id"), "inv_score": r.get("inv_score"),
            "yield_proxy": r.get("yield_proxy"), "risk_score": r.get("risk_score"),
            "liquidity": r.get("liquidity"), "quality": r.get("quality"),
            "rank_suburb": r.get("rank_suburb")
        })
        
    upsert_listings(listings)
    upsert_enrichments(enrichments)
    upsert_scores(scores)
    return len(scores)"""

# Replace the old _do_seed function
content = re.sub(r'def _do_seed\(.*?return inserted', correct_seed, content, flags=re.DOTALL)
with open("app.py", "w") as f:
    f.write(content)
