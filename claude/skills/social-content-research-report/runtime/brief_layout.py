"""Trim the thirteen-slide research deck to the strategy brief.

A brief (`report_data.json` with `"layout": "strategy_brief"`) is the
strategist's deliverable: the cover, the platform slides for the platforms the
run actually searched, the Meta Ads reference when it was, and then the
strategy section that `strategy_slides.py` appends. The market narrative —
executive summary, landscape, competitive field, format patterns, the closing
About page — never existed for it, so those slides are cut rather than left
blank, and the survivors are renumbered so the pages still count from the
cover. `report-views.ts` drops the same sections on the web page, which is
what keeps the PDF and the Studio report in step.
"""

from __future__ import annotations

import re

STRATEGY_TAG = "{{strategySectionHtml}}"
RESEARCH_COVER_CATEGORY = "Social Content Research"
BRIEF_COVER_CATEGORY = "Content Strategy Brief"

_SLIDE_MARK = re.compile(r"(?=<!-- ═+ SLIDE \d\d — )")
_PAGE_NUM = re.compile(r'<div class="page-num">\d+</div>')

COVER_SLIDE = 1
ADS_SLIDE = 9
RESEARCH_SLIDE_COUNT = 13

# Template slide number → the report_data.json slot that fills it. A brief keeps
# a platform slide only when that slot holds videos, and the ads slide only when
# the Ad Library run captured creatives.
PLATFORM_SLIDES: dict[int, tuple[str, str]] = {
    5: ("tiktok", "brand_videos"),
    6: ("tiktok", "creator_videos"),
    7: ("instagram", "brand_videos"),
    8: ("instagram", "creator_videos"),
    10: ("youtube", "brand_videos"),
    11: ("youtube", "creator_videos"),
}


def is_brief(data: dict) -> bool:
    return data.get("layout") == "strategy_brief"


def brief_slide_numbers(data: dict) -> list[int]:
    """The template slides a brief keeps, in deck order."""
    platforms = data.get("platforms") or {}
    keep = [COVER_SLIDE]
    for number in range(COVER_SLIDE + 1, RESEARCH_SLIDE_COUNT + 1):
        if number == ADS_SLIDE:
            if (data.get("meta_ads") or {}).get("ads"):
                keep.append(number)
        elif number in PLATFORM_SLIDES:
            platform, slot = PLATFORM_SLIDES[number]
            if (platforms.get(platform) or {}).get(slot):
                keep.append(number)
    return keep


def trim_to_brief(html: str, data: dict) -> tuple[str, int]:
    """Cut the template down to the brief's slides, renumbered.

    Returns the trimmed HTML with the strategy placeholder still in place, and
    how many slides survived — where the strategy section starts counting.
    """
    parts = _SLIDE_MARK.split(html)
    head, slides = parts[0], parts[1:]
    if len(slides) != RESEARCH_SLIDE_COUNT:
        raise ValueError(
            f"expected {RESEARCH_SLIDE_COUNT} slide markers in the template, "
            f"found {len(slides)}"
        )
    last, tag, tail = slides[-1].partition(STRATEGY_TAG)
    if not tag:
        raise ValueError("the template has no strategy section placeholder")
    slides[-1] = last
    kept = []
    for page, number in enumerate(brief_slide_numbers(data), 1):
        slide = _PAGE_NUM.sub(
            f'<div class="page-num">{page:02d}</div>', slides[number - 1]
        )
        if number == COVER_SLIDE:
            slide = slide.replace(RESEARCH_COVER_CATEGORY, BRIEF_COVER_CATEGORY, 1)
        kept.append(slide)
    return head + "".join(kept) + tag + tail, len(kept)
