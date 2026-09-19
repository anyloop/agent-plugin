"""Recommend the brand's hashtag sets from the research artifacts.

The order is the point: competitors first, then the niche keywords, then the
brand's own tags — the same evidence the discovery ran on, folded into the
tags a post should carry. Every set is at most `--max-per-post` tags (five by
default) and always leads with a brand tag; feed tags (#fyp, #viral) never
appear. Stdlib only, like the rest of this runtime.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

from discovery_policy import GENERIC_HASHTAGS, compact_hashtag, mine_relevant_hashtags

MAX_PER_POST = 5
MAX_TAG_LENGTH = 24
PLATFORM_LIMITS = {"tiktok": MAX_PER_POST, "instagram": MAX_PER_POST, "youtube": 3}
FEED_TAGS = {
    tag.casefold()
    for tag in (
        *GENERIC_HASHTAGS,
        "#fypage",
        "#fypシ",
        "#foryourpage",
        "#viralvideo",
        "#trend",
        "#explore",
        "#explorepage",
        "#tiktok",
        "#instagram",
        "#youtube",
        "#youtubeshorts",
        "#reel",
        "#short",
        "#xyzbca",
        "#capcut",
    )
}
# Words that make a keyword a search phrase rather than a tag.
STOP_WORDS = {"a", "an", "and", "app", "apps", "best", "for", "how", "of", "the", "to", "vs", "with"}


def _tag(value: str, *, keep_stop_words: bool = False) -> str:
    """One hashtag from a keyword, a name, or a tag: lowercase, compact, no stop words."""
    text = str(value or "").strip().lstrip("#")
    words = [w for w in re.split(r"[\s_\-]+", text) if w]
    kept = words if keep_stop_words else ([w for w in words if w.casefold() not in STOP_WORDS] or words)
    tag = compact_hashtag(" ".join(kept)).casefold()
    if not tag or len(tag) > MAX_TAG_LENGTH + 1 or tag in FEED_TAGS:
        return ""
    return tag


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _tags(values: Iterable[Any]) -> list[str]:
    return _dedupe(_tag(str(v)) for v in values if isinstance(v, str))


def brand_tags(profile: dict[str, Any]) -> list[str]:
    """The brand's own tags: the client name, and its 'app' form when the product is an app."""
    name = str(profile.get("client_name") or "").strip()
    if not name:
        return []
    plain = _tag(name, keep_stop_words=True)
    if not profile.get("is_app"):
        return _dedupe([plain])
    # An app's plain name is often a common word (#spark, #mint); the app form leads.
    return _dedupe([_tag(f"{name} app", keep_stop_words=True), plain])[:2]


def competitor_tags(competitors: dict[str, Any], keywords: list[dict[str, Any]]) -> list[str]:
    """Direct competitors first, then the keyword research's competitor names."""
    ranked: list[tuple[int, str]] = []
    for entry in competitors.get("competitors", []) or []:
        if not isinstance(entry, dict) or not entry.get("name"):
            continue
        tier = str(entry.get("tier") or "")
        rank = {"direct": 0, "partial_overlap": 1}.get(tier, 2)
        ranked.append((rank, str(entry["name"])))
    names = [name for _, name in sorted(ranked, key=lambda item: item[0])]
    for result in keywords:
        names.extend(
            str(kw)
            for kw in (result.get("keyword_categories", {}) or {}).get("competitor", []) or []
            if isinstance(kw, str) and not re.search(r"\b(review|alternative|vs)\b", kw, re.I)
        )
    return _tags(names)


def niche_tags(
    profile: dict[str, Any], keywords: list[dict[str, Any]], observed: list[str]
) -> list[str]:
    """Niche keywords as tags, the ones the relevant winning posts already carry first."""
    candidates: list[str] = []
    for result in keywords:
        categories = result.get("keyword_categories", {}) or {}
        candidates.extend(str(kw) for kw in categories.get("niche", []) or [] if isinstance(kw, str))
    for result in keywords:
        categories = result.get("keyword_categories", {}) or {}
        candidates.extend(str(kw) for kw in categories.get("hook", []) or [] if isinstance(kw, str))
    candidates.extend(str(kw) for kw in profile.get("keyword_seeds", []) or [] if isinstance(kw, str))
    tags = _tags(candidates)
    seen_on_winners = set(observed)
    return [tag for tag in tags if tag in seen_on_winners] + [
        tag for tag in tags if tag not in seen_on_winners
    ]


