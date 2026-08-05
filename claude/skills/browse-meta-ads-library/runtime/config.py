"""Configuration constants for the browse-meta-ads-library skill."""

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = SKILL_DIR / "output"
PROFILE_DIR = SKILL_DIR / "data" / "browser_profile"

DEFAULT_RESULTS_PER_KEYWORD = 20
MAX_RESULTS_PER_KEYWORD = 50

# Meta Ad Library base URL
AD_LIBRARY_BASE_URL = "https://www.facebook.com/ads/library/"
AD_LIBRARY_SEARCH_URL = "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&q={query}&search_type=keyword_unordered"

# Filter options
PLATFORM_FILTERS = ["all", "facebook", "instagram", "audience_network", "messenger"]
MEDIA_TYPE_FILTERS = ["all", "image", "video", "meme", "carousel"]

# Search type options
SEARCH_TYPES = ["keyword", "advertiser_and_keyword"]

# Longevity thresholds (days)
LONGEVITY_PROVEN = 90
LONGEVITY_ESTABLISHED = 30
LONGEVITY_TESTING = 7


class BrowseMetaAdsError(Exception):
    """Base exception."""

class ValidationError(BrowseMetaAdsError):
    """Input validation errors."""

class SearchError(BrowseMetaAdsError):
    """Meta Ad Library search failures."""
