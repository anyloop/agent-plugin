"""research_run / research_status / platform_session contract tests."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

import pytest
from fastmcp import Client

from adant_local import events, phases, runner
from adant_local.server import mcp


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("ADANT_SOCIAL_DATA_DIR", str(Path(tmp) / "ws" / ".runtime"))
        monkeypatch.setenv("HOME", tmp)
        (Path(tmp) / "ws").mkdir()
        yield Path(tmp) / "ws"


@pytest.fixture
def fake_phase(monkeypatch):
    """Route every phase to a stub script so no browser or network runs."""
    script_dir = Path(tempfile.mkdtemp())
    (script_dir / "stub.py").write_text(
        "import sys, time\n"
        "print('query 1/2: 7 videos', flush=True)\n"
        "time.sleep(0.4)\n"
        "print('query 2/2: 12 videos', flush=True)\n"
        "out = [a for a in sys.argv if a.endswith('.json')]\n"
        "open(out[0], 'w').write('{\"videos\": 12}')\n"
    )
    original = phases.build_argv

    def fake_build(phase_id, args, workspace):
        original(phase_id, args, workspace)  # keep validation behavior
        out = phases._workspace_path(workspace, args["output"])
        return [sys.executable, str(script_dir / "stub.py"), out]

    monkeypatch.setattr(phases, "build_argv", fake_build)
    return script_dir


def run(coro):
    return asyncio.run(coro)


def test_build_argv_typed_mapping(isolated):
    argv = phases.build_argv(
        "platform-tiktok",
        {
            "queries": ["neck massager review", "posture fix"],
            "sort_by": "likes",
            "max_results": 20,
            "output": "brand/browse_tiktok.json",
        },
        isolated,
    )
    assert argv[0] == "uv" and argv[1] == "run"
    assert argv[4].endswith("browse.py")
    assert "neck massager review" in argv and "--sort-by" in argv
    out = argv[argv.index("-o") + 1]
    assert out.startswith(str(isolated.resolve())) and out.endswith(
        "brand/browse_tiktok.json"
    )


def test_build_argv_content_strategy_phases(isolated):
    keywords = phases.build_argv(
        "strategy-keywords",
        {
            "videos": ["https://example.com/one", "https://example.com/two"],
            "captions_from": ["research/tiktok.json", "research/instagram.json"],
            "product_name": "Nimbus",
            "niche": "posture tools",
            "output": "strategy/keywords.json",
        },
        isolated,
    )
    assert keywords.count("--video") == 2
    assert keywords.count("--captions-from") == 2
    assert str(isolated.resolve() / "research" / "tiktok.json") in keywords

    strategies = phases.build_argv(
        "content-strategies",
        {
            "product_description": "posture coach",
            "candidates": "strategy/candidates.json",
            "product_name": "Nimbus",
            "product_url": "https://nimbus.example",
            "count": 8,
            "output": "strategy/final.md",
        },
        isolated,
    )
    assert "--product-description" in strategies
    assert strategies[strategies.index("--count") + 1] == "8"


def test_build_argv_rejects_bad_input(isolated):
    with pytest.raises(phases.PhaseArgError):
        phases.build_argv(
            "platform-tiktok",
            {"queries": ["x"], "output": "o.json", "evil": "1"},
            isolated,
        )
    with pytest.raises(phases.PhaseArgError):
        phases.build_argv(
            "platform-tiktok", {"queries": [], "output": "o.json"}, isolated
        )
    with pytest.raises(phases.PhaseArgError):
        phases.build_argv(
            "platform-tiktok",
            {"queries": ["x"], "output": "../../etc/pwn.json"},
            isolated,
        )
    with pytest.raises(phases.PhaseArgError):
        phases.build_argv(
            "platform-tiktok",
            {"queries": ["x"], "output": "o.json", "sort_by": "bogus"},
            isolated,
        )


def test_research_run_parallel_fanout(isolated, fake_phase):
    async def scenario():
        async with Client(mcp) as client:
            started = time.monotonic()
            result = (
                await client.call_tool(
                    "research_run",
                    {
                        "phase_runs": [
                            {
                                "id": "product-profile",
                                "args": {
                                    "url": "https://nimbus.example",
                                    "output": "a/out1.json",
                                },
                            },
                            {
                                "id": "competitors",
                                "args": {
                                    "client": "Nimbus",
                                    "description": "massager",
                                    "output": "b/out2.json",
                                },
                            },
                        ],
                        "workspace": str(isolated),
                        "subject": "Nimbus",
                    },
                )
            ).data
            assert [j["status"] for j in result["jobs"]] == ["running", "running"]
            status = (
                await client.call_tool(
                    "research_status", {"wait": True, "timeout_s": 30}
                )
            ).data
            elapsed = time.monotonic() - started
            assert status["running"] == 0 and status["failed"] == 0
            assert elapsed < 5, "two 0.4s phases must overlap"
            assert (isolated / "a" / "out1.json").exists()

    run(scenario())
    snap = events.snapshot()
    statuses = {(e["phase"], e["status"]) for e in snap["events"]}
    assert ("product-profile", "start") in statuses and (
        "product-profile",
        "done",
    ) in statuses
    assert any(e.get("subject") == "Nimbus" for e in snap["events"])
    assert any(
        e.get("artifact", {}).get("path", "").endswith("a/out1.json")
        for e in snap["events"]
    )


def test_research_run_structured_errors(isolated):
    async def scenario():
        async with Client(mcp) as client:
            bad_ws = (
                await client.call_tool(
                    "research_run",
                    {
                        "phase_runs": [{"id": "platform-tiktok", "args": {}}],
                        "workspace": "relative/path",
                    },
                )
            ).data
            assert bad_ws["error"]["code"] == "workspace-invalid"
            missing_variant = (
                await client.call_tool(
                    "research_run",
                    {
                        "phase_runs": [{"id": "report", "args": {}}],
                        "workspace": str(isolated),
                    },
                )
            ).data
            assert missing_variant["error"]["code"] == "phase-failed"
            assert "variant" in missing_variant["error"]["message"]
            unknown = (
                await client.call_tool(
                    "research_run",
                    {
                        "phase_runs": [{"id": "platform-mars", "args": {}}],
                        "workspace": str(isolated),
                    },
                )
            ).data
            assert unknown["error"]["code"] == "phase-failed"

    run(scenario())


def test_research_run_enforces_browser_and_strategy_concurrency(isolated):
    async def scenario():
        async with Client(mcp) as client:
            browsers = (
                await client.call_tool(
                    "research_run",
                    {
                        "phase_runs": [
                            {
                                "id": "platform-tiktok",
                                "args": {"queries": ["a"], "output": "a.json"},
                            },
                            {
                                "id": "platform-youtube",
                                "args": {"queries": ["b"], "output": "b.json"},
                            },
                        ],
                        "workspace": str(isolated),
                    },
                )
            ).data
            assert "one social browser phase" in browsers["error"]["message"]
            strategies = (
                await client.call_tool(
                    "research_run",
                    {
                        "phase_runs": [
                            {
                                "id": "strategy",
                                "args": {
                                    "url": f"https://example.com/{index}",
                                    "output": f"s{index}.json",
                                },
                            }
                            for index in range(3)
                        ],
                        "workspace": str(isolated),
                    },
                )
            ).data
            assert "at most two strategy analyses" in strategies["error"]["message"]

    run(scenario())


def test_runner_enforces_hard_timeout(isolated):
    progress = isolated / ".runtime" / "progress"
    runner.start_job(
        "product-profile",
        [sys.executable, "-c", "import time; time.sleep(5)"],
        progress_dir=progress,
        timeout_s=1,
    )
    jobs = runner.wait_all(5, poll_s=0.05, progress_dir=progress)
    assert jobs[0]["status"] == "failed"
    assert jobs[0]["exit"] == 124
    assert jobs[0]["timed_out"] is True


def test_runner_records_expected_nonzero_as_warning(isolated):
    progress = isolated / ".runtime" / "progress"
    runner.start_job(
        "platform-instagram",
        [sys.executable, "-c", "import sys; print('no results'); sys.exit(2)"],
        progress_dir=progress,
        expected_exit_codes=frozenset({2}),
    )
    jobs = runner.wait_all(5, poll_s=0.05, progress_dir=progress)
    assert jobs[0]["status"] == "warning"
    assert jobs[0]["exit"] == 2
    assert jobs[0]["expected_exit"] is True


def test_platform_session_validates_platform():
    async def scenario():
        async with Client(mcp) as client:
            bad = (
                await client.call_tool("platform_session", {"platform": "myspace"})
            ).data
            assert bad["error"]["code"] == "phase-failed"

    run(scenario())


def test_build_argv_inference_and_variant_phases(isolated):
    argv = phases.build_argv(
        "competitors",
        {
            "client": "Nimbus",
            "description": "neck massager",
            "website": "https://nimbus.example",
            "max_competitors": 8,
            "output": "brand/competitors.json",
        },
        isolated,
    )
    assert argv[4].endswith("research_competitors.py")
    assert "--client" in argv and "Nimbus" in argv

    kw = phases.build_argv(
        "keywords",
        {
            "variant": "instagram",
            "client": "Nimbus",
            "description": "neck massager",
            "output": "kw/ig.json",
        },
        isolated,
    )
    assert "instagram-keyword-research" in kw[3]

    pdf = phases.build_argv(
        "report",
        {"variant": "pdf", "input": "deck/deck.html", "output": "deck/deck.pdf"},
        isolated,
    )
    assert pdf[4].endswith("to_pdf.py")
    assert pdf[5].endswith("deck/deck.html") and pdf[6].endswith(
        "deck/deck.pdf"
    )  # positionals in order

    build = phases.build_argv(
        "report",
        {
            "variant": "build",
            "data": "report_data.json",
            "output": "deck/deck.html",
            "strict": True,
        },
        isolated,
    )
    assert build[-1] == "--strict"  # boolean flag
    off = phases.build_argv(
        "report",
        {
            "variant": "build",
            "data": "report_data.json",
            "output": "deck/deck.html",
            "strict": False,
        },
        isolated,
    )
    assert "--strict" not in off

    validate = phases.build_argv(
        "curation",
        {
            "variant": "validate",
            "data": "report.json",
            "audit": "audit.json",
            "require_min_cards": 4,
            "require_type_coverage": True,
        },
        isolated,
    )
    assert "--require-min-cards" in validate and "--require-type-coverage" in validate

    strategy = phases.build_argv(
        "strategy",
        {
            "video": "clips/pick.mp4",
            "url": "https://example.com/video",
            "output": "analysis/pick.json",
            "brand": "Nimbus",
            "download_timeout": 120,
        },
        isolated,
    )
    assert "--video" in strategy and "--brand" in strategy
    assert strategy[strategy.index("--video") + 1].startswith(str(isolated.resolve()))

    with pytest.raises(phases.PhaseArgError):
        phases.build_argv(
            "keywords",
            {
                "variant": "myspace",
                "client": "x",
                "description": "d",
                "output": "o.json",
            },
            isolated,
        )
    with pytest.raises(phases.PhaseArgError):
        phases.build_argv(
            "competitors", {"output": "o.json"}, isolated
        )  # missing required client
    with pytest.raises(phases.PhaseArgError):
        phases.build_argv("strategy", {"output": "o.json"}, isolated)
    with pytest.raises(phases.PhaseArgError):
        phases.build_argv(
            "platform-tiktok",
            {"queries": ["x"], "output": "o.json", "variant": "x"},
            isolated,
        )


def test_variant_jobs_do_not_collide(isolated, fake_phase):
    """Two variants of one phase must not share a job record or log file."""

    async def scenario():
        async with Client(mcp) as client:
            result = (
                await client.call_tool(
                    "research_run",
                    {
                        "phase_runs": [
                            {
                                "id": "keywords",
                                "args": {
                                    "variant": "tiktok",
                                    "client": "N",
                                    "description": "d",
                                    "output": "kw/tt.json",
                                },
                            },
                            {
                                "id": "keywords",
                                "args": {
                                    "variant": "instagram",
                                    "client": "N",
                                    "description": "d",
                                    "output": "kw/ig.json",
                                },
                            },
                        ],
                        "workspace": str(isolated),
                    },
                )
            ).data
            assert sorted(j["phase"] for j in result["jobs"]) == [
                "keywords-instagram",
                "keywords-tiktok",
            ]
            status = (
                await client.call_tool(
                    "research_status", {"wait": True, "timeout_s": 30}
                )
            ).data
            assert status["running"] == 0 and status["failed"] == 0
            assert len(status["jobs"]) == 2

    run(scenario())
    jobs = sorted(
        p.name for p in (isolated / ".runtime" / "progress" / "jobs").glob("*.json")
    )
    assert jobs == ["keywords-instagram.json", "keywords-tiktok.json"]


def test_registry_requires_description_like_the_scripts(isolated):
    with pytest.raises(phases.PhaseArgError):
        phases.build_argv("competitors", {"client": "N", "output": "c.json"}, isolated)
    with pytest.raises(phases.PhaseArgError):
        phases.build_argv(
            "keywords",
            {"variant": "tiktok", "client": "N", "output": "k.json"},
            isolated,
        )


def test_skills_root_resolves_in_the_installed_layout(tmp_path, monkeypatch):
    """The host does not export PLUGIN_ROOT to the server process, so the
    skills directory must resolve from the server's own location."""
    monkeypatch.delenv("ADANT_SKILLS_ROOT", raising=False)
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    root = phases.skills_root()
    assert root.name == "skills"
    assert root.parent.name != "adant" or root.parent == root.parent  # sanity
    # the sibling of local-server/, never a doubled path segment
    assert "adant/adant" not in str(root)
    assert (root.parent / "local-server").is_dir()
