"""PropIQ — SQLite storage layer (swap DB_URL for PostgreSQL in prod)."""
import sqlite3, json
from propiq.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    listing_id   TEXT PRIMARY KEY,
    suburb       TEXT, address      TEXT, sale_price   REAL,
    land_size_sqm REAL, house_type  TEXT, year_built   INTEGER,
    bedrooms     INTEGER, bathrooms INTEGER,
    agent_name   TEXT, agency       TEXT, agent_phone  TEXT,
    description  TEXT, image_url    TEXT,
    scraped_at   TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS enrichments (
    listing_id      TEXT PRIMARY KEY,
    material        TEXT, material_conf REAL,
    tree_flag       INTEGER, ndvi_score REAL,
    suburb_income   REAL, walk_score REAL, school_rating REAL,
    nlp_features    TEXT,
    enriched_at     TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS scores (
    listing_id   TEXT PRIMARY KEY,
    inv_score    REAL, yield_proxy REAL,
    risk_score   REAL, liquidity   REAL, quality REAL,
    weights_json TEXT,
    rank_suburb  INTEGER,
    scored_at    TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS agents (
    agent_name TEXT, agency TEXT, agent_phone TEXT,
    suburb TEXT, listing_count INTEGER DEFAULT 1,
    PRIMARY KEY (agent_name, agency)
);
CREATE TABLE IF NOT EXISTS outcomes (
    listing_id     TEXT PRIMARY KEY,
    clicked        INTEGER DEFAULT 0,
    purchased      INTEGER DEFAULT 0,
    actual_price   REAL,
    feedback_score REAL,
    recorded_at    TEXT DEFAULT (datetime('now'))
);
"""

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit(); conn.close()
    print(f"[storage] DB initialised → {DB_PATH}")

def upsert_listings(records: list[dict]):
    conn = sqlite3.connect(DB_PATH)
    for r in records:
        conn.execute("""INSERT OR REPLACE INTO listings
            (listing_id,suburb,address,sale_price,land_size_sqm,house_type,
             year_built,bedrooms,bathrooms,agent_name,agency,agent_phone,description,image_url)
            VALUES (:listing_id,:suburb,:address,:sale_price,:land_size_sqm,:house_type,
                    :year_built,:bedrooms,:bathrooms,:agent_name,:agency,:agent_phone,
                    :description,:image_url)""", r)
    conn.commit(); conn.close()

def upsert_enrichments(records: list[dict]):
    conn = sqlite3.connect(DB_PATH)
    for r in records:
        r2 = dict(r)
        if isinstance(r2.get("nlp_features"), dict):
            r2["nlp_features"] = json.dumps(r2["nlp_features"])
        conn.execute("""INSERT OR REPLACE INTO enrichments
            (listing_id,material,material_conf,tree_flag,ndvi_score,
             suburb_income,walk_score,school_rating,nlp_features)
            VALUES (:listing_id,:material,:material_conf,:tree_flag,:ndvi_score,
                    :suburb_income,:walk_score,:school_rating,:nlp_features)""", r2)
    conn.commit(); conn.close()

def upsert_scores(records: list[dict]):
    conn = sqlite3.connect(DB_PATH)
    for r in records:
        r2 = dict(r)
        if isinstance(r2.get("weights_json"), list):
            r2["weights_json"] = json.dumps(r2["weights_json"])
        conn.execute("""INSERT OR REPLACE INTO scores
            (listing_id,inv_score,yield_proxy,risk_score,liquidity,quality,weights_json,rank_suburb)
            VALUES (:listing_id,:inv_score,:yield_proxy,:risk_score,:liquidity,:quality,
                    :weights_json,:rank_suburb)""", r2)
    conn.commit(); conn.close()

def fetch_all_joined() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT l.*,e.material,e.material_conf,e.tree_flag,e.ndvi_score,
               e.suburb_income,e.walk_score,e.school_rating,e.nlp_features,
               s.inv_score,s.yield_proxy,s.risk_score,s.liquidity,s.quality,
               s.weights_json,s.rank_suburb
        FROM listings l
        JOIN enrichments e ON l.listing_id=e.listing_id
        JOIN scores s ON l.listing_id=s.listing_id
        ORDER BY s.inv_score DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
