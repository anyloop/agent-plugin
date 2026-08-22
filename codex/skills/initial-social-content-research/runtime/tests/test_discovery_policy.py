from __future__ import annotations

import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))

from discovery_policy import (
    _mode_queries,
    build_gap_plan,
    build_query_plan,
    choose_creator_floor,
    expand_query_variants,
    extract_hashtags,
    mine_relevant_hashtags,
)


class DiscoveryPolicyTest(unittest.TestCase):
    def test_creator_content_type_expansion_excludes_owned_queries(self) -> None:
        passes = _mode_queries(
            {
                "platform": "tiktok",
                "pool": "creator",
                "search_modes": ["content-type-expansion"],
                "content_type_gaps": ["branded-owned", "ugc-testimonial"],
            },
            client_name="AdAnt",
            competitor_names=["Arcads"],
            all_entities=[{"name": "AdAnt"}, {"name": "Arcads"}],
            use_cases=["AI UGC ads"],
            mined_hashtags=[],
            is_app=True,
            per_entity_limit=24,
            batch_size=8,
            max_queries_per_pass=24,
        )
        content_pass = next(
            item for item in passes if item["mode"] == "content-type-expansion"
        )
        joined = " ".join(content_pass["queries"]).casefold()
        self.assertNotIn("official", joined)
        self.assertNotIn("founder story", joined)
        self.assertIn("honest review", joined)

    def test_expands_brand_into_hashtag_and_high_intent_queries(self) -> None:
        queries = expand_query_variants(
            "Prompt Tornado",
            is_app=True,
            use_cases=["AI workflow automation", "multi-agent orchestration"],
        )

        self.assertEqual(queries[0], "Prompt Tornado")
        self.assertIn("#PromptTornado", queries)
        self.assertIn("Prompt Tornado review", queries)
        self.assertIn("Prompt Tornado demo", queries)
        self.assertIn("Prompt Tornado tutorial", queries)
        self.assertIn("Prompt Tornado app", queries)
        self.assertIn("Prompt Tornado alternative", queries)
        self.assertIn("Prompt Tornado AI workflow automation", queries)
        self.assertEqual(len(queries), len(set(queries)))

    def test_expansion_respects_cap_without_dropping_core_queries(self) -> None:
        queries = expand_query_variants(
            "Notis AI",
            is_app=True,
            use_cases=[f"use case {index}" for index in range(20)],
            limit=10,
        )

        self.assertEqual(len(queries), 10)
        self.assertEqual(queries[:3], ["Notis AI", "#NotisAI", "Notis AI review"])

    def test_extracts_distinct_caption_hashtags(self) -> None:
        self.assertEqual(
            extract_hashtags("Try #JobSearch with #CareerTok and #jobsearch today"),
            ["#JobSearch", "#CareerTok"],
        )

    def test_chooses_highest_floor_that_can_fill_target(self) -> None:
        self.assertEqual(
            choose_creator_floor([90_000, 60_000, 49_000, 30_000, 12_000], target=5),
            10_000,
        )
        self.assertEqual(
            choose_creator_floor([12_000, 11_000, 9_000, 5_000, 1_500], target=5),
            1_000,
        )
        self.assertEqual(
            choose_creator_floor([100_000, 80_000, 70_000, 60_000, 50_000], target=5),
            50_000,
        )
        self.assertEqual(
            choose_creator_floor([1_900, 125, 41, 27, 14], target=5),
            0,
        )

    def test_gap_plan_reports_each_underfilled_pool(self) -> None:
        data = {
            "platforms": {
                "tiktok": {"brand_videos": [{}], "creator_videos": []},
                "instagram": {"brand_videos": [{}, {}, {}, {}, {}], "creator_videos": [{}, {}, {}, {}]},
                "youtube": {"brand_videos": [{}, {}, {}, {}, {}], "creator_videos": [{}, {}, {}, {}, {}]},
            }
        }

        plan = build_gap_plan(data, target=5)

        self.assertEqual(
            [(item["platform"], item["pool"], item["missing"]) for item in plan],
            [("tiktok", "brand", 4), ("tiktok", "creator", 5), ("instagram", "creator", 1)],
        )
        self.assertEqual(
            plan[0]["search_modes"][:3],
            ["official-account", "product-query", "brand-hashtag"],
        )

    def test_gap_plan_requires_a_relevance_first_candidate_buffer(self) -> None:
        data = {
            "platforms": {
                "tiktok": {"brand_videos": [{}] * 2, "creator_videos": [{}] * 3},
                "instagram": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
                "youtube": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
            }
        }

        brand, creator = build_gap_plan(data)

        self.assertEqual(brand["candidate_target"], 12)
        self.assertEqual(brand["minimum"], 4)
        self.assertEqual(brand["minimum_missing"], 2)
        self.assertTrue(brand["delivery_blocked"])
        self.assertEqual(
            brand["search_modes"],
            [
                "official-account",
                "product-query",
                "brand-hashtag",
                "partnership-query",
                "retailer-distributor",
                "content-type-expansion",
                "indexed-fallback",
            ],
        )
        self.assertEqual(
            creator["search_modes"],
            [
                "exact-product",
                "competitor-product",
                "product-decision",
                "precise-problem",
                "content-type-expansion",
                "mined-hashtag",
                "indexed-fallback",
            ],
        )
        self.assertEqual(creator["engagement_floors"], [50000, 10000, 1000, 0])

    def test_gap_plan_tops_up_full_slides_with_a_thin_candidate_pool(self) -> None:
        data = {
            "platforms": {
                platform: {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5}
                for platform in ("tiktok", "instagram", "youtube")
            }
        }
        audit = {
            "platforms": {
                platform: {
                    "brand_candidates": [{}] * (5 if platform == "tiktok" else 12),
                    "creator_candidates": [{}] * 12,
                }
                for platform in ("tiktok", "instagram", "youtube")
            }
        }

        plan = build_gap_plan(data, audit=audit)

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["platform"], "tiktok")
        self.assertEqual(plan[0]["missing"], 0)
        self.assertEqual(plan[0]["candidate_missing"], 7)

    def test_builds_domain_qualified_queries_for_ambiguous_competitors(self) -> None:
        data = {
            "platforms": {
                "tiktok": {"brand_videos": [], "creator_videos": []},
                "instagram": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
                "youtube": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
            }
        }
        profile = {
            "client_name": "Notis",
            "is_app": True,
            "keyword_seeds": ["WhatsApp AI assistant", "voice note automation"],
        }
        competitors = {
            "confirmed_competitors": [
                {"name": "Arlo", "website": "https://www.arlo.sh"}
            ]
        }

        plan = build_query_plan(data, profile, competitors, per_entity_limit=6)

        self.assertEqual(len(plan), 2)
        brand_queries = plan[0]["queries"]
        self.assertIn('"Arlo" arlo.sh', brand_queries)
        self.assertIn("#Notis", brand_queries)
        self.assertEqual(len(brand_queries), len(set(brand_queries)))

    def test_query_plan_groups_queries_by_required_search_mode(self) -> None:
        data = {
            "platforms": {
                "tiktok": {"brand_videos": [], "creator_videos": []},
                "instagram": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
                "youtube": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
            }
        }
        profile = {
            "client_name": "Trail Vest",
            "website": "https://trailvest.example",
            "keyword_seeds": ["night dog walking", "reflective dog vest"],
        }
        competitors = {
            "confirmed_competitors": [
                {"name": "Pup Safe", "website": "https://pupsafe.example"}
            ]
        }

        brand, creator = build_query_plan(
            data,
            profile,
            competitors,
            mined_hashtags=["#NightWalkSafety"],
        )

        self.assertEqual(
            [item["mode"] for item in brand["passes"]], brand["search_modes"]
        )
        self.assertEqual(
            [item["mode"] for item in creator["passes"]], creator["search_modes"]
        )
        creator_passes = {item["mode"]: item["queries"] for item in creator["passes"]}
        self.assertIn("Pup Safe review", creator_passes["competitor-product"])
        self.assertIn("reflective dog vest review", creator_passes["product-decision"])
        self.assertIn("#NightWalkSafety", creator_passes["mined-hashtag"])
        self.assertIn(
            "Trail Vest before after",
            creator_passes["content-type-expansion"],
        )
        self.assertTrue(all(item["queries"] for item in brand["passes"]))
        self.assertTrue(all(item["queries"] for item in creator["passes"]))
        self.assertTrue(
            all(
                len(batch) <= 8
                for gap in (brand, creator)
                for item in gap["passes"]
                for batch in item["batches"]
            )
        )

    def test_mines_hashtags_only_from_relevant_candidates(self) -> None:
        audit = {
            "platforms": {
                "tiktok": {
                    "creator_candidates": [
                        {
                            "caption": "Built a product ad with #AIUGC and #AdCreative",
                            "relevance": {
                                "test": "product-decision-service",
                                "specificity": 2,
                                "evidence": "The post demonstrates an AI product-ad workflow.",
                            },
                        },
                        {
                            "caption": "A broad animation montage #ViralAI",
                            "relevance": {
                                "test": "general-topic",
                                "specificity": 1,
                                "evidence": "No advertising product or workflow appears.",
                            },
                        },
                    ]
                }
            }
        }

        self.assertEqual(
            mine_relevant_hashtags(audit),
            ["#AIUGC", "#AdCreative"],
        )

    def test_query_plan_automatically_uses_relevant_audit_hashtags(self) -> None:
        data = {
            "platforms": {
                "tiktok": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 3},
                "instagram": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
                "youtube": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
            }
        }
        profile = {"client_name": "AdAnt", "keyword_seeds": ["AI UGC ads"]}
        competitors = {"confirmed_competitors": [{"name": "Creatify"}]}
        audit = {
            "platforms": {
                "tiktok": {
                    "creator_candidates": [
                        {
                            "description": "Creatify workflow #AIProductAds",
                            "relevance": {
                                "test": "named-competitor-product",
                                "specificity": 3,
                                "evidence": "Creatify is named and its product workflow is shown.",
                            },
                        }
                    ]
                }
            }
        }

        [creator_gap] = build_query_plan(data, profile, competitors, audit=audit)
        passes = {item["mode"]: item for item in creator_gap["passes"]}

        self.assertIn("#AIProductAds", passes["mined-hashtag"]["queries"])
        self.assertEqual(
            [query for batch in passes["mined-hashtag"]["batches"] for query in batch],
            passes["mined-hashtag"]["queries"],
        )

    def test_thin_page_still_expands_formats_when_platform_types_are_covered(self) -> None:
        covered_types = [
            "branded / owned IP",
            "branded commercial",
            "educational",
            "UGC testimonial",
        ]
        data = {
            "platforms": {
                "tiktok": {
                    "brand_videos": [
                        {"content_type": content_type}
                        for content_type in covered_types
                    ],
                    "creator_videos": [{"content_type": "educational"}] * 3,
                },
                "instagram": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
                "youtube": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
            }
        }
        profile = {"client_name": "AdAnt", "keyword_seeds": ["AI UGC ads"]}
        competitors = {"confirmed_competitors": [{"name": "Creatify"}]}

        gaps = build_query_plan(data, profile, competitors)
        creator_gap = next(item for item in gaps if item["pool"] == "creator")
        passes = {item["mode"]: item["queries"] for item in creator_gap["passes"]}

        self.assertEqual(creator_gap["content_type_gaps"], [])
        self.assertIn("AdAnt before after", passes["content-type-expansion"])

    def test_query_passes_bound_primary_work_and_preserve_reserve_queries(self) -> None:
        data = {
            "platforms": {
                "tiktok": {"brand_videos": [], "creator_videos": []},
                "instagram": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
                "youtube": {"brand_videos": [{}] * 5, "creator_videos": [{}] * 5},
            }
        }
        profile = {"client_name": "AdAnt", "keyword_seeds": ["AI UGC ads"]}
        competitors = {
            "confirmed_competitors": [
                {"name": f"Competitor {index}"} for index in range(20)
            ]
        }

        gaps = build_query_plan(data, profile, competitors, max_queries_per_pass=24)
        brand_gap = next(item for item in gaps if item["pool"] == "brand")
        product_pass = next(
            item for item in brand_gap["passes"] if item["mode"] == "product-query"
        )

        self.assertEqual(len(product_pass["queries"]), 24)
        self.assertGreater(len(product_pass["reserve_queries"]), 0)
        self.assertEqual(len(product_pass["batches"]), 3)
        self.assertTrue(
            all(len(batch) <= 8 for batch in product_pass["reserve_batches"])
        )


if __name__ == "__main__":
    unittest.main()
