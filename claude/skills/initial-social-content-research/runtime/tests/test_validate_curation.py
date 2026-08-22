from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))

from validate_curation import validate, validate_content_type_coverage


def relevance(test: str = "product-decision-service", specificity: int = 2) -> dict:
    return {
        "test": test,
        "specificity": specificity,
        "evidence": "The transcript compares two named snowboard bindings for a specific rider.",
    }


def candidate(platform: str, group: str, index: int, selected: bool) -> dict:
    content_types = (
        "branded / owned IP",
        "branded commercial",
        "educational",
        "UGC testimonial",
    )
    item = {
        "url": f"https://example.com/{platform}/{group}/{index}",
        "handle": f"@{group}{index % 3}",
        "metric": f"{500 - index}K views",
        "format": ("REVIEW", "SETUP", "COMPARISON")[index % 3],
        "content_type": content_types[index % len(content_types)],
        "selected": selected,
        "relevance": relevance(),
    }
    if group == "brand":
        item["official_account_verified"] = True
    if not selected:
        item["exclusion_reason"] = "Lower reach after relevance and diversity ranking."
    return item


def valid_payloads() -> tuple[dict, dict]:
    data = {"platforms": {}}
    audit = {"platforms": {}}
    for platform in ("tiktok", "instagram", "youtube"):
        brand = [candidate(platform, "brand", index, index < 5) for index in range(10)]
        creator = [
            candidate(platform, "creator", index, index < 5) for index in range(10)
        ]
        data["platforms"][platform] = {
            "brand_videos": [
                {
                    key: value
                    for key, value in item.items()
                    if key not in {"selected", "official_account_verified"}
                }
                for item in brand[:5]
            ],
            "creator_videos": [
                {key: value for key, value in item.items() if key != "selected"}
                for item in creator[:5]
            ],
        }
        audit["platforms"][platform] = {
            "brand_search_modes": [
                "official-account",
                "product-query",
                "brand-hashtag",
                "partnership-query",
                "retailer-distributor",
                "content-type-expansion",
                "indexed-fallback",
            ],
            "brand_candidates": brand,
            "creator_search_modes": [
                "exact-product",
                "competitor-product",
                "product-decision",
                "precise-problem",
                "content-type-expansion",
                "mined-hashtag",
                "indexed-fallback",
            ],
            "creator_candidates": creator,
            "creator_floor": 50_000,
        }
    return data, audit


