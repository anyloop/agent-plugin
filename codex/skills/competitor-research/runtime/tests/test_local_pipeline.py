from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RUNTIME = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME))

import local_report  # noqa: E402
import local_tiktok  # noqa: E402
import research_competitors  # noqa: E402


class CompetitorResearchTests(unittest.TestCase):
    def test_phase_one_enforces_limit_and_records_execution_split(self):
        response = {
            "client": "Client",
            "competitors": [
                {
                    "name": "Partial",
                    "tier": "partial_overlap",
                    "overlap_count": 1,
                    "capability_overlap": ["A"],
                },
                {
                    "name": "Direct",
                    "tier": "direct",
                    "overlap_count": 9,
                    "capability_overlap": ["A", "B"],
                },
            ],
            "competitive_landscape_summary": {},
        }
        with patch.object(
            research_competitors, "_call_adant_json", return_value=(response, [])
        ) as call_adant:
            result = research_competitors.research_competitors(
                "Client", "Description", "", [], max_competitors=1
            )
        self.assertEqual([item["name"] for item in result["competitors"]], ["Direct"])
        self.assertEqual(result["competitors"][0]["overlap_count"], 2)
        self.assertEqual(result["execution"]["computer_policy"], "local-only")
        self.assertIn(
            "Do not invoke workspace, shell, computer",
            call_adant.call_args.args[0],
        )

    def test_tiktok_capture_maps_local_results_without_remote_inference(self):
        capture = {
            "all_results": {
                "Client official": [],
                "Acme AI official": [
                    {
                        "uploader": "acmeai",
                        "url": "https://www.tiktok.com/@acmeai/video/1",
                        "title": "Demo #ai",
                        "follower_count": 1200,
                        "author_total_likes": 5000,
                        "author_video_count": 20,
                        "view_count": 15000,
                        "hashtags": ["#ai"],
                    }
                ],
            }
        }
        with patch.object(local_tiktok, "_run_local_browse", return_value=capture):
            result = local_tiktok.research_tiktok_presence(
                "Client", [{"name": "Acme AI", "website": "https://acme.ai"}]
            )
        self.assertEqual(result["execution_location"], "local")
        self.assertEqual(result["competitors"][0]["tiktok_handle"], "@acmeai")
        self.assertEqual(result["competitors"][0]["presence_level"], "strong")
        self.assertEqual(result["browser_backend"], "chrome_cdp")

    def test_codex_browser_capture_is_shaped_without_launching_chrome(self):
        capture = {
            "all_results": {
                "Client official": [],
                "Acme AI official": [
                    {
                        "uploader": "acmeai",
                        "url": "https://www.tiktok.com/@acmeai/video/1",
                        "title": "Product demo",
                        "follower_count": 800,
                        "author_total_likes": 2000,
                        "author_video_count": 8,
                        "view_count": 9000,
                    }
                ],
            }
        }
        with patch.object(
            local_tiktok,
            "_run_local_browse",
            side_effect=AssertionError("Chrome fallback should not run"),
        ):
            result = local_tiktok.research_tiktok_presence_from_capture(
                "Client",
                [{"name": "Acme AI", "website": "https://acme.ai"}],
                capture,
                browser_backend="codex_in_app",
            )
        self.assertEqual(result["execution_location"], "local")
        self.assertEqual(result["browser_backend"], "codex_in_app")
        self.assertEqual(result["competitors"][0]["tiktok_handle"], "@acmeai")

    def test_resume_uses_browser_capture_without_repeating_phase_one(self):
        phase_one = {
            "client": "Client",
            "competitors": [
                {"name": "Acme AI", "website": "https://acme.ai", "tier": "direct"}
            ],
            "competitive_landscape_summary": {},
        }
        capture = {"all_results": {"Client official": [], "Acme AI official": []}}
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            phase_one_path = root / "competitors.json"
            capture_path = root / "capture.json"
            output_path = root / "merged.json"
            phase_one_path.write_text(json.dumps(phase_one))
            capture_path.write_text(json.dumps(capture))
            argv = [
                "research_competitors.py",
                "--input",
                str(phase_one_path),
                "--tiktok-input",
                str(capture_path),
                "-o",
                str(output_path),
            ]
            with (
                patch.object(sys, "argv", argv),
                patch.object(
                    research_competitors,
                    "research_competitors",
                    side_effect=AssertionError("Phase 1 should not run"),
                ),
                patch.object(
                    local_tiktok,
                    "_run_local_browse",
                    side_effect=AssertionError("Chrome fallback should not run"),
                ),
            ):
                research_competitors.main()
            result = json.loads(output_path.read_text())
        self.assertEqual(result["tiktok_presence"]["browser_backend"], "codex_in_app")

    def test_report_is_rendered_locally_from_supplied_data(self):
        report = local_report.generate_report(
            "Client",
            {
                "category": "Research software",
                "core_problem": "slow customer insight",
                "competitors": [],
                "competitive_landscape_summary": {"key_insight": "A growing category"},
            },
            None,
        )
        self.assertIn("# Competitor Analysis Report", report)
        self.assertIn("instructed to use web research only", report)


if __name__ == "__main__":
    unittest.main()
