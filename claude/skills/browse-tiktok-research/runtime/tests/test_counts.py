"""The count parser, on both sides of the browser boundary.

Regression tests for numbers that reached a delivered report looking real. The
parser used to match the WHOLE string, so a node rendering "12.3K likes" — how
both sites write a count and its noun together — missed and fell through to
`parseInt`, which answers 12. Nothing downstream can tell that from a real 12.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

import counts

RUNTIME = Path(__file__).resolve().parent.parent


def _node_eval(script, payload):
    """Run one JS helper over a list of inputs and return its answers."""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not available on this machine")
    result = subprocess.run(
        [node, "-e", script, "--", json.dumps(payload)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


class ParseCount(unittest.TestCase):
    def test_reads_a_plain_number(self):
        self.assertEqual(counts.parse_count("1234"), 1234)
        self.assertEqual(counts.parse_count("1,234"), 1234)

    def test_keeps_the_multiplier(self):
        self.assertEqual(counts.parse_count("12.3K"), 12_300)
        self.assertEqual(counts.parse_count("1.2M"), 1_200_000)
        self.assertEqual(counts.parse_count("1.1B"), 1_100_000_000)

    def test_reads_a_count_that_carries_its_noun(self):
        # The regression. Each of these used to come back as its leading digits.
        self.assertEqual(counts.parse_count("12.3K likes"), 12_300)
        self.assertEqual(counts.parse_count("1.2M views"), 1_200_000)
        self.assertEqual(counts.parse_count("823K likes"), 823_000)
        self.assertEqual(counts.parse_count("1,234 comments"), 1_234)

    def test_rejects_text_that_does_not_start_with_a_number(self):
        for junk in ("", None, "Liked by someone and 3 others", "likes", "K"):
            self.assertIsNone(counts.parse_count(junk), junk)

    def test_is_case_insensitive_about_the_multiplier(self):
        self.assertEqual(counts.parse_count("2.5k plays"), 2_500)
        self.assertEqual(counts.parse_count("2.5m plays"), 2_500_000)


class JsParseCount(unittest.TestCase):
    """The browser copy has to answer exactly what the python copy answers."""

    CASES = [
        ("1234", 1234),
        ("1,234", 1234),
        ("12.3K", 12_300),
        ("12.3K likes", 12_300),
        ("1.2M views", 1_200_000),
        ("1.1B", 1_100_000_000),
        ("823K likes", 823_000),
        ("2.5k plays", 2_500),
        ("", None),
        ("likes", None),
        ("Liked by someone and 3 others", None),
    ]

    def test_matches_the_python_parser(self):
        script = (
            "(function(){"
            + counts.JS_PARSE_COUNT
            + "process.stdout.write(JSON.stringify("
            "JSON.parse(process.argv[1]).map(parseCount)));})()"
        )
        answers = _node_eval(script, [text for text, _ in self.CASES])
        self.assertEqual(answers, [want for _, want in self.CASES])

    def test_python_agrees_with_the_table(self):
        for text, want in self.CASES:
            self.assertEqual(counts.parse_count(text), want, text)

    def test_the_snippets_carry_no_second_definition(self):
        source = (RUNTIME / "browse.py").read_text()
        # A second definition is a second set of rules waiting to drift.
        self.assertNotIn("function parseCount(s) {", source)
        self.assertNotIn("parseInt(s, 10)", source)
        self.assertIn("JS_PARSE_COUNT", source)


class MarkdownRecovery(unittest.TestCase):
    """The fallback that reads counts back out of the agent's own transcript."""

    def test_keeps_the_multiplier_on_a_recovered_count(self):
        import recovery

        rows = recovery.parse_markdown_video_list(
            "- Video URL: https://www.tiktok.com/@a/video/1\n"
            "- Like Count: 1.2M\n"
            "- Video URL: https://www.tiktok.com/@b/video/2\n"
            "- View Count: 823K\n"
        )
        self.assertEqual([r.get("like_count") for r in rows], [1_200_000, 823_000])

    def test_leaves_an_unreadable_count_unset(self):
        import recovery

        rows = recovery.parse_markdown_video_list(
            "- Video URL: https://www.tiktok.com/@a/video/1\n- Like Count: unknown\n"
        )
        self.assertNotIn("like_count", rows[0])


if __name__ == "__main__":
    unittest.main()
