from __future__ import annotations

import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))

from browse import parse_view_count_text


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


if __name__ == "__main__":
    unittest.main()
