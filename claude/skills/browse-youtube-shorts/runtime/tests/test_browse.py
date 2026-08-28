from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))

import browse  # noqa: E402
from browse import parse_view_count_text  # noqa: E402


class ParseViewCountTextTest(unittest.TestCase):
    def test_uses_trailing_metric_instead_of_list_number(self) -> None:
        self.assertEqual(
            parse_view_count_text("Top 15 Best online Job searching websites654K views"),
            654_000,
        )

    def test_uses_trailing_metric_instead_of_year(self) -> None:
        self.assertEqual(
            parse_view_count_text("Best places to work in the UK | UK Work Visa 2024 247 views"),
            247,
        )

    def test_accepts_compact_metric_without_views_label(self) -> None:
        self.assertEqual(parse_view_count_text("1.2M"), 1_200_000)

    def test_rejects_non_metric_text(self) -> None:
        self.assertEqual(parse_view_count_text("graduate schemes 2026"), 0)


class BrowserLifecycleTest(unittest.TestCase):
    def tearDown(self) -> None:
        browse._research_chrome_process = None

    @patch("browse._stop_research_browser")
    @patch("browse.browse_youtube_shorts", new_callable=AsyncMock)
    def test_main_stops_browser_after_success(self, browse_shorts: AsyncMock, stop: MagicMock) -> None:
        browse_shorts.return_value = {}
        with patch.object(sys, "argv", ["browse.py", "test query", "--json"]):
            browse.main()
        stop.assert_called_once_with()

    @patch("browse._stop_research_browser")
    @patch("browse.browse_youtube_shorts", new_callable=AsyncMock)
    def test_main_stops_browser_after_failure(self, browse_shorts: AsyncMock, stop: MagicMock) -> None:
        browse_shorts.side_effect = RuntimeError("browse failed")
        with (
            patch.object(sys, "argv", ["browse.py", "test query", "--json"]),
            self.assertRaisesRegex(RuntimeError, "browse failed"),
        ):
            browse.main()
        stop.assert_called_once_with()

    @patch("browse._close_research_tabs")
    def test_stop_waits_then_kills_a_stuck_browser(self, close_tabs: MagicMock) -> None:
        process = MagicMock()
        process.wait.side_effect = [subprocess.TimeoutExpired("chrome", 5), 0]
        browse._research_chrome_process = process

        browse._stop_research_browser()

        close_tabs.assert_called_once_with()
        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        self.assertEqual(process.wait.call_count, 2)
        self.assertIsNone(browse._research_chrome_process)


if __name__ == "__main__":
    unittest.main()
