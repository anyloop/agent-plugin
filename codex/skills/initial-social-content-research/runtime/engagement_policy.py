"""Keep engagement evidence separate from useful but unproven context."""

from __future__ import annotations

import math
import re
from typing import Any

TARGET = 10_000
UNITS = {"tiktok": "likes", "instagram": "likes", "youtube": "views"}
TESTS = {
    "exact-client-product": 3,
    "named-competitor-product": 3,
    "product-decision-service": 2,
    "precise-product-problem": 2,
}


def engagement(item: dict[str, Any], platform: str) -> float | None:
    """Only compare a single measured count in the platform's declared unit."""
    match = re.fullmatch(
        r"\s*([0-9]+(?:\.[0-9]+)?)\s*([kmb]?)\s+(likes|views)\s*",
        str(item.get("metric") or "").lower().replace(",", ""),
    )
    if not match or match[3] != UNITS[platform]:
        return None
    return (
        float(match[1])
        * {"": 1, "k": 1000, "m": 1_000_000, "b": 1_000_000_000}[match[2]]
    )


def relevant(item: dict[str, Any]) -> bool:
    proof = item.get("relevance") or {}
    if not isinstance(proof, dict):
        return False
    minimum = TESTS.get(proof.get("test"))
    specificity = proof.get("specificity")
    return (
        minimum is not None
        and type(specificity) is int
        and minimum <= specificity <= 3
        and len(str(proof.get("evidence") or "").strip()) >= 20
    )


def performance_reference(item: dict[str, Any], platform: str) -> bool:
    count = engagement(item, platform)
    duration = item.get("duration_seconds")
    short = duration is None or (type(duration) in (int, float) and 0 < duration <= 180)
    return relevant(item) and count is not None and count >= TARGET and short


def quality_gap(selected: list[dict], candidates: list[dict], platform: str) -> dict:
    """A full page can still need discovery; card count is not a quality gate."""
    needed = math.ceil(len(selected) * 0.6)
    strong = len(
        {
            item.get("url")
            for item in selected
            if item.get("url") and performance_reference(item, platform)
        }
    )
    available = len(
        {
            item.get("url")
            for item in candidates
            if item.get("url") and performance_reference(item, platform)
        }
    )
    return {
        "performance_target": needed,
        "performance_selected": strong,
        "performance_available": available,
        "performance_missing": max(0, needed - strong),
        "engagement_target": TARGET,
        "engagement_unit": UNITS[platform],
    }


def selection_errors(
    selected: list[dict], candidates: list[dict], platform: str, gap_note: str
) -> list[str]:
    errors = []
    selected_urls = {item.get("url") for item in selected}
    alternatives = [
        item
        for item in candidates
        if item.get("url") not in selected_urls
        and performance_reference(item, platform)
    ]
    for item in selected:
        label = f"{platform}.creator: {item.get('url')}"
        if engagement(item, platform) is None:
            errors.append(
                f"{label}: needs measured {UNITS[platform]}, not another metric"
            )
        count = engagement(item, platform)
        proof = item.get("relevance") or {}
        if not isinstance(proof, dict):
            proof = {}
        specificity = proof.get("specificity")
        specificity = specificity if type(specificity) is int else 0
        if (
            count
            and any(
                (engagement(other, platform) or 0) >= count * 2
                and other["relevance"]["specificity"] >= specificity
                for other in alternatives
            )
            and len(str(item.get("selection_reason") or "").strip()) < 20
        ):
            errors.append(
                f"{label}: stronger equally relevant alternative requires a concrete selection_reason"
            )
        if not performance_reference(item, platform):
            if (
                item.get("selection_role") != "context"
                or len(str(item.get("selection_reason") or "").strip()) < 20
            ):
                errors.append(
                    f"{label}: below-target or long-form reference needs context role and specific selection_reason"
                )
    gap = quality_gap(selected, candidates, platform)
    if gap["performance_missing"]:
        if gap["performance_selected"] < min(
            gap["performance_available"], gap["performance_target"]
        ):
            errors.append(
                f"{platform}.creator: stronger relevant candidates exist; at least 60% of selections must meet the engagement target"
            )
        if (
            gap["performance_available"] < gap["performance_target"]
            and len(gap_note.strip()) < 20
        ):
            errors.append(
                f"{platform}.creator: insufficient strong evidence needs creator_quality_gap, not a silently lowered floor"
            )
    return errors


def primary_strategy_errors(data: dict) -> list[str]:
    """The workflow orders five primary concepts before its three reserves."""
    items = data.get("strategies", {}).get("items", [])
    if not items:
        return []  # Discovery drafts have not reached strategy selection yet.
    references = {
        item.get("url"): (platform, item)
        for platform in UNITS
        for group in ("brand_videos", "creator_videos")
        for item in data.get("platforms", {}).get(platform, {}).get(group, [])
    }
    strong = set()
    for strategy in items[:5]:
        reference = references.get(strategy.get("url"))
        if reference and performance_reference(reference[1], reference[0]):
            strong.add(strategy["url"])
    if len(strong) < 3:
        return [
            "strategies: five primary concepts need at least three distinct relevant references meeting the engagement target"
        ]
    return []