def community_tags(keywords: list[dict[str, Any]]) -> list[str]:
    """Community tags (#fintok, #booktok): one per post at most, never a feed tag."""
    values: list[str] = []
    for result in keywords:
        values.extend(str(kw) for kw in result.get("tiktok_native_keywords", []) or [] if isinstance(kw, str))
        categories = result.get("keyword_categories", {}) or {}
        values.extend(str(kw) for kw in categories.get("tiktok_native", []) or [] if isinstance(kw, str))
    return _tags(values)


def observed_tags(audit: dict[str, Any] | None) -> list[str]:
    """Hashtags the relevant, already-curated posts carried — evidence, not invention."""
    if not audit:
        return []
    return _tags(mine_relevant_hashtags(audit, limit=40))


def compose_set(
    pools: dict[str, list[str]], *, limit: int, competitor_first: bool = False
) -> list[str]:
    """One post's set: the brand tag first, then niche tags, one competitor tag, one community tag.

    The competitor-first variant is for a post that competes for a rival's
    audience (a comparison, a switch story): two competitor tags, then niche.
    """
    brand = pools["brand"][:1]
    competitor = pools["competitor"][:2] if competitor_first else pools["competitor"][:1]
    if limit < 3:
        competitor = []
    community = pools["community"][:1] if limit >= 4 else []
    room = max(limit - len(brand) - len(competitor) - len(community), 1)
    niche = pools["niche"][:room]
    ordered = [*brand, *competitor, *niche, *community] if competitor_first else [*brand, *niche, *competitor, *community]
    chosen = _dedupe(ordered)[:limit]
    if len(chosen) < limit:
        return _dedupe([*chosen, *pools["niche"], *pools["brand"][1:], *pools["observed"]])[:limit]
    return chosen


def build_pools(
    profile: dict[str, Any],
    competitors: dict[str, Any],
    keywords: list[dict[str, Any]],
    audit: dict[str, Any] | None,
) -> dict[str, list[str]]:
    """The ranked tag pools, each tag in exactly one pool (brand wins, then competitor)."""
    observed = observed_tags(audit)
    brand = brand_tags(profile)
    taken = set(brand)
    competitor = [t for t in competitor_tags(competitors, keywords) if t not in taken]
    taken = taken | set(competitor)
    niche = [t for t in niche_tags(profile, keywords, observed) if t not in taken]
    community = [t for t in community_tags(keywords) if t not in taken]
    return {
        "brand": brand,
        "competitor": competitor,
        "niche": niche,
        "community": community,
        "observed": observed,
    }


def recommend(
    profile: dict[str, Any],
    competitors: dict[str, Any],
    keywords: list[dict[str, Any]],
    audit: dict[str, Any] | None = None,
    *,
    max_per_post: int = MAX_PER_POST,
) -> dict[str, Any]:
    pools = build_pools(profile, competitors, keywords, audit)
    sets = {
        platform: {
            "default": compose_set(pools, limit=min(max_per_post, platform_limit)),
            "competitor": compose_set(
                pools, limit=min(max_per_post, platform_limit), competitor_first=True
            ),
        }
        for platform, platform_limit in PLATFORM_LIMITS.items()
    }
    return {
        "client": profile.get("client_name"),
        "max_per_post": max_per_post,
        "rules": [
            f"at most {max_per_post} hashtags per post",
            "always one brand tag, first",
            "niche keyword tags carry the subject; one community tag at most",
            "a competitor tag only on a post that competes for that audience",
            "never a feed tag (#fyp, #viral, #foryou)",
        ],
        "pools": pools,
        "sets": sets,
        "evidence": {
            "competitors": len(competitors.get("competitors", []) or []),
            "keyword_results": len(keywords),
            "observed_on_relevant_posts": len(pools["observed"]),
        },
    }


def _load(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend brand, niche and competitor hashtag sets")
    parser.add_argument("--profile", required=True, help="product_profile.json")
    parser.add_argument("--competitors", required=True, help="competitors_research.json")
    parser.add_argument("--keywords", action="append", default=[], help="keywords_<platform>.json (repeatable)")
    parser.add_argument("--audit", help="curation audit.json — mines the relevant posts' own hashtags")
    parser.add_argument("--max-per-post", type=int, default=MAX_PER_POST)
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    result = recommend(
        _load(args.profile),
        _load(args.competitors),
        [_load(path) for path in args.keywords],
        _load(args.audit) or None,
        max_per_post=max(1, min(args.max_per_post, MAX_PER_POST)),
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Recommended hashtags for {result['client']}: {' '.join(result['sets']['tiktok']['default'])}")


if __name__ == "__main__":
    main()
