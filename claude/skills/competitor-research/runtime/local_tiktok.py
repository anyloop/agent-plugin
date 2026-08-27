"""Local TikTok presence research built on the plugin's Chrome CDP runtime."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


_runtime_dir = Path(__file__).resolve().parent
_plugin_root = _runtime_dir.parent.parent.parent
_browse_runtime = _plugin_root / "skills" / "browse-tiktok-research" / "runtime"
_browse_script = _browse_runtime / "browse.py"
_GENERIC_WORDS = {
    "ai",
    "app",
    "co",
    "company",
    "get",
    "hq",
    "inc",
    "official",
    "the",
    "try",
    "use",
}


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 1 and token not in _GENERIC_WORDS
    }


def _website_label(website: str) -> str:
    try:
        host = urlparse(website).hostname or ""
        return host.removeprefix("www.").split(".")[0]
    except ValueError:
        return ""


def _handle_score(entity: dict, handle: str) -> int:
    clean_handle = _normalized(handle)
    if not clean_handle:
        return 0
    names = [
        str(entity.get("name", "")),
        _website_label(str(entity.get("website", ""))),
    ]
    score = 0
    for name in names:
        clean_name = _normalized(name)
        if not clean_name:
            continue
        if clean_handle == clean_name:
            score = max(score, 8)
        elif clean_name in clean_handle or clean_handle in clean_name:
            score = max(score, 5)
        overlap = len(_tokens(name) & _tokens(handle))
        score = max(score, overlap * 3)
    return score


def _integer(value: object) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def _presence_level(followers: int, videos: int, likes: int) -> str:
    if followers >= 1_000 and videos >= 10 and likes > followers:
        return "strong"
    if followers >= 500 or likes >= 1_000:
        return "medium"
    if videos >= 3 or followers >= 10:
        return "weak"
    if videos > 0 or followers > 0:
        return "minimal"
    return "none"


def _run_local_browse(entities: list[dict], max_time: int) -> dict:
    if not _browse_script.exists():
        raise RuntimeError(f"Local TikTok runtime is missing: {_browse_script}")
    queries = [f"{entity['name']} official" for entity in entities]
    with tempfile.TemporaryDirectory(prefix="adant-tiktok-") as temp_dir:
        output = Path(temp_dir) / "results.json"
        command = [
            "uv",
            "run",
            "--project",
            str(_browse_runtime),
            str(_browse_script),
            *queries,
            "--max-results",
            "3",
            "--min-likes",
            "0",
            "--no-outliers",
            "--max-time",
            str(max_time),
            "--output",
            str(output),
        ]
        try:
            subprocess.run(command, check=True, timeout=max_time + 60)
        except FileNotFoundError as exc:
            raise RuntimeError("uv is required for local TikTok research.") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Local TikTok research exceeded its time limit."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Local TikTok research failed with exit code {exc.returncode}."
            ) from exc
        return json.loads(output.read_text())


def _entity_presence(entity: dict, videos: list[dict]) -> dict:
    candidates: dict[str, list[dict]] = {}
    for video in videos:
        handle = str(video.get("uploader", "")).lstrip("@")
        if _handle_score(entity, handle) >= 3:
            candidates.setdefault(handle, []).append(video)

    if not candidates:
        return {
            "name": entity["name"],
            "tiktok_handle": None,
            "has_tiktok": False,
            "followers": 0,
            "total_likes": 0,
            "videos": 0,
            "bio": "",
            "bio_link": None,
            "is_official_account": False,
            "presence_level": "none",
            "content_strategy": "",
            "notable_videos": [],
            "notes": "No matching account found in the bounded local TikTok search.",
            "also_checked": sorted(
                {
                    f"@{str(v.get('uploader', '')).lstrip('@')}"
                    for v in videos
                    if v.get("uploader")
                }
            ),
        }

    handle, matches = max(
        candidates.items(),
        key=lambda item: (
            _handle_score(entity, item[0]),
            sum(_integer(v.get("like_count")) for v in item[1]),
        ),
    )
    match_score = _handle_score(entity, handle)
    followers = max((_integer(v.get("follower_count")) for v in matches), default=0)
    total_likes = max(
        (_integer(v.get("author_total_likes")) for v in matches), default=0
    )
    video_count = max(
        (_integer(v.get("author_video_count")) for v in matches), default=len(matches)
    )
    notable = []
    for video in sorted(
        matches, key=lambda v: _integer(v.get("view_count")), reverse=True
    )[:3]:
        notable.append(
            {
                "url": video.get("url", ""),
                "description": str(video.get("title", ""))[:180],
                "views": _integer(video.get("view_count")),
                "format": "other",
            }
        )
    hashtags = []
    for video in matches:
        hashtags.extend(str(tag) for tag in video.get("hashtags", []) if tag)
    strategy = "Recent brand videos found locally."
    if hashtags:
        strategy = f"Recent videos commonly use: {', '.join(list(dict.fromkeys(hashtags))[:5])}."
    return {
        "name": entity["name"],
        "tiktok_handle": f"@{handle}",
        "has_tiktok": True,
        "followers": followers,
        "total_likes": total_likes,
        "videos": video_count,
        "bio": "",
        "bio_link": None,
        "is_official_account": match_score >= 8,
        "presence_level": _presence_level(followers, video_count, total_likes),
        "content_strategy": strategy,
        "notable_videos": notable,
        "notes": "Matched from a local TikTok search using the brand name/domain; verify the website social link for identity-critical use.",
        "also_checked": sorted(f"@{candidate}" for candidate in candidates),
    }


def research_tiktok_presence(
    client: str,
    competitors: list[dict],
    client_description: str = "",
    client_website: str = "",
    max_time: int = 300,
) -> dict:
    """Research bounded TikTok presence entirely on the user's computer."""
    del client_description
    entities = [{"name": client, "website": client_website}, *competitors]
    print("  Phase 2: Browsing TikTok locally in the plugin research browser...")
    raw = _run_local_browse(entities, max_time)
    all_results = raw.get("all_results", {})
    presences = [
        _entity_presence(entity, all_results.get(f"{entity['name']} official", []))
        for entity in entities
    ]
    client_presence, competitor_presences = presences[0], presences[1:]
    meaningful = [
        p for p in competitor_presences if p["presence_level"] in {"strong", "medium"}
    ]
    empty_accounts = [
        p for p in competitor_presences if p["has_tiktok"] and p["videos"] <= 2
    ]
    missing = [p for p in competitor_presences if not p["has_tiktok"]]
    ranking = sorted(
        [p for p in competitor_presences if p["has_tiktok"]],
        key=lambda p: (p["followers"], p["total_likes"], p["videos"]),
        reverse=True,
    )
    strongest = ranking[0]["name"] if ranking else None
    sources = [
        {"url": video.get("url"), "title": video.get("title", "TikTok video")}
        for videos in all_results.values()
        for video in videos
        if video.get("url")
    ]
    return {
        "research_date": date.today().isoformat(),
        "execution_location": "local",
        "client": client_presence,
        "competitors": competitor_presences,
        "summary": {
            "total_analyzed": len(competitor_presences),
            "with_meaningful_presence": len(meaningful),
            "with_account_no_content": len(empty_accounts),
            "no_account": len(missing),
            "strongest_competitor": strongest,
            "key_insight": "TikTok presence was measured from a bounded local browser capture; missing accounts should be treated as not found, not proven absent.",
        },
        "presence_ranking": [
            {
                "rank": index,
                "name": p["name"],
                "handle": p["tiktok_handle"],
                "followers": p["followers"],
                "total_likes": p["total_likes"],
                "videos": p["videos"],
                "level": p["presence_level"],
            }
            for index, p in enumerate(ranking, start=1)
        ],
        "tiktok_research_sources": sources[:50],
    }