class ValidateCurationTest(unittest.TestCase):
    def test_content_type_aliases_do_not_fake_diversity(self) -> None:
        data = {
            "platforms": {
                "tiktok": {
                    "brand_videos": [
                        {"content_type": "UGC testimonial"},
                        {"content_type": "UGC / testimonial"},
                    ],
                    "creator_videos": [
                        {"content_type": "Honest review"},
                        {"content_type": "Tutorial"},
                    ],
                }
            }
        }
        errors = validate_content_type_coverage(data, "tiktok")
        self.assertEqual(1, len(errors))
        self.assertIn("found 2", errors[0])

    def test_accepts_relevant_high_reach_selection(self) -> None:
        data, audit = valid_payloads()
        self.assertEqual(validate(data, audit), [])

    def test_rejects_general_topic_creator(self) -> None:
        data, audit = valid_payloads()
        bad_relevance = relevance("general-topic", 1)
        data["platforms"]["tiktok"]["creator_videos"][0]["relevance"] = bad_relevance
        audit["platforms"]["tiktok"]["creator_candidates"][0]["relevance"] = (
            bad_relevance
        )
        errors = validate(data, audit)
        self.assertTrue(any("unsupported relevance test" in error for error in errors))
        self.assertTrue(
            any("specificity must be one of (2, 3)" in error for error in errors)
        )

    def test_allows_rejected_generic_candidate_in_audit(self) -> None:
        data, audit = valid_payloads()
        rejected = audit["platforms"]["tiktok"]["creator_candidates"][5]
        rejected["relevance"] = relevance("general-topic", 1)
        rejected["exclusion_reason"] = (
            "General snowboarding montage; no product is evaluated."
        )
        self.assertEqual(validate(data, audit), [])

    def test_requires_highest_reach_brand_candidate(self) -> None:
        data, audit = valid_payloads()
        platform_audit = audit["platforms"]["youtube"]
        platform_audit["brand_candidates"][0]["selected"] = False
        platform_audit["brand_candidates"][0]["exclusion_reason"] = (
            "Skipped without cause."
        )
        replacement = platform_audit["brand_candidates"][5]
        replacement["selected"] = True
        replacement.pop("exclusion_reason")
        data["platforms"]["youtube"]["brand_videos"][0] = {
            key: value
            for key, value in replacement.items()
            if key not in {"selected", "official_account_verified"}
        }
        errors = validate(data, audit)
        self.assertIn(
            "youtube.brand: highest-reach eligible candidate was not selected",
            errors,
        )

    def test_does_not_mutate_inputs(self) -> None:
        data, audit = valid_payloads()
        before = (copy.deepcopy(data), copy.deepcopy(audit))
        validate(data, audit)
        self.assertEqual((data, audit), before)

    def test_allows_one_thousand_floor_after_recorded_targeted_top_up(self) -> None:
        data, audit = valid_payloads()
        platform = audit["platforms"]["tiktok"]
        platform["creator_floor"] = 1_000
        platform["creator_gap_note"] = (
            "Targeted product, competitor, hashtag, and use-case sweeps produced fewer than five creators above 10K."
        )
        platform["creator_top_up_complete"] = True
        for index, item in enumerate(data["platforms"]["tiktok"]["creator_videos"]):
            metric = f"{9 - index}K views"
            item["metric"] = metric
            platform["creator_candidates"][index]["metric"] = metric

        self.assertEqual(validate(data, audit), [])

    def test_rejects_one_thousand_floor_without_recorded_targeted_top_up(self) -> None:
        data, audit = valid_payloads()
        platform = audit["platforms"]["instagram"]
        platform["creator_floor"] = 1_000
        platform["creator_gap_note"] = "The preferred creator floor was too thin."

        errors = validate(data, audit)

        self.assertIn(
            "instagram.creator: 1K fallback requires creator_top_up_complete=true",
            errors,
        )

    def test_allows_zero_floor_for_verified_niche_after_exhaustive_top_up(self) -> None:
        data, audit = valid_payloads()
        platform = audit["platforms"]["instagram"]
        platform["creator_floor"] = 0
        platform["creator_gap_note"] = (
            "The local practitioner niche produced five exact service posts but fewer than five above 1K."
        )
        platform["creator_top_up_complete"] = True
        for index, item in enumerate(data["platforms"]["instagram"]["creator_videos"]):
            metric = f"{125 - (index * 25)} likes"
            item["metric"] = metric
            platform["creator_candidates"][index]["metric"] = metric

        self.assertEqual(validate(data, audit), [])

    def test_rejects_relaxed_creator_floor_with_incomplete_search_modes(self) -> None:
        data, audit = valid_payloads()
        platform = audit["platforms"]["instagram"]
        platform["creator_floor"] = 10_000
        platform["creator_gap_note"] = "Five relevant creators were unavailable at 50K."
        platform["creator_top_up_complete"] = True
        platform["creator_search_modes"].remove("indexed-fallback")

        errors = validate(data, audit)

        self.assertIn(
            "instagram.creator: incomplete top-up search modes ['indexed-fallback']",
            errors,
        )

    def test_underfilled_brand_pool_requires_completed_top_up(self) -> None:
        data, audit = valid_payloads()
        removed = data["platforms"]["tiktok"]["brand_videos"].pop()
        for item in audit["platforms"]["tiktok"]["brand_candidates"]:
            if item["url"] == removed["url"]:
                item["selected"] = False
                item["exclusion_reason"] = "No fifth relevant card was found."
        audit["platforms"]["tiktok"]["brand_gap_note"] = "Four relevant cards remain."

        errors = validate(data, audit)

        self.assertIn(
            "tiktok.brand: underfilled pool requires brand_top_up_complete=true",
            errors,
        )

    def test_strict_full_cards_rejects_underfilled_pool(self) -> None:
        data, audit = valid_payloads()
        removed = data["platforms"]["youtube"]["creator_videos"].pop()
        for item in audit["platforms"]["youtube"]["creator_candidates"]:
            if item["url"] == removed["url"]:
                item["selected"] = False
                item["exclusion_reason"] = "Removed to exercise the full-card gate."
        audit["platforms"]["youtube"]["creator_gap_note"] = "One slot remains."

        errors = validate(data, audit, require_full_cards=True)

        self.assertIn("youtube.creator: requires 5 selected cards, found 4", errors)

    def test_minimum_card_gate_rejects_three_card_page(self) -> None:
        data, audit = valid_payloads()
        platform_data = data["platforms"]["tiktok"]
        platform_audit = audit["platforms"]["tiktok"]
        removed = platform_data["brand_videos"][3:]
        del platform_data["brand_videos"][3:]
        removed_urls = {item["url"] for item in removed}
        for item in platform_audit["brand_candidates"]:
            if item["url"] in removed_urls:
                item["selected"] = False
                item["exclusion_reason"] = "Removed to exercise the minimum-card gate."
        platform_audit["brand_gap_note"] = "Only three cards were selected."
        platform_audit["brand_top_up_complete"] = True

        errors = validate(data, audit, minimum_cards=4)

        self.assertIn("tiktok.brand: requires at least 4 selected cards, found 3", errors)

    def test_type_coverage_gate_requires_three_types_per_platform(self) -> None:
        data, audit = valid_payloads()
        for group in ("brand", "creator"):
            report_key = f"{group}_videos"
            candidate_key = f"{group}_candidates"
            for item in data["platforms"]["instagram"][report_key]:
                item["content_type"] = "educational"
            for item in audit["platforms"]["instagram"][candidate_key]:
                item["content_type"] = "educational"

        errors = validate(data, audit, require_type_coverage=True)

        self.assertIn(
            "instagram: requires at least 3 content types across selected cards, found 1",
            errors,
        )

    def test_accepts_attributable_creator_post_in_brand_pool(self) -> None:
        data, audit = valid_payloads()
        item = audit["platforms"]["tiktok"]["brand_candidates"][1]
        item["official_account_verified"] = False
        item["relationship"] = "brand_attributed"
        item["relationship_evidence"] = (
            "The creator demonstrates the named product and tags its official brand account."
        )
        item["promotion_strength"] = "direct"

        self.assertEqual(validate(data, audit), [])

    def test_rejects_unverified_brand_candidate_without_relationship_evidence(self) -> None:
        data, audit = valid_payloads()
        item = audit["platforms"]["instagram"]["brand_candidates"][2]
        item["official_account_verified"] = False

        errors = validate(data, audit)

        self.assertIn(
            "instagram.brand[3]: brand candidate is neither official nor attributable",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
