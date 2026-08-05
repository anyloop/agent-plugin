"""Configuration constants for the browse-instagram-reels skill."""

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = SKILL_DIR / "output"
PROFILE_DIR = SKILL_DIR / "data" / "browser_profile"

DEFAULT_RESULTS_PER_KEYWORD = 10
MAX_RESULTS_PER_KEYWORD = 50

# Outlier detection defaults
DEFAULT_MIN_VIEWS = 50_000
DEFAULT_MIN_VIEW_FOLLOWER_RATIO = 5.0

# Default search filters
DEFAULT_SORT_BY = "relevance"
DEFAULT_TIME_RANGE = "recent"

# Instagram search doesn't have the same filter params as TikTok
# but we can filter results post-collection
TIME_RANGE_DAYS = {
    "all": 0,
    "day": 1,
    "week": 7,
    "month": 30,
    "3months": 90,
    "6months": 180,
}


class BrowseInstagramReelsError(Exception):
    """Base exception."""

class ValidationError(BrowseInstagramReelsError):
    """Input validation errors."""

class SearchError(BrowseInstagramReelsError):
    """Instagram search failures."""

class LoginRequiredError(BrowseInstagramReelsError):
    """Raised when Instagram login is needed."""
