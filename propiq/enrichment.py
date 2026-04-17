import re, random, json
from propiq.config import (BRICK_THRESHOLD, NDVI_TREE_THRESHOLD,
                            SUBURB_INCOMES, SUBURB_WALK_SCORES,
                            SUBURB_SCHOOL_RTGS)
from propiq.storage import upsert_enrichments


# ── 1. CNN Material Classifier (mock / swap in ResNet-18) ─────
BRICK_BIAS = {
    "Fitzroy":0.72, "Richmond":0.65, "Hawthorn":0.80, "Brunswick":0.55,
    "South Yarra":0.60, "Collingwood":0.68, "St Kilda":0.58,
    "Prahran":0.62, "Northcote":0.59, "Footscray":0.50,
}
def _classify_material(suburb: str, year_built: int | None):
    """
    Simulates ResNet-18 facade classification.
    Swap with real model:
        model = torchvision.models.resnet18(pretrained=False)
        model.load_state_dict(torch.load('models/material_clf.pth'))
    """
    year_built = year_built or 1980                     # FIX: guard None
    base_prob  = BRICK_BIAS.get(suburb or "", 0.55)
    if year_built < 1940: base_prob += 0.15
    if year_built > 1980: base_prob -= 0.10
    base_prob  = max(0.10, min(0.95, base_prob))
    raw        = abs(random.gauss(base_prob, 0.08))
    confidence = max(0.50, min(0.99, raw))              # FIX: clamp after abs()
    material   = "brick" if confidence > BRICK_THRESHOLD else "weatherboard"
    return material, round(confidence, 4)

# ── 2. NDVI Tree Detector (mock / swap in satellite API) ──────
def _detect_tree(suburb: str, land_sqm: float | None):
    """
    Simulates NDVI from Google Maps satellite tile + OpenCV contour detection.
    Real implementation:
        tile = fetch_satellite_tile(lat, lon, zoom=18)
        ndvi = compute_ndvi(tile)   # (NIR-Red)/(NIR+Red)
        tree_flag = ndvi > NDVI_TREE_THRESHOLD
    """
    safe_land  = land_sqm or 0                         # FIX: None → 0 before compare
    base_ndvi  = 0.35
    if safe_land > 500: base_ndvi += 0.10
    if suburb in {"Hawthorn", "South Yarra", "Fitzroy"}: base_ndvi += 0.08
    ndvi       = round(max(0.0, min(1.0, random.gauss(base_ndvi, 0.12))), 4)
    tree_flag  = 1 if ndvi > NDVI_TREE_THRESHOLD else 0
    return tree_flag, ndvi
# ── 3. NLP Feature Parser ─────────────────────────────────────
NLP_PATTERNS = {
    "solar":        r"\b(solar|pv panel|photovoltaic)\b",
    "pool":         r"\b(pool|spa|plunge)\b",
    "renovation":   r"\b(renovat|updated|modern|refurb|new kitchen|new bathroom)\b",
    "period_style": r"\b(period|heritage|edwardian|victorian|federation|art.?deco)\b",
    "garage":       r"\b(garage|carport|car space|parking)\b",
    "needs_work":   r"\b(sold as.?is|deceased estate|cosmetic|needs work|tlc)\b",
    "sentiment_neg":r"\b(powerline|busy road|noise|flood|easement|dispute)\b",
}
def _parse_nlp(description: str | None) -> dict:
    """
    Rule-based NLP. Swap with spaCy model:
        nlp = spacy.load('en_core_web_sm')
        doc = nlp(description)
    """
    desc = (description or "").lower()                 # FIX: guard None
    return {k: bool(re.search(v, desc)) for k, v in NLP_PATTERNS.items()}


# ── 4. ABS Census / Socioeconomic Join ───────────────────────
def _suburb_context(suburb: str | None) -> dict:
    safe_suburb = suburb or ""
    return {
        "suburb_income": SUBURB_INCOMES.get(safe_suburb, 85_000),
        "walk_score":    SUBURB_WALK_SCORES.get(safe_suburb, 75),
        "school_rating": SUBURB_SCHOOL_RTGS.get(safe_suburb, 7.0),
    }
# ── Public API ────────────────────────────────────────────────
def enrich_record(r: dict) -> dict:
    suburb    = r.get("suburb", "")                    # FIX: never r["suburb"]
    year      = r.get("year_built")                    # let classifier handle None
    land      = r.get("land_size_sqm")                 # let detector handle None
    desc      = r.get("description", "")
    # Derive a stable listing_id from address + suburb if missing
    listing_id = (
        r.get("listing_id")
        or f"{r.get('address', 'unknown')}_{suburb}".replace(" ", "_").lower()
    )

    material, conf         = _classify_material(suburb, year)
    tree_flag, ndvi        = _detect_tree(suburb, land)
    nlp                    = _parse_nlp(desc)
    ctx                    = _suburb_context(suburb)

    return {
        "listing_id":    listing_id,
        "material":      material,
        "material_conf": conf,
        "tree_flag":     tree_flag,
        "ndvi_score":    ndvi,
        "nlp_features":  json.dumps(nlp),
        **ctx,
    }

def enrich_batch(records: list[dict], verbose: bool = False) -> list[dict]:
    enriched = []
    for i, r in enumerate(records, 1):
        try:
            enriched.append({**r, **enrich_record(r)})   # FIX: per-record try/except
        except Exception as exc:
            print(f"  [enrichment] WARNING — skipped record {i}: {exc}")
            enriched.append(r)                            # pass through raw if enrichment fails
        if verbose and i % 50 == 0:
            print(f"  [enrichment] {i}/{len(records)} enriched")
    upsert_enrichments(enriched)
    print(f"[enrichment] Completed {len(enriched)} records")
    return enriched 