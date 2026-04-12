"""PropIQ — Central Configuration"""
from pathlib import Path

BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"

DATA_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

DB_PATH    = DATA_DIR / "propiq.db"
DB_URL     = f"sqlite:///{DB_PATH}"     # swap for postgresql://user:pass@host/propiq

# Scraper
RATE_LIMIT_SEC    = 1.2
MAX_PAGES_PER_SUB = 5
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
]

TARGET_SUBURBS = [
    "Fitzroy", "Richmond", "Hawthorn",
    "Brunswick", "South Yarra", "Collingwood",
    "St Kilda", "Prahran", "Northcote", "Footscray",
]

SUBURB_MEDIANS = {
    "Fitzroy": 1_050_000, "Richmond": 1_100_000, "Hawthorn": 1_350_000,
    "Brunswick": 900_000,  "South Yarra": 1_300_000, "Collingwood": 980_000,
    "St Kilda": 950_000,   "Prahran": 1_050_000, "Northcote": 1_000_000,
    "Footscray": 750_000,
}

SUBURB_WALK_SCORES  = {"Fitzroy":92,"Richmond":88,"Hawthorn":85,"Brunswick":90,
                        "South Yarra":91,"Collingwood":87,"St Kilda":89,
                        "Prahran":88,"Northcote":84,"Footscray":80}
SUBURB_SCHOOL_RTGS  = {"Fitzroy":8.2,"Richmond":7.9,"Hawthorn":8.7,"Brunswick":7.8,
                        "South Yarra":9.1,"Collingwood":7.6,"St Kilda":7.5,
                        "Prahran":8.0,"Northcote":8.1,"Footscray":7.3}
SUBURB_INCOMES      = {"Fitzroy":95_000,"Richmond":98_000,"Hawthorn":115_000,
                        "Brunswick":82_000,"South Yarra":120_000,"Collingwood":88_000,
                        "St Kilda":85_000,"Prahran":92_000,"Northcote":89_000,
                        "Footscray":72_000}

# Enrichment
BRICK_THRESHOLD     = 0.55
NDVI_TREE_THRESHOLD = 0.55
TREE_RISK_PENALTY   = 0.05

# DE optimiser
DE_POPSIZE   = 18
DE_MAXITER   = 300
DE_TOL       = 1e-6
DE_SEED      = 42

# Reporting
TOP_K                 = 10
SCORE_ALERT_THRESHOLD = 0.80
