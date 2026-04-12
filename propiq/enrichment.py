"""
PropIQ — Enrichment Agent
Layers three enrichment models over raw listings:
  1. CNN material classifier  (brick vs weatherboard)
  2. NDVI satellite tree flag (giant canopy detection)
  3. spaCy NLP feature parser (listing description)
  4. ABS Census join          (suburb-level socioeconomics)
"""
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

def _classify_material(suburb: str, year_built: int):
    """
    Simulates ResNet-18 facade classification.
    Swap with real model:
        model = torchvision.models.resnet18(pretrained=False)
        model.load_state_dict(torch.load('models/material_clf.pth'))
    """
    base_prob = BRICK_BIAS.get(suburb, 0.55)
    if year_built < 1940: base_prob += 0.15
    if year_built > 1980: base_prob -= 0.10
    base_prob = max(0.1, min(0.95, base_prob))
    confidence = abs(random.gauss(base_prob, 0.08))
    confidence = max(0.50, min(0.99, confidence))
    material = "brick" if confidence > BRICK_THRESHOLD else "weatherboard"
    return material, round(confidence, 4)

# ── 2. NDVI Tree Detector (mock / swap in satellite API) ──────
def _detect_tree(suburb: str, land_sqm: float):
    """
    Simulates NDVI from Google Maps satellite tile + OpenCV contour detection.
    Real implementation:
        tile = fetch_satellite_tile(lat, lon, zoom=18)
        ndvi = compute_ndvi(tile)   # (NIR-Red)/(NIR+Red)
        tree_flag = ndvi > NDVI_TREE_THRESHOLD
    """
    base_ndvi = 0.35
    if (land_sqm or 0) > 500: base_ndvi += 0.12
    if suburb in ["Hawthorn","South Yarra","Fitzroy"]: base_ndvi += 0.08
    ndvi = round(max(0.0, min(1.0, random.gauss(base_ndvi, 0.12))), 4)
    tree_flag = 1 if ndvi > NDVI_TREE_THRESHOLD else 0
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

def _parse_nlp(description: str) -> dict:
    """
    Rule-based NLP. Swap with spaCy model:
        nlp = spacy.load('en_core_web_sm')
        doc = nlp(description)
    """
    desc = (description or "").lower()
    return {k: bool(re.search(v, desc)) for k, v in NLP_PATTERNS.items()}

# ── 4. ABS Census / Socioeconomic Join ───────────────────────
def _suburb_context(suburb: str) -> dict:
    return {
        "suburb_income": SUBURB_INCOMES.get(suburb, 85_000),
        "walk_score":    SUBURB_WALK_SCORES.get(suburb, 75),
        "school_rating": SUBURB_SCHOOL_RTGS.get(suburb, 7.0),
    }

# ── Public API ────────────────────────────────────────────────
def enrich_record(r: dict) -> dict:
    material, conf = _classify_material(r["suburb"], r.get("year_built", 1980))
    tree_flag, ndvi = _detect_tree(r["suburb"], r.get("land_size_sqm", 300))
    nlp = _parse_nlp(r.get("description", ""))
    ctx = _suburb_context(r["suburb"])
    return {
        "listing_id":    r.get("listing_id", r.get("address","") + "_" + r.get("suburb","")),
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
        enriched.append({**r, **enrich_record(r)})
        if verbose and i % 50 == 0:
            print(f"  [enrichment] {i}/{len(records)} enriched")
    upsert_enrichments(enriched)
    print(f"[enrichment] Completed {len(enriched)} records")
    return enriched
