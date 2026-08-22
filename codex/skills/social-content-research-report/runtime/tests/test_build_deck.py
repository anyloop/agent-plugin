from __future__ import annotations

import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))

from build_deck import validate_platform
from copy_validation import validate_reader_copy


class ValidateReaderCopyTest(unittest.TestCase):
    def test_accepts_concise_video_slide_intros(self) -> None:
        data = {
            "platforms": {
                "youtube": {
                    "brand_intro": (
                        "Canva leads YouTube at 57K views; Twinkl and Teach Starter "
                        "remain below 3K. Tutorials are the clearest brand format."
                    ),
                    "creator_intro": (
                        "Teacher demos turn one classroom problem into a quick payoff."
                    ),
                }
            }
        }

        self.assertEqual(validate_reader_copy(data), [])

    def test_flags_long_audit_narrative_on_video_slide(self) -> None:
        data = {
            "platforms": {
                "youtube": {
                    "brand_intro": (
                        "Canva has the highest eligible official post at 57K views. "
                        "Several product-central candidates were excluded because "
                        "candidate rows had missing handles, while other searches "
                        "returned blank captions and weak query results."
                    )
                }
            }
        }

        warnings = validate_reader_copy(data)

        self.assertTrue(
            any("character slide-copy budget" in warning for warning in warnings)
        )
        self.assertTrue(any("methodology" in warning for warning in warnings))

    def test_flags_multi_sentence_format_description(self) -> None:
        data = {
            "formats": {
                "format1Desc": (
                    "Teachers name the problem. They demo the resource. "
                    "Then they recap it."
                )
            }
        }

        warnings = validate_reader_copy(data)

        self.assertTrue(
            any("1-sentence slide-copy budget" in warning for warning in warnings)
        )


class ValidatePlatformTest(unittest.TestCase):
    def test_content_type_aliases_do_not_fake_diversity(self) -> None:
        section = {
            "creator_floor": 0,
            "creator_gap_note": "Exhaustive top-up completed.",
            "creator_top_up_complete": True,
            "brand_videos": [
                {"handle": "a", "content_type": "UGC testimonial"},
                {"handle": "b", "content_type": "UGC / testimonial"},
                {"handle": "c", "content_type": "Honest review"},
                {"handle": "d", "content_type": "Tutorial"},
            ],
            "creator_videos": [
                {"handle": "e", "content_type": "Customer review"},
                {"handle": "f", "content_type": "Educational tutorial"},
                {"handle": "g", "content_type": "UGC testimonial"},
                {"handle": "h", "content_type": "Explainer"},
            ],
        }
        warnings = validate_platform("TikTok", section)
        self.assertTrue(
            any("only 2 distinct content type" in item for item in warnings)
        )

    def test_warns_when_a_content_page_has_fewer_than_four_cards(self) -> None:
        section = {
            "brand_videos": [
                {"handle": f"@brand{index}", "metric": "20K views", "format": "demo"}
                for index in range(3)
            ],
            "creator_videos": [
                {"handle": f"@creator{index}", "metric": "60K views", "format": "review"}
                for index in range(5)
            ],
        }

        warnings = validate_platform("TikTok", section)

        self.assertIn("TikTok: brand page has only 3 cards (minimum 4, target 5)", warnings)

    def test_warns_when_full_platform_lacks_content_type_variety(self) -> None:
        section = {
            "brand_videos": [
                {
                    "handle": f"@brand{index}",
                    "metric": "20K views",
                    "format": ("demo", "review", "comparison")[index % 3],
                    "content_type": "educational",
                }
                for index in range(4)
            ],
            "creator_videos": [
                {
                    "handle": f"@creator{index}",
                    "metric": "60K views",
                    "format": ("demo", "review", "comparison")[index % 3],
                    "content_type": "educational",
                }
                for index in range(4)
            ],
        }

        warnings = validate_platform("Instagram", section)

        self.assertIn(
            "Instagram: only 1 distinct content type across 8 cards (minimum 3)",
            warnings,
        )

    def test_accepts_one_thousand_creator_floor_after_targeted_top_up(self) -> None:
        section = {
            "brand_videos": [],
            "creator_videos": [
                {"handle": f"@creator{index}", "metric": "5K views", "format": "demo"}
                for index in range(5)
            ],
            "creator_floor": 1_000,
            "creator_gap_note": "All targeted product and hashtag modes were exhausted.",
            "creator_top_up_complete": True,
        }

        warnings = validate_platform("TikTok", section)

        self.assertFalse(any("below the declared creator floor" in warning for warning in warnings))
        self.assertFalse(any("10K hard floor" in warning for warning in warnings))

    def test_rejects_one_thousand_floor_without_top_up_evidence(self) -> None:
        section = {
            "brand_videos": [],
            "creator_videos": [
                {"handle": "@creator", "metric": "5K views", "format": "demo"}
            ],
            "creator_floor": 1_000,
        }

        warnings = validate_platform("TikTok", section)

        self.assertTrue(any("creator_top_up_complete" in warning for warning in warnings))

    def test_accepts_verified_niche_without_reach_floor_after_top_up(self) -> None:
        section = {
            "brand_videos": [],
            "creator_videos": [
                {"handle": f"@local{index}", "metric": f"{125 - index * 25} likes", "format": "demo"}
                for index in range(5)
            ],
            "creator_floor": 0,
            "creator_gap_note": "Five exact local service posts remained after exhaustive top-up.",
            "creator_top_up_complete": True,
        }

        warnings = validate_platform("Instagram", section)

        self.assertFalse(any("creator_floor must be" in warning for warning in warnings))
        self.assertFalse(any("below the declared creator floor" in warning for warning in warnings))

    def test_rejects_ten_thousand_floor_without_top_up_evidence(self) -> None:
        section = {
            "brand_videos": [],
            "creator_videos": [
                {"handle": "@creator", "metric": "25K views", "format": "demo"}
            ],
            "creator_floor": 10_000,
            "creator_gap_note": "Relevant 50K examples were unavailable.",
        }

        warnings = validate_platform("Instagram", section)

        self.assertTrue(any("creator_top_up_complete" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
