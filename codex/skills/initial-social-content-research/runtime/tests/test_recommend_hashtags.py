from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))

from recommend_hashtags import (  # noqa: E402
    MAX_PER_POST,
    brand_tags,
    build_pools,
    compose_set,
    competitor_tags,
    niche_tags,
    recommend,
)

PROFILE = {
    "client_name": "Alinea",
    "is_app": True,
    "keyword_seeds": ["investing for beginners", "how to build wealth", "alinea app"],
}
COMPETITORS = {
    "competitors": [
        {"name": "Coinbase", "tier": "partial_overlap"},
        {"name": "Robinhood", "tier": "direct"},
        {"name": "Acorns", "tier": "direct"},
    ]
}
KEYWORDS = [
    {
        "keyword_categories": {
            "brand": ["alinea app"],
            "niche": ["investing", "build wealth", "stock market for beginners", "invest app"],
            "hook": ["how to start investing", "investing with $100"],
            "competitor": ["robinhood app", "acorns review", "public app"],
            "trend": ["fyp"],
            "tiktok_native": ["fintok", "moneytok"],
        },
        "tiktok_native_keywords": ["fintok", "moneytok"],
    }
]
AUDIT = {
    "platforms": {
        "tiktok": {
            "creator_candidates": [
                {
                    "caption": "Investing early feels like a cheat key ngl #wealth #investing #alineaapp #fyp",
                    "relevance": {"test": "exact-client-product", "specificity": 3},
                },
                {
                    "caption": "random montage #viral #moneytok",
                    "relevance": {"test": "general-topic", "specificity": 1},
                },
            ]
        }
    }
}


class RecommendHashtagsTest(unittest.TestCase):
    def test_brand_tags_lead_with_the_app_form_for_an_app(self) -> None:
        self.assertEqual(brand_tags(PROFILE), ["#alineaapp", "#alinea"])
        self.assertEqual(brand_tags({"client_name": "Cobalt Overhead Doors"}), ["#cobaltoverheaddoors"])
        self.assertEqual(brand_tags({}), [])

    def test_competitors_rank_direct_tier_first_and_drop_query_forms(self) -> None:
        self.assertEqual(
            competitor_tags(COMPETITORS, KEYWORDS),
            ["#robinhood", "#acorns", "#coinbase", "#public"],
        )

    def test_niche_tags_put_observed_winner_tags_first(self) -> None:
        tags = niche_tags(PROFILE, KEYWORDS, observed=["#investing", "#wealth"])
        self.assertEqual(tags[0], "#investing")
        self.assertIn("#buildwealth", tags)
        # "invest app" loses its stop word; "$100" loses its symbol.
        self.assertIn("#invest", tags)
        self.assertIn("#investing100", tags)
        self.assertNotIn("#fyp", tags)

    def test_pools_keep_each_tag_in_one_pool_and_mine_only_relevant_posts(self) -> None:
        pools = build_pools(PROFILE, COMPETITORS, KEYWORDS, AUDIT)
        self.assertEqual(pools["observed"], ["#wealth", "#investing", "#alineaapp"])
        self.assertNotIn("#alineaapp", pools["niche"])
        self.assertNotIn("#robinhood", pools["niche"])
        self.assertEqual(pools["community"], ["#fintok", "#moneytok"])

    def test_default_set_is_brand_niche_competitor_community_within_five(self) -> None:
        result = recommend(PROFILE, COMPETITORS, KEYWORDS, AUDIT)
        tiktok = result["sets"]["tiktok"]["default"]
        self.assertEqual(len(tiktok), MAX_PER_POST)
        self.assertEqual(tiktok[0], "#alineaapp")
        self.assertEqual(tiktok[-1], "#fintok")
        self.assertIn("#robinhood", tiktok)
        self.assertEqual(result["sets"]["tiktok"]["competitor"][:3], ["#alineaapp", "#robinhood", "#acorns"])
        self.assertEqual(len(result["sets"]["youtube"]["default"]), 3)
        for platform in result["sets"].values():
            for tags in platform.values():
                self.assertLessEqual(len(tags), MAX_PER_POST)
                self.assertEqual(len(tags), len(set(tags)))
                self.assertNotIn("#fyp", tags)

    def test_a_brand_with_no_research_still_gets_its_own_tag(self) -> None:
        result = recommend({"client_name": "Cobalt Overhead Doors"}, {}, [], None)
        self.assertEqual(result["sets"]["instagram"]["default"], ["#cobaltoverheaddoors"])
        self.assertEqual(result["evidence"]["observed_on_relevant_posts"], 0)

    def test_compose_set_honours_a_smaller_limit(self) -> None:
        pools = build_pools(PROFILE, COMPETITORS, KEYWORDS, AUDIT)
        self.assertEqual(compose_set(pools, limit=2), ["#alineaapp", "#investing"])
        self.assertEqual(compose_set(pools, limit=1), ["#alineaapp"])

    def test_cli_writes_the_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "profile.json").write_text(json.dumps(PROFILE))
            (root / "competitors.json").write_text(json.dumps(COMPETITORS))
            (root / "keywords.json").write_text(json.dumps(KEYWORDS[0]))
            (root / "audit.json").write_text(json.dumps(AUDIT))
            subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME / "recommend_hashtags.py"),
                    "--profile",
                    str(root / "profile.json"),
                    "--competitors",
                    str(root / "competitors.json"),
                    "--keywords",
                    str(root / "keywords.json"),
                    "--audit",
                    str(root / "audit.json"),
                    "--max-per-post",
                    "4",
                    "-o",
                    str(root / "out" / "hashtags.json"),
                ],
                check=True,
                capture_output=True,
            )
            written = json.loads((root / "out" / "hashtags.json").read_text())
            self.assertEqual(written["max_per_post"], 4)
            self.assertEqual(len(written["sets"]["tiktok"]["default"]), 4)
            self.assertEqual(written["sets"]["tiktok"]["default"][0], "#alineaapp")


if __name__ == "__main__":
    unittest.main()
