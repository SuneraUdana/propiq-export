"""PropIQ — Differential Evolution Optimiser & Scoring Engine"""
import json
from collections import defaultdict
from datetime import date

import numpy as np
from scipy.optimize import differential_evolution

from propiq.config import DE_POPSIZE, DE_MAXITER, DE_TOL, DE_SEED, TREE_RISK_PENALTY
from propiq.storage import upsert_scores

_CURRENT_YEAR = date.today().year

def _compute_features(r: dict, suburb_median: float) -> dict:
    price  = r.get("sale_price", suburb_median) or suburb_median
    land   = max(r.get("land_size_sqm") or 200, 1)   # already safe from previous fix
    year   = r.get("year_built", 1980) or 1980
    walk   = r.get("walk_score", 75) or 75
    school = r.get("school_rating", 7.0) or 7.0
    mat    = r.get("material", "weatherboard")
    tree   = r.get("tree_flag", 0)

    nlp_raw = r.get("nlp_features", {})
    if isinstance(nlp_raw, str):
        try:
            nlp_raw = json.loads(nlp_raw)
        except (json.JSONDecodeError, TypeError):   # FIX: was bare except:
            nlp_raw = {}

    yield_proxy   = max(0, (suburb_median - price) / suburb_median)
    age_risk      = max(0, (_CURRENT_YEAR - year) / 130)
    price_risk    = min(1, price / 3_000_000)
    neg_nlp       = float(
        bool(nlp_raw.get("needs_work", 0)) or bool(nlp_raw.get("sentiment_neg", 0))
    )
    tree_risk     = TREE_RISK_PENALTY if tree else 0
    risk_score    = age_risk * 0.4 + price_risk * 0.3 + neg_nlp * 0.2 + tree_risk * 0.1

    liquidity     = walk / 100.0
    brick_bonus   = 0.10 if mat == "brick" else 0.0
    nlp_bonus     = sum(0.02 for k in ["solar", "pool", "renovation"] if nlp_raw.get(k))
    sentiment_pen = 0.05 if nlp_raw.get("sentiment_neg") else 0.0
    quality       = min(1.0, school / 10.0 * 0.5 + brick_bonus + nlp_bonus - sentiment_pen + 0.3)

    return {
        "yield_proxy": yield_proxy,
        "risk_score":  risk_score,
        "liquidity":   liquidity,
        "quality":     quality,
    }
def _fitness(weights, all_feats):
    w0, w1, w2, w3 = weights
    scores   = [w0*f["yield_proxy"] - w1*f["risk_score"]
                + w2*f["liquidity"] + w3*f["quality"] for f in all_feats]
    variance = float(np.var(scores))
    return -variance


def optimise_weights(all_feats: list[dict], verbose: bool = False) -> np.ndarray:
    # FIX: reset mutable globals each call — stale state from a previous run
    #      would corrupt convergence logging across multiple pipeline runs
    last_w = [0.25, 0.25, 0.25, 0.25]
    iter_n = [0]

    def _cb(xk, convergence):
        last_w[:] = list(xk)
        iter_n[0] += 1
        if iter_n[0] % 5 == 0:
            print(f"  [DE] convergence={convergence:.4f}  "
                  f"w=[{xk[0]:.3f},{xk[1]:.3f},{xk[2]:.3f},{xk[3]:.3f}]")

    bounds = [(0, 1), (0, 0.5), (0, 1), (0, 1)]
    result = differential_evolution(
        _fitness, bounds, args=(all_feats,),
        popsize=DE_POPSIZE, maxiter=DE_MAXITER, tol=DE_TOL,
        seed=DE_SEED, callback=_cb if verbose else None,
        polish=True, workers=1,
    )
    return result.x


def score_and_rank(
    records: list[dict],
    weights: np.ndarray | None = None,
    verbose: bool = False,
) -> list[dict]:

    # ── Build per-suburb price medians ────────────────────────────────────────
    suburb_prices: dict[str, list] = defaultdict(list)
    for r in records:
        suburb = r.get("suburb") or "Unknown"          # FIX: was r["suburb"] → KeyError
        if r.get("sale_price"):
            suburb_prices[suburb].append(r["sale_price"])
    suburb_med = {s: float(np.median(v)) for s, v in suburb_prices.items()}

    # ── Optimise weights if not supplied ─────────────────────────────────────
    if weights is None:
        all_feats = [
            _compute_features(r, suburb_med.get(r.get("suburb") or "Unknown", 1_000_000))
            for r in records
        ]
        weights = optimise_weights(all_feats, verbose=verbose)

    w0, w1, w2, w3 = weights
    wj = weights.tolist()

    # ── Score every record ───────────────────────────────────────────────────
    suburb_scores: dict[str, list] = defaultdict(list)
    scored: list[dict] = []
    for r in records:
        suburb = r.get("suburb") or "Unknown"          # FIX: was r["suburb"] → KeyError
        f = _compute_features(r, suburb_med.get(suburb, 1_000_000))
        score = w0*f["yield_proxy"] - w1*f["risk_score"] + w2*f["liquidity"] + w3*f["quality"]
        row = {**r, **f, "inv_score": round(float(score), 6), "weights_json": wj, "rank_suburb": 0}
        scored.append(row)
        suburb_scores[suburb].append(row)              # FIX: was r["suburb"] → KeyError

    # ── Rank within suburb ───────────────────────────────────────────────────
    for sub_recs in suburb_scores.values():
        for rank, rec in enumerate(
            sorted(sub_recs, key=lambda x: x["inv_score"], reverse=True), 1
        ):
            rec["rank_suburb"] = rank

    scored.sort(key=lambda x: x["inv_score"], reverse=True)
    upsert_scores(scored)
    return scored
