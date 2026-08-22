"""Validate product relevance and brand-reach selection before deck rendering."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PLATFORMS = ("tiktok", "instagram", "youtube")
RELEVANCE_TESTS = {
    "exact-client-product": 3,
    "named-competitor-product": 3,
    "product-decision-service": 2,
    "precise-product-problem": 2,
}
REQUIRED_SEARCH_MODES = {"official-account", "product-query"}
TOP_UP_SEARCH_MODES = {
    "brand": {
        "official-account",
        "product-query",
        "brand-hashtag",
        "partnership-query",
        "retailer-distributor",
        "content-type-expansion",
        "indexed-fallback",
    },
    "creator": {
        "exact-product",
        "competitor-product",
        "product-decision",
        "precise-problem",
        "content-type-expansion",
        "mined-hashtag",
        "indexed-fallback",
    },
}
REJECTED_RELEVANCE_TESTS = {"general-topic", "incidental-product", "unverified-product"}
ATTRIBUTABLE_BRAND_RELATIONSHIPS = {
    "confirmed_paid",
    "commercial_affiliate",
    "potential_collaboration",
    "brand_attributed",
}
DIRECT_PROMOTION_STRENGTHS = {"integrated", "direct"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate report_data.json against its curation_audit.json",
    )
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument(
        "--require-full-cards",
        action="store_true",
        help="Require exactly five selected brand and creator cards per platform.",
    )
    parser.add_argument(
        "--require-min-cards",
        type=int,
        choices=range(0, 6),
        default=0,
        metavar="0-5",
        help="Require at least this many selected cards on every content page.",
    )
    parser.add_argument(
        "--require-type-coverage",
        action="store_true",
        help="Require at least three content types across each platform.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def metric_value(metric: Any) -> float:
    text = str(metric or "").strip().lower().replace(",", "")
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([kmb])?", text)
    if not match:
        return -1
    multiplier = {None: 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    return float(match.group(1)) * multiplier[match.group(2)]


def relevance_errors(
    item: dict[str, Any],
    label: str,
    *,
    selected_required: bool = True,
) -> list[str]:
    relevance = item.get("relevance")
    if not isinstance(relevance, dict):
        return [f"{label}: missing relevance object"]
    test = relevance.get("test")
    specificity = relevance.get("specificity")
    evidence = str(relevance.get("evidence") or "").strip()
    errors: list[str] = []
    accepted_test = test in RELEVANCE_TESTS
    rejected_test = test in REJECTED_RELEVANCE_TESTS
    if not accepted_test and (selected_required or not rejected_test):
        errors.append(f"{label}: unsupported relevance test {test!r}")
    allowed_specificity = (2, 3) if accepted_test or selected_required else (0, 1)
    if not isinstance(specificity, int) or specificity not in allowed_specificity:
        errors.append(f"{label}: specificity must be one of {allowed_specificity}")
    elif accepted_test and specificity < RELEVANCE_TESTS[test]:
        errors.append(f"{label}: specificity is too low for {test}")
    if len(evidence) < 20:
        errors.append(f"{label}: relevance evidence must name concrete product proof")
    return errors


def report_items(
    data: dict[str, Any], platform: str, group: str
) -> list[dict[str, Any]]:
    platform_data = data.get("platforms", {}).get(platform, {})
    key = "brand_videos" if group == "brand" else "creator_videos"
    items = platform_data.get(key, [])
    return items if isinstance(items, list) else []


def candidate_map(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("url")): item
        for item in items
        if isinstance(item, dict) and item.get("url")
    }


def is_attributable_brand_candidate(item: dict[str, Any]) -> bool:
    """Accept creator posts only when their connection to the brand is evidenced."""
    relationship = str(item.get("relationship") or "").strip()
    evidence = str(item.get("relationship_evidence") or "").strip()
    promotion_strength = str(item.get("promotion_strength") or "").strip()
    return (
        relationship in ATTRIBUTABLE_BRAND_RELATIONSHIPS
        and len(evidence) >= 20
        and promotion_strength in DIRECT_PROMOTION_STRENGTHS
    )


def validate_group(
    data: dict[str, Any],
    audit_platform: dict[str, Any],
    platform: str,
    group: str,
    *,
    require_full_cards: bool = False,
    minimum_cards: int = 0,
) -> list[str]:
    errors: list[str] = []
    pool_key = f"{group}_candidates"
    candidates = audit_platform.get(pool_key, [])
    if not isinstance(candidates, list):
        return [f"{platform}.{pool_key}: must be a list"]
    candidates = [item for item in candidates if isinstance(item, dict)]
    by_url = candidate_map(candidates)
    selected_report = report_items(data, platform, group)
    selected_urls = {str(item.get("url")) for item in selected_report}
    audited_selected = {
        str(item.get("url")) for item in candidates if item.get("selected") is True
    }
    if selected_urls != audited_selected:
        errors.append(
            f"{platform}.{group}: report URLs and audit selected URLs differ",
        )

    gap_note = str(audit_platform.get(f"{group}_gap_note") or "").strip()
    if len(candidates) < 10 and not gap_note:
        errors.append(
            f"{platform}.{group}: fewer than 10 candidates requires a gap note"
        )
    if len(selected_report) < 5 and not gap_note:
        errors.append(
            f"{platform}.{group}: fewer than 5 selections requires a gap note"
        )
    if require_full_cards and len(selected_report) != 5:
        errors.append(
            f"{platform}.{group}: requires 5 selected cards, found {len(selected_report)}"
        )
    elif minimum_cards and len(selected_report) < minimum_cards:
        errors.append(
            f"{platform}.{group}: requires at least {minimum_cards} selected cards, "
            f"found {len(selected_report)}"
        )

    creator_floor = audit_platform.get("creator_floor", 50_000)
    top_up_needed = (
        len(candidates) < 10
        or len(selected_report) < 5
        or (group == "creator" and creator_floor in (0, 1_000, 10_000))
    )
    if top_up_needed:
        top_up_key = f"{group}_top_up_complete"
        if audit_platform.get(top_up_key) is not True:
            errors.append(
                f"{platform}.{group}: underfilled pool requires {top_up_key}=true"
            )
        modes = set(audit_platform.get(f"{group}_search_modes", []))
        missing_modes = sorted(TOP_UP_SEARCH_MODES[group] - modes)
        if missing_modes:
            errors.append(
                f"{platform}.{group}: incomplete top-up search modes {missing_modes}"
            )

    for index, item in enumerate(candidates, start=1):
        label = f"{platform}.{group}[{index}]"
        errors.extend(
            relevance_errors(
                item,
                label,
                selected_required=item.get("selected") is True,
            ),
        )
        if metric_value(item.get("metric")) < 0:
            errors.append(f"{label}: metric is missing or unparsable")
        if (
            item.get("selected") is not True
            and not str(item.get("exclusion_reason") or "").strip()
        ):
            errors.append(f"{label}: rejected candidate needs exclusion_reason")
        if (
            group == "brand"
            and item.get("official_account_verified") is not True
            and not is_attributable_brand_candidate(item)
        ):
            errors.append(
                f"{label}: brand candidate is neither official nor attributable"
            )

    for index, item in enumerate(selected_report, start=1):
        label = f"report.{platform}.{group}[{index}]"
        url = str(item.get("url"))
        errors.extend(relevance_errors(item, label))
        if url not in by_url:
            errors.append(f"{label}: URL is absent from the candidate audit")
            continue
        audited_relevance = by_url[url].get("relevance")
        if item.get("relevance") != audited_relevance:
            errors.append(f"{label}: report relevance does not match audit evidence")

    handles = Counter(str(item.get("handle") or "").lower() for item in selected_report)
    if any(count > 3 for count in handles.values()):
        errors.append(
            f"{platform}.{group}: more than 3 selected videos from one account"
        )
    formats = {str(item.get("format") or "").strip() for item in selected_report}
    if len(selected_report) >= 5 and len(formats - {""}) < 3:
        errors.append(f"{platform}.{group}: 5 selections require at least 3 formats")

    if group == "creator":
        floor = creator_floor
        if floor not in (0, 1_000, 10_000, 50_000):
            errors.append(
                f"{platform}.creator_floor: must be 0, 1000, 10000, or 50000"
            )
            floor = 50_000
        if floor < 50_000 and not gap_note:
            errors.append(
                f"{platform}.creator: {floor / 1_000:g}K fallback requires a gap note"
            )
        if floor == 1_000 and audit_platform.get("creator_top_up_complete") is not True:
            errors.append(
                f"{platform}.creator: 1K fallback requires creator_top_up_complete=true"
            )
        if floor == 0 and audit_platform.get("creator_top_up_complete") is not True:
            errors.append(
                f"{platform}.creator: verified-niche fallback requires creator_top_up_complete=true"
            )
        for item in selected_report:
            if metric_value(item.get("metric")) < floor:
                errors.append(
                    f"{platform}.creator: {item.get('url')} is below the {floor:g} floor"
                )

    return errors


def validate_brand_reach(audit_platform: dict[str, Any], platform: str) -> list[str]:
    errors: list[str] = []
    modes = set(audit_platform.get("brand_search_modes", []))
    missing_modes = REQUIRED_SEARCH_MODES - modes
    if missing_modes:
        errors.append(f"{platform}.brand: missing search modes {sorted(missing_modes)}")
    candidates = [
        item
        for item in audit_platform.get("brand_candidates", [])
        if isinstance(item, dict)
        and not relevance_errors(item, "candidate", selected_required=True)
    ]
    if not candidates:
        return errors + [f"{platform}.brand: no eligible candidates"]
    best = max(candidates, key=lambda item: metric_value(item.get("metric")))
    if best.get("selected") is not True:
        errors.append(
            f"{platform}.brand: highest-reach eligible candidate was not selected"
        )
    distinct_handles = {str(item.get("handle") or "").lower() for item in candidates}
    gap_note = str(audit_platform.get("brand_gap_note") or "").strip()
    if len(distinct_handles - {""}) < 3 and not gap_note:
        errors.append(
            f"{platform}.brand: fewer than 3 official accounts requires a gap note"
        )
    return errors


def validate_content_type_coverage(
    data: dict[str, Any], platform: str, *, minimum_types: int = 3
) -> list[str]:
    selected = [
        item
        for group in ("brand", "creator")
        for item in report_items(data, platform, group)
    ]
    content_types = {
        content_type
        for item in selected
        if (content_type := canonical_content_type(item.get("content_type")))
    }
    if len(content_types) < minimum_types:
        return [
            f"{platform}: requires at least {minimum_types} content types across "
            f"selected cards, found {len(content_types)}"
        ]
    return []


def canonical_content_type(value: Any) -> str | None:
    text = str(value or "").strip().casefold()
    if "owned" in text or "branded ip" in text or "founder" in text:
        return "branded-owned"
    if "commercial" in text or "paid" in text or "sponsor" in text:
        return "branded-commercial"
    if "educat" in text or "tutorial" in text or "explainer" in text:
        return "educational"
    if (
        "ugc" in text
        or "testimonial" in text
        or "review" in text
        or "customer story" in text
    ):
        return "ugc-testimonial"
    return text or None


def validate(
    data: dict[str, Any],
    audit: dict[str, Any],
    *,
    require_full_cards: bool = False,
    minimum_cards: int = 0,
    require_type_coverage: bool = False,
) -> list[str]:
    errors: list[str] = []
    audit_platforms = audit.get("platforms", {})
    for platform in PLATFORMS:
        platform_audit = audit_platforms.get(platform)
        if not isinstance(platform_audit, dict):
            errors.append(f"{platform}: missing platform audit")
            continue
        errors.extend(
            validate_group(
                data,
                platform_audit,
                platform,
                "brand",
                require_full_cards=require_full_cards,
                minimum_cards=minimum_cards,
            )
        )
        errors.extend(
            validate_group(
                data,
                platform_audit,
                platform,
                "creator",
                require_full_cards=require_full_cards,
                minimum_cards=minimum_cards,
            )
        )
        errors.extend(validate_brand_reach(platform_audit, platform))
        if require_type_coverage:
            errors.extend(validate_content_type_coverage(data, platform))
    return errors


def main() -> int:
    args = parse_args()
    try:
        errors = validate(
            load_json(args.data),
            load_json(args.audit),
            require_full_cards=args.require_full_cards,
            minimum_cards=args.require_min_cards,
            require_type_coverage=args.require_type_coverage,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"Curation validation failed: {error}", file=sys.stderr)
        return 1
    if errors:
        print("Curation validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Curation validation passed for TikTok, Instagram, and YouTube.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
