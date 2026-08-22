"""Reader-facing copy budgets for the Social Content Research deck."""

from __future__ import annotations

import re

STATIC_LIMITS = {
    "cover.reportSubtitle": (140, 2),
    "exec.execSummaryHeadline": (110, 1),
    "exec.finding1": (180, 2),
    "exec.finding2": (180, 2),
    "exec.finding3": (180, 2),
    "exec.execRecommendation": (180, 2),
    "landscape.landscapeHeadline": (110, 1),
    "landscape.landscapeCopy": (180, 2),
    "meta_ads.headline": (110, 1),
    "meta_ads.intro": (160, 2),
    "formats.formatsHeadline": (110, 1),
    "strategies.headline": (110, 1),
    "strategies.intro": (160, 2),
    "strategies.closingHeadline": (110, 1),
    "strategies.closingCopy": (160, 2),
}

AUDIT_NARRATIVE_PATTERNS = (
    r"\breject(?:ed|ion|ions)?\b",
    r"\bexcluded?\b",
    r"\bcandidate(?:s| rows?)?\b",
    r"\bblank captions?\b",
    r"\bmissing handles?\b",
    r"\bquery (?:coverage|results?|hits?)\b",
    r"\bsearch(?:ed|es|ing)? (?:for|terms?|queries)\b",
)


def _plain(text: str) -> str:
    return re.sub(r"</?[a-z][^>]*>", "", str(text)).strip()


def _sentence_count(text: str) -> int:
    if not text:
        return 0
    return len(re.split(r"(?<=[.!?])\s+", text))


def _static_fields(data: dict) -> list[tuple[str, str, int, int]]:
    fields = []
    for path, (max_chars, max_sentences) in STATIC_LIMITS.items():
        section_name, field_name = path.split(".", 1)
        fields.append(
            (
                path,
                data.get(section_name, {}).get(field_name, ""),
                max_chars,
                max_sentences,
            )
        )
    return fields


def _repeated_fields(data: dict) -> list[tuple[str, str, int, int]]:
    fields = []
    for platform_name, section in data.get("platforms", {}).items():
        for field_name in (
            "brand_headline",
            "creator_headline",
        ):
            fields.append(
                (
                    f"platforms.{platform_name}.{field_name}",
                    section.get(field_name, ""),
                    110,
                    1,
                )
            )
        for field_name in ("brand_intro", "creator_intro"):
            fields.append(
                (
                    f"platforms.{platform_name}.{field_name}",
                    section.get(field_name, ""),
                    160,
                    2,
                )
            )
    for index in range(1, 4):
        fields.append(
            (
                f"competitive.tier{index}Desc",
                data.get("competitive", {}).get(f"tier{index}Desc", ""),
                140,
                1,
            )
        )
    for index in range(1, 5):
        fields.append(
            (
                f"formats.format{index}Desc",
                data.get("formats", {}).get(f"format{index}Desc", ""),
                140,
                1,
            )
        )
    for index, item in enumerate(data.get("strategies", {}).get("items", []), 1):
        fields.append(
            (
                f"strategies.items[{index}].why_this_video",
                item.get("why_this_video", ""),
                140,
                1,
            )
        )
    return fields


def validate_reader_copy(data: dict) -> list[str]:
    """Flag slide copy that reads like an audit log instead of a visual brief."""
    warnings = []
    for path, text, max_chars, max_sentences in (
        _static_fields(data) + _repeated_fields(data)
    ):
        plain = _plain(text)
        if not plain:
            continue
        if len(plain) > max_chars:
            warnings.append(
                f"{path}: {len(plain)} characters exceeds the "
                f"{max_chars}-character slide-copy budget"
            )
        sentences = _sentence_count(plain)
        if sentences > max_sentences:
            warnings.append(
                f"{path}: {sentences} sentences exceeds the "
                f"{max_sentences}-sentence slide-copy budget"
            )
        is_video_intro = path.endswith(("brand_intro", "creator_intro"))
        if is_video_intro or path == "meta_ads.intro":
            if any(
                re.search(pattern, plain, re.IGNORECASE)
                for pattern in AUDIT_NARRATIVE_PATTERNS
            ):
                warnings.append(
                    f"{path}: contains search or rejection methodology; "
                    "move it to curation_audit.json"
                )
    return warnings
