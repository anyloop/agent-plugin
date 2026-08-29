"""Frozen phase registry: phase id -> script + typed argument mapping.

The registry is the security boundary that keeps research_run from being a
shell: every phase (or phase variant) maps to one fixed entry script, and
only the allow-listed, typed arguments below are translated into argv.
Unknown keys are rejected; workspace paths are resolved symlink-safe and
must stay inside the workspace. Multi-script phases select a variant via
the reserved "variant" argument (e.g. keywords: tiktok|instagram).

Inference-backed scripts authenticate through adant_agent's token-direct
transport (single sign-on) — the child process inherits PLUGIN_DATA and
ADANT_SERVER_URL from this server's environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def skills_root() -> Path:
    """Locate the packaged skills/ directory.

    The server always lives at <plugin>/local-server/src/adant_local/, so the
    sibling `skills/` two levels up from the project is correct in BOTH the
    installed cache layout and the monorepo — deriving it from the file path
    is what makes this work when the host does not export PLUGIN_ROOT to the
    server process (it usually does not).
    """
    override = os.environ.get("ADANT_SKILLS_ROOT", "").strip()
    if override:
        return Path(override)
    sibling = Path(__file__).resolve().parents[2].parent / "skills"
    if sibling.is_dir():
        return sibling
    plugin_root = (
        os.environ.get("PLUGIN_ROOT", "").strip()
        or os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    )
    if plugin_root:
        return Path(plugin_root) / "skills"
    return sibling


@dataclass(frozen=True)
class ArgSpec:
    flag: str | None  # None = positional (list -> many, str -> one)
    kind: type
    choices: tuple[str, ...] = ()
    required: bool = False
    is_path: bool = False  # resolved under the workspace


@dataclass(frozen=True)
class PhaseSpec:
    skill: str
    script: str
    args: dict[str, ArgSpec] = field(default_factory=dict)


def _browse(extra: dict[str, ArgSpec]) -> dict[str, ArgSpec]:
    return {
        "queries": ArgSpec(None, list, required=True),
        "max_results": ArgSpec("--max-results", int),
        "max_time": ArgSpec("--max-time", int),
        "output": ArgSpec("-o", str, required=True, is_path=True),
        **extra,
    }


REGISTRY: dict[str, PhaseSpec | dict[str, PhaseSpec]] = {
    # ---- platform browsing (headless Chrome) ----
    "platform-tiktok": PhaseSpec(
        "browse-tiktok-research",
        "browse.py",
        _browse(
            {
                "sort_by": ArgSpec("--sort-by", str, ("relevance", "likes", "date")),
                "time_range": ArgSpec("--time-range", str),
                "min_likes": ArgSpec("--min-likes", int),
            }
        ),
    ),
    "platform-instagram": PhaseSpec(
        "browse-instagram-reels",
        "browse.py",
        _browse({"min_views": ArgSpec("--min-views", int)}),
    ),
    "platform-meta-ads": PhaseSpec(
        "browse-meta-ads-library",
        "browse.py",
        {
            "queries": ArgSpec(None, list),
            "advertiser": ArgSpec("--advertiser", str),
            "country": ArgSpec("--country", str),
            "media_type": ArgSpec("--media-type", str),
            "platform": ArgSpec("--platform", str),
            "screenshot_dir": ArgSpec("--screenshot-dir", str, is_path=True),
            "max_results": ArgSpec("--max-results", int),
            "output": ArgSpec("-o", str, required=True, is_path=True),
        },
    ),
    "platform-youtube": PhaseSpec(
        "browse-youtube-shorts",
        "browse.py",
        _browse(
            {
                "sort_by": ArgSpec("--sort-by", str),
                "time_range": ArgSpec("--time-range", str),
                "min_views": ArgSpec("--min-views", int),
                "screenshot_dir": ArgSpec("--screenshot-dir", str, is_path=True),
            }
        ),
    ),
    # ---- inference-backed research (token-direct via adant_agent) ----
    "product-profile": PhaseSpec(
        "product-research",
        "research_product.py",
        {
            "url": ArgSpec("--url", str, required=True),
            "notes": ArgSpec("--notes", str),
            "output": ArgSpec("-o", str, required=True, is_path=True),
        },
    ),
    "competitors": PhaseSpec(
        "competitor-research",
        "research_competitors.py",
        {
            "client": ArgSpec("--client", str, required=True),
            "description": ArgSpec("--description", str, required=True),
            "website": ArgSpec("--website", str),
            "competitors": ArgSpec("--competitors", str),
            "max_competitors": ArgSpec("--max-competitors", int),
            "output": ArgSpec("-o", str, required=True, is_path=True),
        },
    ),
    "keywords": {
        "tiktok": PhaseSpec(
            "tiktok-keyword-research",
            "research_keywords.py",
            {
                "client": ArgSpec("--client", str, required=True),
                "description": ArgSpec("--description", str, required=True),
                "website": ArgSpec("--website", str),
                "competitors": ArgSpec("--competitors", str),
                "max_keywords": ArgSpec("--max-keywords", int),
                "output": ArgSpec("-o", str, required=True, is_path=True),
            },
        ),
        "instagram": PhaseSpec(
            "instagram-keyword-research",
            "research_keywords.py",
            {
                "client": ArgSpec("--client", str, required=True),
                "description": ArgSpec("--description", str, required=True),
                "website": ArgSpec("--website", str),
                "competitors": ArgSpec("--competitors", str),
                "max_keywords": ArgSpec("--max-keywords", int),
                "output": ArgSpec("-o", str, required=True, is_path=True),
            },
        ),
    },
    "curation": {
        "plan": PhaseSpec(
            "initial-social-content-research",
            "discovery_policy.py",
            {
                "data": ArgSpec("--data", str, required=True, is_path=True),
                "profile": ArgSpec("--profile", str, required=True, is_path=True),
                "competitors": ArgSpec(
                    "--competitors", str, required=True, is_path=True
                ),
                "audit": ArgSpec("--audit", str, required=True, is_path=True),
                "mined_hashtag": ArgSpec("--mined-hashtag", str),
                "target": ArgSpec("--target", int),
                "minimum": ArgSpec("--minimum", int),
                "candidate_target": ArgSpec("--candidate-target", int),
                "per_entity_limit": ArgSpec("--per-entity-limit", int),
                "batch_size": ArgSpec("--batch-size", int),
                "output": ArgSpec("-o", str, required=True, is_path=True),
            },
        ),
        "validate": PhaseSpec(
            "initial-social-content-research",
            "validate_curation.py",
            {
                "data": ArgSpec("--data", str, required=True, is_path=True),
                "audit": ArgSpec("--audit", str, required=True, is_path=True),
                "require_full_cards": ArgSpec("--require-full-cards", bool),
                "require_min_cards": ArgSpec("--require-min-cards", int),
                "require_type_coverage": ArgSpec("--require-type-coverage", bool),
            },
        ),
    },
    "report": {
        "build": PhaseSpec(
            "social-content-research-report",
            "build_deck.py",
            {
                "data": ArgSpec("--data", str, required=True, is_path=True),
                "output": ArgSpec("-o", str, required=True, is_path=True),
                "md": ArgSpec("--md", str, is_path=True),
                "strict": ArgSpec("--strict", bool),
            },
        ),
        "pdf": PhaseSpec(
            "slide-pdf-generator",
            "to_pdf.py",
            {
                "input": ArgSpec(None, str, required=True, is_path=True),
                "output": ArgSpec(None, str, required=True, is_path=True),
                "width": ArgSpec("--width", int),
                "height": ArgSpec("--height", int),
            },
        ),
    },
    "strategy": PhaseSpec(
        "trend-video-understanding",
        "understand_video.py",
        {
            "url": ArgSpec("--url", str),
            "video": ArgSpec("--video", str, is_path=True),
            "output": ArgSpec("-o", str, required=True, is_path=True),
            "context": ArgSpec("--context", str),
            "brand": ArgSpec("--brand", str),
            "model": ArgSpec("--model", str),
            "work_dir": ArgSpec("--work-dir", str, is_path=True),
            "keep_video": ArgSpec("--keep-video", bool),
            "cookies_from_browser": ArgSpec("--cookies-from-browser", str),
            "download_timeout": ArgSpec("--download-timeout", int),
        },
    ),
    "strategy-keywords": PhaseSpec(
        "content-strategy-generator",
        "mine_report_keywords.py",
        {
            "report": ArgSpec("--report", str, is_path=True),
            "videos": ArgSpec("--video", list),
            "description": ArgSpec("--description", str),
            "profile": ArgSpec("--profile", str, is_path=True),
            "captions_from": ArgSpec("--captions-from", list, is_path=True),
            "product_name": ArgSpec("--product-name", str, required=True),
            "niche": ArgSpec("--niche", str, required=True),
            "base_keywords": ArgSpec("--base-keywords", str, is_path=True),
            "output": ArgSpec("-o", str, required=True, is_path=True),
        },
    ),
    "content-strategies": PhaseSpec(
        "content-strategy-generator",
        "generate_strategies.py",
        {
            "report": ArgSpec("--report", str, is_path=True),
            "product_description": ArgSpec("--product-description", str),
            "candidates": ArgSpec("--candidates", str, required=True, is_path=True),
            "product_name": ArgSpec("--product-name", str, required=True),
            "product_url": ArgSpec("--product-url", str, required=True),
            "history": ArgSpec("--history", str, is_path=True),
            "history_out": ArgSpec("--history-out", str, is_path=True),
            "count": ArgSpec("--count", int),
            "output": ArgSpec("-o", str, required=True, is_path=True),
        },
    ),
}

LOGIN_PLATFORMS = {
    "tiktok": "browse-tiktok-research",
    "instagram": "browse-instagram-reels",
}


class PhaseArgError(ValueError):
    pass


def _workspace_path(workspace: Path, value: str) -> str:
    workspace = workspace.resolve()
    path = (
        (workspace / value).resolve()
        if not value.startswith("/")
        else Path(value).resolve()
    )
    if workspace not in path.parents and path != workspace:
        raise PhaseArgError(f"path escapes the workspace: {value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def runtime_dir(spec: PhaseSpec) -> Path:
    return skills_root() / spec.skill / "runtime"


def resolve_spec(phase_id: str, args: dict) -> PhaseSpec:
    entry = REGISTRY.get(phase_id)
    if entry is None:
        raise KeyError(phase_id)
    if isinstance(entry, dict):
        variant = args.pop("variant", None)
        if variant is None or variant not in entry:
            raise PhaseArgError(f"{phase_id} requires 'variant' in {sorted(entry)}")
        return entry[variant]
    if "variant" in args:
        raise PhaseArgError(f"{phase_id} does not take 'variant'")
    return entry


def build_argv(phase_id: str, args: dict, workspace: Path) -> list[str]:
    args = dict(args)
    spec = resolve_spec(phase_id, args)
    unknown = set(args) - set(spec.args)
    if unknown:
        raise PhaseArgError(
            f"unknown argument(s) for {phase_id}: {', '.join(sorted(unknown))}"
        )
    for key, arg_spec in spec.args.items():
        if arg_spec.required and args.get(key) in (None, "", []):
            raise PhaseArgError(f"{phase_id} requires '{key}'")
    if phase_id == "strategy" and not (args.get("url") or args.get("video")):
        raise PhaseArgError("strategy requires 'url' or 'video'")
    project = runtime_dir(spec)
    argv: list[str] = [
        "uv",
        "run",
        "--project",
        str(project),
        str(project / spec.script),
    ]

    def render(key: str, arg_spec: ArgSpec, value) -> list[str]:
        if arg_spec.kind is bool:
            if not isinstance(value, bool):
                raise PhaseArgError(f"{key} must be a boolean")
            return [arg_spec.flag] if value else []
        if arg_spec.kind is int:
            if not isinstance(value, int) or isinstance(value, bool):
                raise PhaseArgError(f"{key} must be an integer")
            rendered = str(value)
        elif arg_spec.kind is list:
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                raise PhaseArgError(f"{key} must be a list of non-empty strings")
            rendered_items = [
                _workspace_path(workspace, item) if arg_spec.is_path else item
                for item in value
            ]
            if arg_spec.flag is None:
                return rendered_items
            return [part for item in rendered_items for part in (arg_spec.flag, item)]
        else:
            if not isinstance(value, str) or not value.strip():
                raise PhaseArgError(f"{key} must be a non-empty string")
            if arg_spec.choices and value not in arg_spec.choices:
                raise PhaseArgError(f"{key} must be one of {arg_spec.choices}")
            rendered = _workspace_path(workspace, value) if arg_spec.is_path else value
        return [rendered] if arg_spec.flag is None else [arg_spec.flag, rendered]

    # positionals first, in declaration order; then flagged args
    for key, arg_spec in spec.args.items():
        if arg_spec.flag is None and args.get(key) is not None:
            argv.extend(render(key, arg_spec, args[key]))
    for key, arg_spec in spec.args.items():
        if arg_spec.flag is not None and args.get(key) is not None:
            argv.extend(render(key, arg_spec, args[key]))
    return argv
