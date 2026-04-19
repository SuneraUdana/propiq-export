"""PropIQ — SQLite storage layer with episodic memory + outcome tracking."""
from __future__ import annotations
import sqlite3, json, uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/propiq.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────
def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            listing_id    TEXT PRIMARY KEY,
            suburb        TEXT,
            address       TEXT,
            sale_price    REAL,
            land_size_sqm REAL,
            house_type    TEXT,
            year_built    INTEGER,
            bedrooms      INTEGER,
            bathrooms     INTEGER,
            image_url     TEXT,
            scraped_at    TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS enrichments (
            listing_id    TEXT PRIMARY KEY,
            material      TEXT,
            walk_score    REAL,
            school_rating REAL,
            nlp_features  TEXT,
            enriched_at   TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS scores (
            listing_id  TEXT PRIMARY KEY,
            inv_score   REAL,
            yield_proxy REAL,
            risk_score  REAL,
            liquidity   REAL,
            quality     REAL,
            rank_suburb INTEGER,
            scored_at   TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS agents (
            agent_id           TEXT PRIMARY KEY,
            suburb             TEXT,
            name               TEXT,
            agency             TEXT,
            listings_count     INTEGER,
            avg_days_on_market REAL
        );
        CREATE TABLE IF NOT EXISTS outcomes (
            outcome_id      TEXT PRIMARY KEY,
            listing_id      TEXT,
            conv_id         TEXT,
            predicted_at    TEXT DEFAULT (datetime('now')),
            predicted_price REAL,
            predicted_score REAL,
            actual_sale     REAL,
            actual_date     TEXT,
            status          TEXT DEFAULT 'pending',
            notes           TEXT
        );
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id         TEXT PRIMARY KEY,
            suburbs        TEXT,
            started_at     TEXT,
            finished_at    TEXT,
            listings_found INTEGER DEFAULT 0,
            scores_written INTEGER DEFAULT 0,
            status         TEXT DEFAULT 'running',
            error_msg      TEXT
        );
        CREATE TABLE IF NOT EXISTS conversations (
            conv_id          TEXT PRIMARY KEY,
            timestamp        TEXT DEFAULT (datetime('now')),
            question         TEXT,
            answer           TEXT,
            model            TEXT,
            tokens           INTEGER,
            suburbs_context  TEXT,
            top_property_ids TEXT
        );
    """)
    conn.commit()
    conn.close()


# ── Upserts ───────────────────────────────────────────────────────────────────
def upsert_listings(records: list[dict]):
    conn = _connect()
    conn.executemany("""
        INSERT INTO listings (listing_id,suburb,address,sale_price,land_size_sqm,
            house_type,year_built,bedrooms,bathrooms,image_url)
        VALUES (:listing_id,:suburb,:address,:sale_price,:land_size_sqm,
            :house_type,:year_built,:bedrooms,:bathrooms,:image_url)
        ON CONFLICT(listing_id) DO UPDATE SET
            sale_price=excluded.sale_price, scraped_at=datetime('now')
    """, records)
    conn.commit(); conn.close()


def upsert_enrichments(records: list[dict]):
    conn = _connect()
    conn.executemany("""
        INSERT INTO enrichments
            (listing_id,material,walk_score,school_rating,nlp_features)
        VALUES (:listing_id,:material,:walk_score,:school_rating,:nlp_features)
        ON CONFLICT(listing_id) DO UPDATE SET
            walk_score=excluded.walk_score, enriched_at=datetime('now')
    """, records)
    conn.commit(); conn.close()


def upsert_scores(records: list[dict]):
    conn = _connect()
    conn.executemany("""
        INSERT INTO scores
            (listing_id,inv_score,yield_proxy,risk_score,liquidity,quality,rank_suburb)
        VALUES
            (:listing_id,:inv_score,:yield_proxy,:risk_score,:liquidity,:quality,:rank_suburb)
        ON CONFLICT(listing_id) DO UPDATE SET
            inv_score=excluded.inv_score, scored_at=datetime('now')
    """, records)
    conn.commit(); conn.close()


# ── Fetch helpers ─────────────────────────────────────────────────────────────
def fetch_all_joined() -> list[dict]:
    conn = _connect()
    rows = conn.execute("""
        SELECT l.listing_id, l.suburb, l.address, l.sale_price,
               l.land_size_sqm, l.house_type, l.year_built,
               l.bedrooms, l.bathrooms, l.image_url,
               e.material, e.walk_score, e.school_rating, e.nlp_features,
               s.inv_score, s.yield_proxy, s.risk_score,
               s.liquidity, s.quality, s.rank_suburb, s.scored_at
        FROM listings l
        JOIN enrichments e ON l.listing_id = e.listing_id
        JOIN scores s      ON l.listing_id = s.listing_id
        ORDER BY s.inv_score DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_scores(suburb: str | None = None, limit: int = 20) -> list[dict]:
    conn = _connect()
    if suburb:
        rows = conn.execute("""
            SELECT l.listing_id, l.suburb, l.address, l.sale_price,
                   l.land_size_sqm, l.house_type, l.year_built,
                   l.bedrooms, l.bathrooms, l.image_url,
                   e.material, e.walk_score, e.school_rating, e.nlp_features,
                   s.inv_score, s.yield_proxy, s.risk_score,
                   s.liquidity, s.quality, s.rank_suburb, s.scored_at
            FROM listings l
            JOIN enrichments e ON l.listing_id = e.listing_id
            JOIN scores s      ON l.listing_id = s.listing_id
            WHERE LOWER(l.suburb) = LOWER(?)
            ORDER BY s.inv_score DESC LIMIT ?
        """, (suburb, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT l.listing_id, l.suburb, l.address, l.sale_price,
                   l.land_size_sqm, l.house_type, l.year_built,
                   l.bedrooms, l.bathrooms, l.image_url,
                   e.material, e.walk_score, e.school_rating, e.nlp_features,
                   s.inv_score, s.yield_proxy, s.risk_score,
                   s.liquidity, s.quality, s.rank_suburb, s.scored_at
            FROM listings l
            JOIN enrichments e ON l.listing_id = e.listing_id
            JOIN scores s      ON l.listing_id = s.listing_id
            ORDER BY s.inv_score DESC LIMIT ?
        """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def fetch_suburb_summary(suburb: str | None = None) -> list[dict]:
    try:
        conn = _connect()
        q = """
            SELECT l.suburb,
                   COUNT(*)       AS count,
                   AVG(s.inv_score) AS avg_score,
                   MIN(s.inv_score) AS min_score,
                   MAX(s.inv_score) AS max_score,
                   AVG(l.sale_price) AS avg_price,
                   AVG(l.sale_price) AS median_price
            FROM listings l
            JOIN scores s ON l.listing_id = s.listing_id
        """
        if suburb:
            rows = conn.execute(q + " WHERE LOWER(l.suburb)=LOWER(?) GROUP BY l.suburb",
                                (suburb,)).fetchall()
        else:
            rows = conn.execute(q + " GROUP BY l.suburb ORDER BY avg_score DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def fetch_top_agents(suburb: str | None = None, limit: int = 5) -> list[dict]:
    conn = _connect()
    if suburb:
        rows = conn.execute(
            "SELECT * FROM agents WHERE LOWER(suburb)=LOWER(?) LIMIT ?",
            (suburb, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM agents LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Episodic: Pipeline Runs ───────────────────────────────────────────────────
def log_pipeline_start(suburbs: list[str]) -> str:
    run_id = str(uuid.uuid4())
    conn = _connect()
    conn.execute("""
        INSERT INTO pipeline_runs (run_id, suburbs, started_at, status)
        VALUES (?, ?, ?, 'running')
    """, (run_id, json.dumps(suburbs), datetime.utcnow().isoformat()))
    conn.commit(); conn.close()
    return run_id


def log_pipeline_finish(run_id: str, listings_found: int = 0,
                        scores_written: int = 0, status: str = "done",
                        error_msg: str | None = None):
    conn = _connect()
    conn.execute("""
        UPDATE pipeline_runs
        SET finished_at=?, listings_found=?, scores_written=?, status=?, error_msg=?
        WHERE run_id=?
    """, (datetime.utcnow().isoformat(), listings_found, scores_written,
          status, error_msg, run_id))
    conn.commit(); conn.close()


def fetch_pipeline_runs(limit: int = 20) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Episodic: Conversations ───────────────────────────────────────────────────
def log_conversation(question: str, answer: str, model: str, tokens: int,
                     suburbs_context: list[str], top_property_ids: list[str]):
    conn = _connect()
    conn.execute("""
        INSERT INTO conversations
            (conv_id,question,answer,model,tokens,suburbs_context,top_property_ids)
        VALUES (?,?,?,?,?,?,?)
    """, (str(uuid.uuid4()), question, answer, model, tokens,
          json.dumps(suburbs_context), json.dumps(top_property_ids)))
    conn.commit(); conn.close()


def fetch_conversations(limit: int = 50) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Outcome Tracking ──────────────────────────────────────────────────────────
def record_outcome(listing_id: str, conv_id: str | None,
                   predicted_price: float | None,
                   predicted_score: float | None,
                   notes: str | None = None) -> str:
    outcome_id = str(uuid.uuid4())
    conn = _connect()
    conn.execute("""
        INSERT INTO outcomes
            (outcome_id,listing_id,conv_id,predicted_at,
             predicted_price,predicted_score,status,notes)
        VALUES (?,?,?,?,?,?,'pending',?)
    """, (outcome_id, listing_id, conv_id,
          datetime.utcnow().isoformat(),
          predicted_price, predicted_score, notes))
    conn.commit(); conn.close()
    return outcome_id


def update_outcome(outcome_id: str, actual_sale: float,
                   actual_date: str | None = None,
                   notes: str | None = None):
    conn = _connect()
    conn.execute("""
        UPDATE outcomes
        SET actual_sale=?, actual_date=?, status='sold',
            notes=COALESCE(?,notes)
        WHERE outcome_id=?
    """, (actual_sale,
          actual_date or datetime.utcnow().isoformat()[:10],
          notes, outcome_id))
    conn.commit(); conn.close()


def withdraw_outcome(outcome_id: str, notes: str | None = None):
    conn = _connect()
    conn.execute("""
        UPDATE outcomes SET status='withdrawn', notes=COALESCE(?,notes)
        WHERE outcome_id=?
    """, (notes, outcome_id))
    conn.commit(); conn.close()


def fetch_outcomes(status: str | None = None, limit: int = 100) -> list[dict]:
    conn = _connect()
    base = """
        SELECT
            o.outcome_id, o.listing_id, o.conv_id,
            o.predicted_at, o.predicted_price, o.predicted_score,
            o.actual_sale, o.actual_date, o.status, o.notes,
            l.suburb, l.address, l.sale_price AS listed_price,
            l.bedrooms, l.bathrooms, l.land_size_sqm,
            s.inv_score, s.yield_proxy, s.rank_suburb,
            CASE
                WHEN o.actual_sale IS NOT NULL AND o.predicted_price IS NOT NULL
                THEN ROUND((o.actual_sale - o.predicted_price)
                           / o.predicted_price * 100, 2)
                ELSE NULL
            END AS variance_pct,
            CASE
                WHEN o.actual_sale IS NOT NULL AND o.predicted_price IS NOT NULL
                THEN CASE WHEN o.actual_sale >= o.predicted_price THEN 1 ELSE 0 END
                ELSE NULL
            END AS hit
        FROM outcomes o
        LEFT JOIN listings l ON o.listing_id = l.listing_id
        LEFT JOIN scores   s ON o.listing_id = s.listing_id
    """
    if status:
        rows = conn.execute(
            base + " WHERE o.status=? ORDER BY o.predicted_at DESC LIMIT ?",
            (status, limit)).fetchall()
    else:
        rows = conn.execute(
            base + " ORDER BY o.predicted_at DESC LIMIT ?",
            (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_outcome_stats() -> dict:
    conn = _connect()
    row = conn.execute("""
        SELECT
            COUNT(*)                                              AS total_tracked,
            SUM(CASE WHEN status='sold'      THEN 1 ELSE 0 END)  AS total_sold,
            SUM(CASE WHEN status='pending'   THEN 1 ELSE 0 END)  AS total_pending,
            SUM(CASE WHEN status='withdrawn' THEN 1 ELSE 0 END)  AS total_withdrawn,
            AVG(CASE
                WHEN actual_sale IS NOT NULL AND predicted_price IS NOT NULL
                THEN (actual_sale - predicted_price) / predicted_price * 100
                ELSE NULL END)                                    AS avg_variance_pct,
            SUM(CASE
                WHEN actual_sale IS NOT NULL AND actual_sale >= predicted_price
                THEN 1 ELSE 0 END)                                AS hits,
            COUNT(CASE WHEN actual_sale IS NOT NULL THEN 1 END)   AS resolved
        FROM outcomes
    """).fetchone()
    conn.close()
    d = dict(row)
    resolved = d.get("resolved") or 0
    hits     = d.get("hits") or 0
    d["hit_rate_pct"] = round(hits / resolved * 100, 1) if resolved else None
    return d
