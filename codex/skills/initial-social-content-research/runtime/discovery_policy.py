"""Adaptive query expansion and card-gap planning for social research."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

PLATFORMS = ("tiktok", "instagram", "youtube")
CREATOR_FLOORS = (50_000, 10_000, 1_000, 0)
MINIMUM_PER_PAGE = 4
TARGET_PER_PAGE = 5
CANDIDATE_TARGET = 12
QUERY_BATCH_SIZE = 8
MAX_QUERIES_PER_PASS = 24
CORE_ACTIONS = ("review", "demo", "tutorial", "comparison", "setup", "test")
APP_ACTIONS = ("app", "app review", "alternative", "apps like")
CONTENT_TYPE_ACTIONS = {
    "branded-owned": ("official", "founder story", "behind the scenes"),
    "branded-commercial": ("ad", "commercial", "product demo"),
    "educational": ("tutorial", "how it works", "comparison"),
    "ugc-testimonial": ("honest review", "customer story", "before after", "results"),
}
GENERIC_HASHTAGS = {
    "#fyp",
    "#foryou",
    "#foryoupage",
    "#reels",
    "#shorts",
    "#trending",
    "#viral",
}
RELEVANT_TESTS = {
    "exact-client-product",
    "named-competitor-product",
    "product-decision-service",
    "precise-product-problem",
}
BRAND_SEARCH_MODES = (
    "official-account",
    "product-query",
    "brand-hashtag",
    "partnership-query",
    "retailer-distributor",
    "content-type-expansion",
    "indexed-fallback",
)
CREATOR_SEARCH_MODES = (
    "exact-product",
    "competitor-product",
    "product-decision",
    "precise-problem",
    "content-type-expansion",
    "mined-hashtag",
    "indexed-fallback",
)
PLATFORM_DOMAINS = {
    "tiktok": "tiktok.com",
    "instagram": "instagram.com/reel",
    "youtube": "youtube.com/shorts",
}


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(value.split()).strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def compact_hashtag(name: str) -> str:
    """Return the stable compact hashtag form of a product or brand name."""
    compact = re.sub(r"[^\w]+", "", name, flags=re.UNICODE)
    return f"#{compact}" if compact else ""


def expand_query_variants(
    name: str,
    *,
    is_app: bool = False,
    use_cases: Iterable[str] = (),
    mined_hashtags: Iterable[str] = (),
    limit: int = 24,
) -> list[str]:
    """Expand one entity into product-first, platform-native discovery queries.

    Core exact-name and hashtag queries are deliberately first so a low limit
    cannot remove the most attributable discovery modes.
    """
    cleaned = " ".join(name.split()).strip()
    if not cleaned or limit <= 0:
        return []
    values = [cleaned, compact_hashtag(cleaned)]
    values.extend(f"{cleaned} {action}" for action in CORE_ACTIONS)
    if is_app:
        values.extend(
            f"{cleaned} {action}" if action != "apps like" else f"apps like {cleaned}"
            for action in APP_ACTIONS
        )
    values.extend(f"{cleaned} {use_case}" for use_case in use_cases)
    values.extend(mined_hashtags)
    return _dedupe(values)[:limit]


def extract_hashtags(text: str, *, limit: int = 20) -> list[str]:
    """Extract distinct hashtags while preserving their first-seen spelling."""
    return _dedupe(re.findall(r"#[\w]+", text, flags=re.UNICODE))[:limit]


def mine_relevant_hashtags(
    audit: dict[str, Any], *, limit: int = 24
) -> list[str]:
    """Mine hashtags only from candidates that already pass relevance review."""
    found: list[str] = []
    for platform in audit.get("platforms", {}).values():
        if not isinstance(platform, dict):
            continue
        for pool in ("brand_candidates", "creator_candidates"):
            for item in platform.get(pool, []):
                if not isinstance(item, dict):
                    continue
                relevance = item.get("relevance")
                if not isinstance(relevance, dict):
                    continue
                if (
                    relevance.get("test") not in RELEVANT_TESTS
                    or relevance.get("specificity") not in (2, 3)
                ):
                    continue
                text = " ".join(
                    _string_values(
                        {
                            key: item.get(key)
                            for key in ("caption", "title", "description", "hashtags")
                        }
                    )
                )
                found.extend(extract_hashtags(text, limit=limit))
    return [
        tag
        for tag in _dedupe(found)
        if tag.casefold() not in GENERIC_HASHTAGS
    ][:limit]


def choose_creator_floor(
    metrics: Iterable[int | float],
    *,
    target: int = 5,
    floors: Iterable[int] = CREATOR_FLOORS,
) -> int:
    """Choose the highest engagement floor that can fill the relevant pool."""
    observed = [max(0, int(value)) for value in metrics]
    ordered = sorted({int(value) for value in floors}, reverse=True)
    if not ordered:
        raise ValueError("at least one creator floor is required")
    for floor in ordered:
        if sum(value >= floor for value in observed) >= target:
            return floor
    return ordered[-1]


def build_gap_plan(
    data: dict[str, Any],
    *,
    audit: dict[str, Any] | None = None,
    target: int = TARGET_PER_PAGE,
    minimum: int = MINIMUM_PER_PAGE,
    candidate_target: int = CANDIDATE_TARGET,
) -> list[dict[str, Any]]:
    """Describe every platform/pool that still needs report cards."""
    plan: list[dict[str, Any]] = []
    audit_platforms = (audit or {}).get("platforms", {})
    for platform in PLATFORMS:
        platform_data = data.get("platforms", {}).get(platform, {})
        platform_audit = audit_platforms.get(platform, {})
        for pool, key in (("brand", "brand_videos"), ("creator", "creator_videos")):
            count = len(platform_data.get(key, []))
            audited_candidates = platform_audit.get(f"{pool}_candidates")
            if isinstance(audited_candidates, list):
                candidate_count = len(audited_candidates)
            else:
                candidate_count = candidate_target if count >= target else count
            if count >= target and candidate_count >= candidate_target:
                continue
            search_modes = list(
                BRAND_SEARCH_MODES if pool == "brand" else CREATOR_SEARCH_MODES
            )
            plan.append(
                {
                    "platform": platform,
                    "pool": pool,
                    "current": count,
                    "target": target,
                    "minimum": minimum,
                    "missing": max(0, target - count),
                    "minimum_missing": max(0, minimum - count),
                    "delivery_blocked": count < minimum,
                    "current_candidates": candidate_count,
                    "candidate_target": candidate_target,
                    "candidate_missing": max(0, candidate_target - candidate_count),
                    "search_modes": search_modes,
                    "engagement_floors": list(CREATOR_FLOORS)
                    if pool == "creator"
                    else [],
                    "stop_condition": (
                        "Do not render below the minimum card count. Continue to the "
                        "target from the relevance-qualified candidate buffer; lower "
                        "creator reach only after every query mode is exhausted."
                    ),
                }
            )
    return plan


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in _string_values(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _string_values(child)]
    return []


def _domain_hint(website: Any) -> str:
    hostname = urlparse(str(website or "")).hostname or ""
    return hostname.removeprefix("www.")


def _canonical_content_type(value: Any) -> str | None:
    text = str(value or "").casefold()
    if "owned" in text or "branded ip" in text:
        return "branded-owned"
    if "commercial" in text or "paid" in text or "sponsor" in text:
        return "branded-commercial"
    if "educat" in text or "tutorial" in text or "explainer" in text:
        return "educational"
    if "ugc" in text or "testimonial" in text or "review" in text:
        return "ugc-testimonial"
    return None


def _missing_content_types(data: dict[str, Any], platform: str) -> list[str]:
    section = data.get("platforms", {}).get(platform, {})
    observed = {
        content_type
        for key in ("brand_videos", "creator_videos")
        for item in section.get(key, [])
        if isinstance(item, dict)
        if (content_type := _canonical_content_type(item.get("content_type")))
    }
    return [name for name in CONTENT_TYPE_ACTIONS if name not in observed]


def _query_batches(queries: list[str], *, size: int) -> list[list[str]]:
    return [queries[index : index + size] for index in range(0, len(queries), size)]


def _entity_queries(
    entity: dict[str, Any],
    *,
    is_app: bool,
    use_cases: Iterable[str],
    mined_hashtags: Iterable[str],
    limit: int,
) -> list[str]:
    name = str(entity.get("name") or "").strip()
    expanded = expand_query_variants(
        name,
        is_app=is_app,
        use_cases=use_cases,
        mined_hashtags=mined_hashtags,
        limit=limit,
    )
    domain = _domain_hint(entity.get("website"))
    if domain:
        expanded.insert(1, f'"{name}" {domain}')
    return _dedupe(expanded)[:limit]


def _mode_queries(
    gap: dict[str, Any],
    *,
    client_name: str,
    competitor_names: list[str],
    all_entities: list[dict[str, Any]],
    use_cases: list[str],
    mined_hashtags: list[str],
    is_app: bool,
    per_entity_limit: int,
    batch_size: int,
    max_queries_per_pass: int,
) -> list[dict[str, Any]]:
    """Build ordered, auditable query passes for one underfilled pool."""
    names = _dedupe(
        str(entity.get("name") or "")
        for entity in all_entities
        if entity.get("name")
    )
    compact_tags = _dedupe(compact_hashtag(name) for name in names)
    domain_queries = _dedupe(
        f'"{entity.get("name")}" {_domain_hint(entity.get("website"))}'
        for entity in all_entities
        if entity.get("name") and _domain_hint(entity.get("website"))
    )
    platform_domain = PLATFORM_DOMAINS[str(gap["platform"])]
    missing_types = gap.get("content_type_gaps") or list(CONTENT_TYPE_ACTIONS)
    if gap["pool"] == "creator":
        missing_types = [
            content_type
            for content_type in missing_types
            if content_type != "branded-owned"
        ]
        if not missing_types:
            missing_types = ["educational", "ugc-testimonial"]
    type_actions = _dedupe(
        action
        for content_type in missing_types
        for action in CONTENT_TYPE_ACTIONS.get(content_type, ())
    )

    if gap["pool"] == "brand":
        queries_by_mode = {
            "official-account": names + domain_queries,
            "product-query": [
                f"{name} {action}" for name in names for action in CORE_ACTIONS
            ],
            "brand-hashtag": compact_tags,
            "partnership-query": [
                f"{name} {action}"
                for name in names
                for action in ("review", "demo", "partner", "sponsored", "ambassador")
            ],
            "retailer-distributor": [
                f"{name} {source}"
                for name in names
                for source in ("retailer", "distributor", "stockist")
            ],
            "content-type-expansion": [
                f"{name} {action}" for name in names for action in type_actions
            ],
            "indexed-fallback": [
                f'site:{platform_domain} "{name}"' for name in names
            ],
        }
    else:
        product_names = _dedupe([client_name, *competitor_names])
        decision_seeds = _dedupe(use_cases or product_names)
        queries_by_mode = {
            "exact-product": [
                f"{client_name} {action}"
                for action in ("review", "demo", "tutorial", "test")
                if client_name
            ],
            "competitor-product": [
                f"{name} {action}"
                for name in competitor_names
                for action in ("review", "demo", "tutorial", "test")
            ],
            "product-decision": [
                f"{seed} {action}"
                for seed in decision_seeds
                for action in ("review", "comparison", "how to", "best")
            ],
            "precise-problem": _dedupe(
                [*use_cases, *(f"how to {seed}" for seed in use_cases)]
            ),
            "content-type-expansion": [
                f"{name} {action}"
                for name in product_names
                for action in type_actions
                if name
            ],
            "mined-hashtag": _dedupe([*mined_hashtags, *compact_tags]),
            "indexed-fallback": [
                f'site:{platform_domain} "{seed}"'
                for seed in _dedupe([*product_names, *use_cases])
            ],
        }
        if is_app and client_name:
            queries_by_mode["exact-product"].extend(
                (f"{client_name} app review", f"apps like {client_name}")
            )

    passes = []
    for mode in gap["search_modes"]:
        queries = _dedupe(queries_by_mode.get(mode, []))
        if not queries:
            queries = domain_queries or compact_tags or names
        all_queries = queries[: max(1, per_entity_limit * max(1, len(names)))]
        primary = all_queries[: max(1, max_queries_per_pass)]
        reserve = all_queries[len(primary) :]
        passes.append(
            {
                "mode": mode,
                "queries": primary,
                "batches": _query_batches(primary, size=max(1, batch_size)),
                "reserve_queries": reserve,
                "reserve_batches": _query_batches(reserve, size=max(1, batch_size)),
                "max_results_per_query": 20,
                "run_policy": (
                    "Run primary batches, re-curate, then run reserve batches only "
                    "while this page remains below four qualified cards."
                ),
            }
        )
    return passes


def build_query_plan(
    data: dict[str, Any],
    profile: dict[str, Any],
    competitors: dict[str, Any],
    *,
    audit: dict[str, Any] | None = None,
    mined_hashtags: Iterable[str] = (),
    target: int = TARGET_PER_PAGE,
    minimum: int = MINIMUM_PER_PAGE,
    candidate_target: int = CANDIDATE_TARGET,
    per_entity_limit: int = 12,
    batch_size: int = QUERY_BATCH_SIZE,
    max_queries_per_pass: int = MAX_QUERIES_PER_PASS,
) -> list[dict[str, Any]]:
    """Turn report gaps and research artifacts into targeted discovery queries."""
    mined_hashtag_list = _dedupe(
        [*mined_hashtags, *mine_relevant_hashtags(audit or {})]
    )
    client = {
        "name": profile.get("client_name"),
        "website": profile.get("website"),
    }
    competitor_items = competitors.get("confirmed_competitors", [])
    entities = [client] + [
        item for item in competitor_items if isinstance(item, dict) and item.get("name")
    ]
    use_cases = _string_values(profile.get("keyword_seeds"))[:12]
    broad_queries = _dedupe(
        query
        for entity in entities
        for query in _entity_queries(
            entity,
            is_app=bool(profile.get("is_app")),
            use_cases=use_cases,
            mined_hashtags=mined_hashtag_list,
            limit=per_entity_limit,
        )
    )
    plan = []
    for gap in build_gap_plan(
        data,
        audit=audit,
        target=target,
        minimum=minimum,
        candidate_target=candidate_target,
    ):
        gap["content_type_gaps"] = _missing_content_types(data, str(gap["platform"]))
        passes = _mode_queries(
            gap,
            client_name=str(client.get("name") or ""),
            competitor_names=[
                str(item.get("name"))
                for item in competitor_items
                if isinstance(item, dict) and item.get("name")
            ],
            all_entities=entities,
            use_cases=use_cases,
            mined_hashtags=mined_hashtag_list,
            is_app=bool(profile.get("is_app")),
            per_entity_limit=per_entity_limit,
            batch_size=batch_size,
            max_queries_per_pass=max_queries_per_pass,
        )
        queries = _dedupe(
            [
                *broad_queries,
                *(query for item in passes for query in item["queries"]),
                *(query for item in passes for query in item["reserve_queries"]),
            ]
        )
        plan.append({**gap, "queries": queries, "passes": passes})
    return plan


def _load_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build adaptive social-content top-up queries from report artifacts."
    )
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--competitors", required=True, type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--mined-hashtag", action="append", default=[])
    parser.add_argument("--target", type=int, default=5)
    parser.add_argument("--minimum", type=int, default=MINIMUM_PER_PAGE)
    parser.add_argument("--candidate-target", type=int, default=CANDIDATE_TARGET)
    parser.add_argument("--per-entity-limit", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=QUERY_BATCH_SIZE)
    parser.add_argument(
        "--max-queries-per-pass", type=int, default=MAX_QUERIES_PER_PASS
    )
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    plan = build_query_plan(
        _load_object(args.data),
        _load_object(args.profile),
        _load_object(args.competitors),
        audit=_load_object(args.audit) if args.audit else None,
        mined_hashtags=args.mined_hashtag,
        target=args.target,
        minimum=args.minimum,
        candidate_target=args.candidate_target,
        per_entity_limit=args.per_entity_limit,
        batch_size=args.batch_size,
        max_queries_per_pass=args.max_queries_per_pass,
    )
    rendered = json.dumps({"gaps": plan}, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
