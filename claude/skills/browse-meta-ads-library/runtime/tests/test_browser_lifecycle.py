from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))

import browse  # noqa: E402


class BrowserLifecycleTest(unittest.TestCase):
    def tearDown(self) -> None:
        browse._research_chrome_process = None

    @patch("browse._close_research_tabs")
    def test_stop_waits_for_browser_exit(self, close_tabs: MagicMock) -> None:
        process = MagicMock()
        browse._research_chrome_process = process

        browse._stop_research_browser()

        close_tabs.assert_called_once_with()
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5)
        process.kill.assert_not_called()
        self.assertIsNone(browse._research_chrome_process)

    @patch("browse._close_research_tabs")
    def test_stop_kills_browser_that_ignores_terminate(self, close_tabs: MagicMock) -> None:
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
