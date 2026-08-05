"""Configuration constants and exception hierarchy for the browse-tiktok-research skill."""

import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
_runtime_data_dir = os.environ.get("ADANT_SOCIAL_DATA_DIR")
DATA_DIR = Path(_runtime_data_dir) / "browse-tiktok-research" if _runtime_data_dir else SKILL_DIR / "data"
DEFAULT_OUTPUT_DIR = DATA_DIR / "output"
PROFILE_DIR = DATA_DIR / "browser_profile"
COOKIES_PATH = DATA_DIR / "tiktok_cookies.json"

DEFAULT_RESULTS_PER_KEYWORD = 10
MAX_RESULTS_PER_KEYWORD = 30
MAX_TOTAL_RESULTS = 100
API_PAGE_SIZE = 20

# Top-N display limits
TOP_VIDEOS_LIMIT = 30

# Outlier detection defaults
# NOTE: TikTok search results show likes (not views) on thumbnails,
# so thresholds here apply to like_count from search results.
DEFAULT_MIN_LIKES = 10_000
DEFAULT_MIN_VIEW_FOLLOWER_RATIO = 5.0

# Default search filters (optimized for finding viral outliers)
DEFAULT_SORT_BY = "likes"
DEFAULT_TIME_RANGE = "3months"
DEFAULT_DURATION = "all"

# TikTok search filter constants
SORT_TYPE = {"relevance": 0, "likes": 1, "date": 2}
PUBLISH_TIME = {"all": 0, "day": 1, "week": 2, "month": 3, "3months": 4, "6months": 5}
DURATION_FILTER = {"all": 0, "short": 1, "medium": 2, "long": 3}  # short=<1min, medium=1-5min, long=>5min


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class BrowseTiktokResearchError(Exception):
    """Base exception for browse-tiktok-research skill errors."""


class ValidationError(BrowseTiktokResearchError):
    """Input validation errors."""


class ProcessingError(BrowseTiktokResearchError):
    """Processing or conversion failures."""


class SearchError(BrowseTiktokResearchError):
    """TikTok search failures."""


class LoginRequiredError(BrowseTiktokResearchError):
    """Raised when TikTok login is needed."""
