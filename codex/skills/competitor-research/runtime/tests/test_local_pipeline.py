from __future__ import annotations

import sys
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
