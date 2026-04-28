from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
import os, sqlite3, json
from pathlib import Path
from groq import Groq

from propiq.storage import (
    init_db, DB_PATH,
    fetch_scores, fetch_top_agents,
    log_pipeline_start, log_pipeline_finish,
    log_conversation, fetch_pipeline_runs, fetch_conversations,
    record_outcome, update_outcome, withdraw_outcome,
    fetch_outcomes, fetch_outcome_stats
)
from propiq.reporter import json_report
from propiq.agent import run_pipeline
from propiq.context import build_system_prompt

# ── Seed helper ───────────────────────────────────────────────────────────────
def _do_seed(seed_path: Path) -> int:
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
        
        nlp = r.get("nlp_features", "{}")
        if not isinstance(nlp, str): nlp = json.dumps(nlp or {})
            
        enrichments.append({
            "listing_id": r.get("listing_id"), "material": r.get("material"),
            "walk_score": r.get("walk_score"), "school_rating": r.get("school_rating"),
            "nlp_features": nlp
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
    return len(scores)

# ── Lifespan (startup) ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        count = sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM scores").fetchone()[0]
        if count == 0:
            seed_path = Path(__file__).parent / "seed_data.json"
            if seed_path.exists():
                _do_seed(seed_path)
                print("[startup] Auto-seeded from seed_data.json ✓")
    except Exception as e:
        print(f"[startup] Auto-seed skipped: {e}")
    yield

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="PropIQ API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
_groq = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

class PipelineRequest(BaseModel): suburbs: list[str]
class PipelineResponse(BaseModel): status: str; suburbs: list[str]; message: str
class ChatRequest(BaseModel): message: str; model: str = "llama-3.3-70b-versatile"; history: list[dict] = []

_static = Path("static")
if _static.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
def dashboard(): return FileResponse("static/index.html")

@app.get("/health")
def health(): return {"status": "ok", "version": "0.2.0"}

@app.post("/api/seed")
def seed():
    seed_path = Path(__file__).parent / "seed_data.json"
    if not seed_path.exists(): raise HTTPException(status_code=404, detail="Not found")
    return {"status": "ok", "seeded": _do_seed(seed_path)}

@app.get("/api/market-context")
def market_context(suburb: str | None = Query(None), limit: int = Query(20, ge=1, le=100)):
    records = fetch_scores(suburb=suburb, limit=limit)
    agents  = fetch_top_agents(suburb=suburb, limit=5)
    report  = json_report(records, suburb=suburb, topk=limit)
    return {**report, "agents": agents}

@app.get("/api/market-context/history")
def market_history(days: int = Query(30, ge=1, le=365)):
    from propiq.storage import fetch_suburb_history
    return {"history": fetch_suburb_history(days=days)}

_running: set[str] = set()

@app.post("/api/pipeline/run", response_model=PipelineResponse)
def pipeline_run(body: PipelineRequest, background_tasks: BackgroundTasks):
    for s in body.suburbs: _running.add(s)
    def run_and_cleanup(suburbs: list[str]):
        try: run_pipeline(suburbs)
        except Exception: pass
        finally:
            for s in suburbs: _running.discard(s)
    background_tasks.add_task(run_and_cleanup, body.suburbs)
    return PipelineResponse(status="accepted", suburbs=body.suburbs, message="Started")

@app.get("/api/pipeline/status")
def pipeline_status(): return {"running": list(_running), "idle": len(_running) == 0}

@app.post("/api/chat")
def chat(payload: ChatRequest):
    if not _groq: raise HTTPException(status_code=500, detail="No Groq key")
    system_prompt, sub_ctx, top_ids = build_system_prompt(return_meta=True)
    messages = [{"role": "system", "content": system_prompt}] + payload.history + [{"role": "user", "content": payload.message}]
    resp = _groq.chat.completions.create(model=payload.model, messages=messages, temperature=0.3, max_tokens=1024)
    answer = resp.choices[0].message.content
    log_conversation(payload.message, answer, payload.model, resp.usage.total_tokens, sub_ctx, top_ids)
    return {"reply": answer, "model": payload.model, "tokens": resp.usage.total_tokens}
