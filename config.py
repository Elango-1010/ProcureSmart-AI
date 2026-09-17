"""Central configuration for ProcureSmart AI."""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# Database: SQLite for local dev, Azure SQL / PostgreSQL via env var in cloud
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'procuresmart.db'}")

# LLM configuration (AI Use Case 4 - narrative generation)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LLM_ENABLED = bool(OPENAI_API_KEY)

# Procurement master data
DEPARTMENTS = [
    "IT", "Facilities", "Marketing", "Operations",
    "Human Resources", "Finance", "R&D", "Logistics",
]

CATEGORIES = [
    "IT Hardware", "IT Software & Licences", "Office Supplies",
    "Professional Services", "Travel", "Facilities Maintenance",
    "Marketing Services", "Logistics & Freight",
]

# Business rules for maverick spend detection
MAVERICK_RULES = {
    "requisition_approval_threshold": 50_000,   # INR - needs senior approval above this
    "single_txn_alert_threshold": 200_000,      # INR - always flagged for review
    "department_variance_multiplier": 3.0,      # x median dept spend = anomalous
}

# Volume milestone thresholds for savings recommendations
VOLUME_MILESTONES = [500_000, 1_000_000, 2_500_000, 5_000_000]

# Contract renewal warning window
CONTRACT_RENEWAL_WARNING_DAYS = 90

# Anomaly model settings
ISOLATION_FOREST_PARAMS = {
    "n_estimators": 150,
    "contamination": 0.06,
    "random_state": 42,
}

RISK_BANDS = [(0.75, "HIGH"), (0.50, "MEDIUM"), (0.0, "LOW")]


def ensure_dirs() -> None:
    """Create data directories if they do not exist."""
    for d in (DATA_DIR, RAW_DIR, PROCESSED_DIR):
        d.mkdir(parents=True, exist_ok=True)
