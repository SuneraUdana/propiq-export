"""PropIQ — FastAPI application with episodic memory + outcome tracking."""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from pathlib import Path
from groq import Groq

from propiq.storage import (
    init_db,
    fetch_scores,
    fetch_top_agents,
    log_pipeline_start,
    log_pipeline_finish,
    log_conversation,
    fetch_pipeline_runs,
    fetch_conversations,
    record_outcome,
    update_outcome,
    withdraw_outcome,
    fetch_outcomes,
    fetch_outcome_stats,
)
from propiq.reporter import json_report
from propiq.agent import run_pipeline
from propiq.context import build_system_prompt

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="PropIQ API", version="0.2.0",
              description="Property investment scoring engine with outcome tracking")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ── Groq client ───────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
_groq = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ── Models ────────────────────────────────────────────────────────────────────
class PipelineRequest(BaseModel):
    suburbs: list[str]

class PipelineResponse(BaseModel):
    status: str; suburbs: list[str]; message: str

class ChatRequest(BaseModel):
    message: str
    model:   str        = "llama-3.3-70b-versatile"
    history: list[dict] = []

class OutcomeCreateRequest(BaseModel):
    listing_id:      str
    conv_id:         str | None = None
    predicted_price: float | None = None
    predicted_score: float | None = None
    notes:           str | None = None

class OutcomeUpdateRequest(BaseModel):
    actual_sale: float
    actual_date: str | None = None
    notes:       str | None = None

class OutcomeWithdrawRequest(BaseModel):
    notes: str | None = None

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    import os
    from huggingface_hub import hf_hub_download
    token = os.environ.get("HF_TOKEN","")
    if token:
        try:
            from propiq.storage import DB_PATH
            hf_hub_download(
                repo_id="sunera01/propiq-db",
                filename="propiq.db",
                repo_type="dataset",
                token=token,
                local_dir=str(DB_PATH.parent),
                local_dir_use_symlinks=False
            )
            print("[startup] DB loaded from HF dataset ✓")
        except Exception as e:
            print(f"[startup] No dataset DB yet: {e}")

# ── Static / Dashboard ────────────────────────────────────────────────────────
_static = Path("static")
if _static.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse("static/index.html")

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "version": "0.2.0"}

# ── Market Context ────────────────────────────────────────────────────────────
@app.get("/api/market-context")
def market_context(
    suburb: str | None = Query(None),
    limit:  int        = Query(20, ge=1, le=100),
):
    records = fetch_scores(suburb=suburb, limit=limit)
    agents  = fetch_top_agents(suburb=suburb, limit=5)
    report  = json_report(records, suburb=suburb, top_k=limit)
    if suburb and not records:
        raise HTTPException(status_code=404,
            detail=f"No scored listings for '{suburb}'. Run POST /api/pipeline/run first.")
    return {**report, "agents": agents}

# ── Pipeline ──────────────────────────────────────────────────────────────────
_running: set[str] = set()

@app.post("/api/pipeline/run", response_model=PipelineResponse)
def pipeline_run(body: PipelineRequest, background_tasks: BackgroundTasks):
    if not body.suburbs:
        raise HTTPException(status_code=422, detail="suburbs list must not be empty")
    already = [s for s in body.suburbs if s in _running]
    if already:
        raise HTTPException(status_code=409,
            detail=f"Pipeline already running for: {already}")
    for s in body.suburbs:
        _running.add(s)

    def _run_and_cleanup(suburbs: list[str]):
        run_id = log_pipeline_start(suburbs)
        listings_found = scores_written = 0
        try:
            result = run_pipeline(suburbs)
            if isinstance(result, dict):
                listings_found = len(result.get("records", []))
                scores_written = len(result.get("scored", []))
            log_pipeline_finish(run_id, listings_found, scores_written, "done")
        except Exception as exc:
            log_pipeline_finish(run_id, listings_found, scores_written,
                                "error", str(exc))
        finally:
            for s in suburbs:
                _running.discard(s)

    background_tasks.add_task(_run_and_cleanup, body.suburbs)
    return PipelineResponse(status="accepted", suburbs=body.suburbs,
        message="Pipeline started. Poll GET /api/market-context to see results.")

@app.get("/api/pipeline/status")
def pipeline_status():
    return {"running": list(_running), "idle": len(_running) == 0}

@app.get("/api/pipeline/history")
def pipeline_history(limit: int = Query(20, ge=1, le=100)):
    return {"runs": fetch_pipeline_runs(limit=limit)}

# ── Chat ──────────────────────────────────────────────────────────────────────
@app.post("/api/chat")
def chat(payload: ChatRequest):
    if not GROQ_API_KEY or _groq is None:
        raise HTTPException(status_code=500,
            detail="GROQ_API_KEY not set. Add it to .env file.")
    system_prompt, suburbs_ctx, top_ids = build_system_prompt(return_meta=True)
    messages = [{"role": "system", "content": system_prompt}]
    messages += payload.history
    messages.append({"role": "user", "content": payload.message})
    resp = _groq.chat.completions.create(
        model=payload.model, messages=messages,
        temperature=0.3, max_tokens=1024)
    answer = resp.choices[0].message.content
    tokens = resp.usage.total_tokens
    log_conversation(payload.message, answer, payload.model, tokens,
                     suburbs_ctx, top_ids)
    return {"reply": answer, "model": payload.model, "tokens": tokens}

@app.get("/api/chat/history")
def chat_history(limit: int = Query(50, ge=1, le=200)):
    return {"conversations": fetch_conversations(limit=limit)}

# ── Outcome Tracking ──────────────────────────────────────────────────────────
@app.post("/api/outcomes", status_code=201)
def create_outcome(body: OutcomeCreateRequest):
    """Track a property as a PropIQ recommendation to evaluate later."""
    outcome_id = record_outcome(
        listing_id=body.listing_id,
        conv_id=body.conv_id,
        predicted_price=body.predicted_price,
        predicted_score=body.predicted_score,
        notes=body.notes,
    )
    return {"outcome_id": outcome_id, "status": "pending"}

@app.put("/api/outcomes/{outcome_id}")
def resolve_outcome(outcome_id: str, body: OutcomeUpdateRequest):
    """Record the actual sale price once the property has sold."""
    update_outcome(outcome_id, body.actual_sale, body.actual_date, body.notes)
    return {"outcome_id": outcome_id, "status": "sold",
            "actual_sale": body.actual_sale}

@app.post("/api/outcomes/{outcome_id}/withdraw")
def withdraw(outcome_id: str, body: OutcomeWithdrawRequest):
    """Mark a tracked property as withdrawn (listing removed / not sold)."""
    withdraw_outcome(outcome_id, body.notes)
    return {"outcome_id": outcome_id, "status": "withdrawn"}

@app.get("/api/outcomes")
def list_outcomes(
    status: str | None = Query(None, description="pending | sold | withdrawn"),
    limit:  int        = Query(100, ge=1, le=500),
):
    """Return all tracked outcomes with variance % and hit flag."""
    return {
        "outcomes": fetch_outcomes(status=status, limit=limit),
        "stats":    fetch_outcome_stats(),
    }

@app.get("/api/outcomes/stats")
def outcome_stats():
    """Aggregate performance: hit rate, avg variance, totals."""
    return fetch_outcome_stats()
# rebuild
