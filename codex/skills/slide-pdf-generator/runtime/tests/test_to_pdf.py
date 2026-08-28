"""Tests for deterministic slide readiness before PDF rendering."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))

import to_pdf  # noqa: E402


class ReadinessExpressionTests(unittest.TestCase):
    def test_waits_for_page_fonts_images_and_layout_with_a_cap(self) -> None:
        expression = to_pdf.readiness_expression(2.5)

        self.assertIn('document.readyState !== "complete"', expression)
        self.assertIn("document.fonts.ready", expression)
        self.assertIn("document.images", expression)
        self.assertIn("image.decode()", expression)
        self.assertIn("requestAnimationFrame", expression)
        self.assertIn("2500", expression)

    def test_timeout_is_always_positive(self) -> None:
        self.assertIn("setTimeout", to_pdf.readiness_expression(0))
        self.assertIn("1", to_pdf.readiness_expression(0))


if __name__ == "__main__":
    unittest.main()
