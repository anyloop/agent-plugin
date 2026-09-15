import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engagement_policy import (
    engagement,
    performance_reference,
    selection_errors,
    primary_strategy_errors,
)
from discovery_policy import build_gap_plan


def post(index, metric="20K likes"):
    return {
        "url": f"https://example.com/{index}",
        "metric": metric,
        "relevance": {
            "test": "precise-product-problem",
            "specificity": 2,
            "evidence": "Shows an adult child coordinating a parent's referral.",
        },
    }


class EngagementPolicyTest(unittest.TestCase):
    def test_units_cannot_be_substituted(self):
        self.assertIsNone(engagement(post(1, "100K views"), "instagram"))
        self.assertIsNone(engagement(post(1, "100K followers"), "tiktok"))
        self.assertEqual(engagement(post(1, "12,345 likes"), "tiktok"), 12345)
        self.assertEqual(engagement(post(1, "20K views"), "youtube"), 20000)

    def test_viral_general_topic_is_not_eligible(self):
        p = post(1, "1M likes")
        p["relevance"]["test"] = "general-topic"
        self.assertFalse(performance_reference(p, "instagram"))

    def test_long_form_is_context_even_with_many_likes(self):
        p = post(1)
        p["duration_seconds"] = 453
        self.assertFalse(performance_reference(p, "tiktok"))
        self.assertTrue(selection_errors([p], [p], "tiktok", ""))

    def test_two_specific_exceptions_balance_five_card_page(self):
        selected = [post(i) for i in range(3)] + [
            post(i, "347 likes") for i in range(3, 5)
        ]
        for p in selected[3:]:
            p.update(
                selection_role="context",
                selection_reason="Only example demonstrating the remote referral handoff.",
            )
        self.assertEqual(selection_errors(selected, selected, "tiktok", ""), [])

    def test_lowered_floor_cannot_hide_stronger_available_candidates(self):
        weak = [post(i, "74 likes") for i in range(5)]
        for p in weak:
            p.update(
                selection_role="context",
                selection_reason="A specific relevant administrative workflow example.",
            )
        strong = [post(i) for i in range(5, 10)]
        errors = selection_errors(
            weak,
            weak + strong,
            "tiktok",
            "Claimed niche gap despite stronger candidates.",
        )
        self.assertTrue(any("stronger relevant" in e for e in errors))

    def test_genuine_shortage_requires_explicit_quality_gap(self):
        weak = [post(1, "74 likes")]
        weak[0].update(
            selection_role="context",
            selection_reason="Only verified example of this referral workflow.",
        )
        self.assertTrue(selection_errors(weak, weak, "tiktok", ""))
        self.assertEqual(
            selection_errors(
                weak,
                weak,
                "tiktok",
                "No strong evidence found in documented targeted searches.",
            ),
            [],
        )

    def test_full_page_still_generates_quality_top_up(self):
        weak = [post(i, "74 likes") for i in range(5)]
        data = {"platforms": {"tiktok": {"creator_videos": weak}}}
        audit = {
            "platforms": {
                "tiktok": {
                    "creator_candidates": [post(i, "74 likes") for i in range(12)]
                }
            }
        }
        before = copy.deepcopy((data, audit))
        gaps = build_gap_plan(data, audit=audit)
        gap = next(
            g for g in gaps if g["platform"] == "tiktok" and g["pool"] == "creator"
        )
        self.assertEqual(gap["performance_missing"], 3)
        self.assertEqual(gap["missing"], 0)
        self.assertEqual((data, audit), before)

    def test_skipping_equally_relevant_stronger_post_needs_tradeoff(self):
        selected = [post(1)]
        errors = selection_errors(
            selected, selected + [post(2, "100K likes")], "tiktok", ""
        )
        self.assertTrue(any("alternative" in e for e in errors))
        selected[0]["selection_reason"] = (
            "Shows bilingual family handoffs rather than a monolingual office tutorial."
        )
        self.assertEqual(
            selection_errors(
                selected, selected + [post(2, "100K likes")], "tiktok", ""
            ),
            [],
        )

    def test_primary_recommendations_cannot_all_be_low_engagement(self):
        references = [post(i, "347 likes") for i in range(5)]
        data = {
            "platforms": {"tiktok": {"creator_videos": references}},
            "strategies": {"items": [{"url": p["url"]} for p in references]},
        }
        self.assertTrue(primary_strategy_errors(data))
        for p in references[:3]:
            p["metric"] = "20K likes"
        self.assertEqual(primary_strategy_errors(data), [])

    def test_malformed_specificity_is_not_a_crash_or_qualified(self):
        p = post(1)
        p["relevance"]["specificity"] = "high"
        self.assertTrue(selection_errors([p], [p, post(2, "100K likes")], "tiktok", ""))

    def test_partial_strong_pool_must_still_be_used(self):
        weak = post(1, "74 likes")
        weak.update(
            selection_role="context",
            selection_reason="Specific referral workflow with a different format.",
        )
        chosen = [weak, dict(weak, url="https://example.com/3")]
        errors = selection_errors(
            chosen,
            chosen + [post(2)],
            "tiktok",
            "Only one strong relevant post was found in targeted searches.",
        )
        self.assertTrue(any("stronger relevant" in e for e in errors))
