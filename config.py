import os
from dotenv import load_dotenv

load_dotenv()

# AI provider — "gemini" (free) or "anthropic" (paid)
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()

# API keys
GOOGLE_API_KEY    = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Default models
GEMINI_MODEL    = os.getenv("GEMINI_MODEL",    "gemini-1.5-flash")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

def active_api_key() -> str:
    return GOOGLE_API_KEY if AI_PROVIDER == "gemini" else ANTHROPIC_API_KEY

def active_model() -> str:
    return GEMINI_MODEL if AI_PROVIDER == "gemini" else ANTHROPIC_MODEL

# LinkedIn
# Profile URL is optional but recommended — it appears on generated resumes and
# pre-fills the "LinkedIn URL" question on Easy Apply forms. Email + password
# are ONLY required for the Auto Apply tab; the rest of the app works without.
LINKEDIN_PROFILE_URL = os.getenv("LINKEDIN_PROFILE_URL", "")
LINKEDIN_EMAIL       = os.getenv("LINKEDIN_EMAIL",       "")
LINKEDIN_PASSWORD    = os.getenv("LINKEDIN_PASSWORD",    "")


def auto_apply_available() -> bool:
    return bool(LINKEDIN_EMAIL and LINKEDIN_PASSWORD)

# Job search defaults
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "United States")
DEFAULT_NUM_JOBS = int(os.getenv("DEFAULT_NUM_JOBS", "50"))
JOB_SEARCH_DAYS  = int(os.getenv("JOB_SEARCH_DAYS", "30"))
OUTPUT_DIR       = os.getenv("OUTPUT_DIR", "./output")

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".svg"}

LINKEDIN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}
