"""Tests for the bounded strategy-analysis queue."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))

import strategy_queue  # noqa: E402


class StrategyQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def candidate(self, candidate_id: str, outcome: str, delay: float) -> dict:
        return {
            "id": candidate_id,
            "label": f"Candidate {candidate_id}",
            "url": f"https://example.com/{candidate_id}",
            "video_path": None,
            "output_path": self.root / f"{candidate_id}.json",
            "work_dir_path": None,
            "context": "",
            "test_outcome": outcome,
            "test_delay": delay,
        }

    @staticmethod
    def command(candidate: dict, _timeout_seconds: float) -> list[str]:
        payload = (
            {"status": "ok", "fingerprint": {"hook": "ready"}}
            if candidate["test_outcome"] == "ok"
            else {"status": "download_failed", "error": "blocked"}
        )
        script = (
            "import json,sys,time;"
            "time.sleep(float(sys.argv[2]));"
            "open(sys.argv[1],'w').write(json.dumps(json.loads(sys.argv[3])))"
        )
        return [
            sys.executable,
            "-c",
            script,
            str(candidate["output_path"]),
            str(candidate["test_delay"]),
            json.dumps(payload),
        ]

    def test_failed_primary_promotes_reserve_without_overlaunching(self) -> None:
        candidates = [
            self.candidate("1", "failed", 0.02),
            self.candidate("2", "ok", 0.08),
            self.candidate("3", "ok", 0.02),
            self.candidate("4", "ok", 0.02),
        ]

        exit_code, summary = strategy_queue.run_queue(
            candidates,
            target_successes=2,
            concurrency=2,
            timeout_seconds=2,
            poll_seconds=0.005,
            command_factory=self.command,
            emit_events=False,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual([item["id"] for item in summary["successes"]], ["2", "3"])
        self.assertEqual([item["id"] for item in summary["failures"]], ["1"])
        self.assertEqual(summary["not_started"], ["4"])
        self.assertFalse((self.root / "4.json").exists())

    def test_cached_success_counts_without_launching(self) -> None:
        cached = self.candidate("cached", "failed", 0.01)
        cached["output_path"].write_text(json.dumps({"status": "ok"}))
        reserve = self.candidate("reserve", "ok", 0.01)

        exit_code, summary = strategy_queue.run_queue(
            [cached, reserve],
            target_successes=1,
            concurrency=2,
            timeout_seconds=2,
            command_factory=self.command,
            emit_events=False,
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(summary["successes"][0]["cached"])
        self.assertFalse(reserve["output_path"].exists())

    def test_reports_insufficient_successes(self) -> None:
        candidates = [
            self.candidate("1", "failed", 0.01),
            self.candidate("2", "failed", 0.01),
        ]

        exit_code, summary = strategy_queue.run_queue(
            candidates,
            target_successes=2,
            concurrency=2,
            timeout_seconds=2,
            poll_seconds=0.005,
            command_factory=self.command,
            emit_events=False,
        )

        self.assertEqual(exit_code, 2)
        self.assertEqual(summary["status"], "insufficient")
        self.assertEqual(len(summary["failures"]), 2)


class ManifestTests(unittest.TestCase):
    def test_resolves_candidate_paths_relative_to_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "queue.json"
            manifest.write_text(
                json.dumps(
                    {
                        "context": "Example product",
                        "candidates": [
                            {
                                "id": "pick 1",
                                "url": "https://example.com/video",
                                "video": "downloads/video.mp4",
                                "output": "analysis/pick-1.json",
                            }
                        ],
                    }
                )
            )

            candidates, context = strategy_queue.load_candidates(manifest)

            self.assertEqual(context, "Example product")
            self.assertEqual(candidates[0]["id"], "pick-1")
            self.assertEqual(
                candidates[0]["video_path"], (root / "downloads/video.mp4").resolve()
            )
            self.assertEqual(
                candidates[0]["output_path"], (root / "analysis/pick-1.json").resolve()
            )


if __name__ == "__main__":
    unittest.main()
