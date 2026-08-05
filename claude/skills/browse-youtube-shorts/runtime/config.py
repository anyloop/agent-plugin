"""Configuration constants for the browse-youtube-shorts skill."""

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = SKILL_DIR / "output"
PROFILE_DIR = SKILL_DIR / "data" / "research-profile"

CDP_PORT = 9336

DEFAULT_RESULTS_PER_KEYWORD = 10
MAX_RESULTS_PER_KEYWORD = 50

# Outlier detection defaults
DEFAULT_MIN_VIEWS = 100_000

# Default search filters
DEFAULT_SORT_BY = "relevance"
DEFAULT_TIME_RANGE = "all"

# YouTube sp filter values (all include "Shorts only")
# Mapping: (time_range, sort_by) -> sp param value
SP_SHORTS_ONLY = "EgQQARgC"
SP_SHORTS_SORT_VIEWS = "EgQQARgCCAE%3D"
SP_SHORTS_SORT_DATE = "EgQQARgCCAI%3D"
SP_SHORTS_TIME_TODAY = "EgQIAhABGAI%3D"
SP_SHORTS_TIME_WEEK = "EgQIAxABGAI%3D"
SP_SHORTS_TIME_MONTH = "EgQIBBABGAI%3D"
SP_SHORTS_TIME_YEAR = "EgQIBRABGAI%3D"

TIME_RANGE_SP = {
    "all": None,
    "today": SP_SHORTS_TIME_TODAY,
    "week": SP_SHORTS_TIME_WEEK,
    "month": SP_SHORTS_TIME_MONTH,
    "year": SP_SHORTS_TIME_YEAR,
}

SORT_BY_SP = {
    "relevance": SP_SHORTS_ONLY,
    "views": SP_SHORTS_SORT_VIEWS,
    "date": SP_SHORTS_SORT_DATE,
}


class BrowseYoutubeShortsError(Exception):
    """Base exception."""

class ValidationError(BrowseYoutubeShortsError):
    """Input validation errors."""

class SearchError(BrowseYoutubeShortsError):
    """YouTube search failures."""
