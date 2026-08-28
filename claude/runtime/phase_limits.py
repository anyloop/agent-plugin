"""Time budgets shared by social-research runners and progress views."""

from __future__ import annotations


DEFAULT_PHASE_TIMEOUT_SECONDS = 600

# Longest/specific prefixes come first. Strategy picks are independent jobs, so
# their limit applies per video rather than to the whole five-video stage.
PHASE_TIMEOUTS = (
    ("platform-meta-ads", 480),
    ("platform-instagram", 720),
    ("platform-tiktok", 720),
    ("platform-youtube", 480),
    ("strategy-pick", 300),
    ("product-profile", 180),
    ("competitors", 300),
    ("keywords", 120),
    ("curation", 360),
    ("strategy", 480),
    ("report", 300),
    ("delivery", 180),
    ("doctor", 90),
)

STAGE_BUDGETS = {
    "production-complete": {
        "setup": 60,
        "product": 180,
        "competitors": 300,
        "keywords": 120,
        "discovery": 720,
        "curation": 360,
        "strategy": 480,
        "report": 300,
        "delivery": 180,
    },
    "fast-draft": {
        "setup": 60,
        "product": 150,
        "competitors": 210,
        "keywords": 120,
        "discovery": 540,
        "curation": 180,
        "report": 180,
    },
}


def phase_timeout_seconds(phase: str) -> int:
    """Return the default hard limit for one phase job."""
    for prefix, seconds in PHASE_TIMEOUTS:
        if phase == prefix or phase.startswith(prefix + "-"):
            return seconds
    return DEFAULT_PHASE_TIMEOUT_SECONDS


def stage_budget_seconds(mode: str, stage_id: str) -> int:
    """Return the user-facing budget for one workflow stage."""
    return STAGE_BUDGETS[mode][stage_id]
