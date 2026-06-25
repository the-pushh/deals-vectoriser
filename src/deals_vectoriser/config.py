"""Environment + constants. Loaded once at import."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- SEC access ---
SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT", "deals-vectoriser research pushkarborkar1809@gmail.com"
)
SEC_MAX_RPS = float(os.getenv("SEC_MAX_RPS", "5"))
DEFAULT_LOOKBACK_DAYS = int(os.getenv("DEFAULT_LOOKBACK_DAYS", "2"))

# --- Endpoints (all verified to work with the UA header) ---
EFTS_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# --- Embeddings (OpenRouter, OpenAI-compatible) ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
EMBED_MODEL = os.getenv("EMBED_MODEL", "openai/text-embedding-3-small")
EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))

# --- Paths ---
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
FILINGS_JSON = DATA_DIR / "filings.json"
