from __future__ import annotations

import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))

from brief_layout import (
    BRIEF_COVER_CATEGORY,
    STRATEGY_TAG,
    brief_slide_numbers,
    is_brief,
    trim_to_brief,
)
from build_deck import TEMPLATE_PATH, build_ads_grid, build_markdown, build_vid_grid, validate_platform


def brief_data() -> dict:
    video = {"handle": "@maker", "metric": "1.2M views", "format": "POV", "url": "https://www.tiktok.com/@maker/video/1"}
    return {
        "layout": "strategy_brief",
        "cover": {"clientName": "Acme", "reportSubtitle": "Fresh ideas", "clientContact": "Ann", "reportDate": "2026-09-15"},
        "platforms": {
            "tiktok": {"creator_headline": "Creators lead.", "creator_videos": [video]},
            "youtube": {"brand_videos": [], "creator_videos": []},
        },
        "meta_ads": {"headline": "Two advertisers.", "ads": [{"advertiser": "Acme"}]},
        "strategies": {
            "headline": "Five to make",
            "items": [
                {
                    "title": "The morning search",
                    "url": video["url"],
                    "handle": "@maker",
                    "platform": "tiktok",
                    "why_this_video": "It works.",
                    "avatar": "Mia",
                }
            ],
        },
    }


class BriefLayoutTest(unittest.TestCase):
    def test_only_a_brief_is_a_brief(self) -> None:
        self.assertTrue(is_brief(brief_data()))
        self.assertFalse(is_brief({}))
        self.assertFalse(is_brief({"layout": "research"}))

    def test_keeps_the_cover_and_only_the_slots_that_hold_videos(self) -> None:
        self.assertEqual(brief_slide_numbers(brief_data()), [1, 6, 9])
        without_ads = brief_data()
        without_ads["meta_ads"] = {"ads": []}
        self.assertEqual(brief_slide_numbers(without_ads), [1, 6])

    def test_trims_and_renumbers_the_template(self) -> None:
        html, pages = trim_to_brief(TEMPLATE_PATH.read_text(), brief_data())
        self.assertEqual(pages, 3)
        self.assertIn("SLIDE 01 — COVER", html)
        self.assertIn("SLIDE 06 — TIKTOK", html)
        self.assertIn("SLIDE 09 — META ADS", html)
        for dropped in ("SLIDE 02", "SLIDE 05", "SLIDE 07", "SLIDE 12", "SLIDE 13"):
            self.assertNotIn(dropped, html)
        self.assertIn('<div class="page-num">02</div>', html)
        self.assertIn('<div class="page-num">03</div>', html)
        self.assertNotIn('<div class="page-num">04</div>', html)
        self.assertNotIn('<div class="page-num">06</div>', html)
        self.assertIn(BRIEF_COVER_CATEGORY, html)
        self.assertIn(STRATEGY_TAG, html)
        self.assertIn("{{ttCreatorGridHtml}}", html)
        self.assertNotIn("{{execSummaryHeadline}}", html)

    def test_platform_validation_relaxes_the_page_minimum_for_a_brief(self) -> None:
        section = brief_data()["platforms"]["tiktok"]
        self.assertEqual(validate_platform("TikTok", section, brief=True), [])
        self.assertTrue(
            any("only 1 cards" in w for w in validate_platform("TikTok", section))
        )

    def test_a_video_without_a_thumbnail_keeps_its_card(self) -> None:
        video = brief_data()["platforms"]["tiktok"]["creator_videos"][0]
        grid = build_vid_grid([video], "tiktok")
        self.assertIn('class="vid-card"', grid)
        self.assertIn('<div class="pf">TIKTOK</div>', grid)
        self.assertNotIn("<img", grid)
        self.assertIn("<img", build_vid_grid([{**video, "thumb": "t.jpg"}], "tiktok"))
        ads = build_ads_grid([{"advertiser": "Acme", "ad_id": "1"}])
        self.assertIn('class="ad-card"', ads)
        self.assertNotIn("<img", ads)

    def test_markdown_skips_the_narrative_sections(self) -> None:
        md = build_markdown(brief_data())
        self.assertTrue(md.startswith("# Acme — Content Strategy Brief"))
        self.assertIn("## TikTok — Organic Creators", md)
        self.assertNotIn("## TikTok — Brand & Competitor", md)
        self.assertIn("## Meta Ads — Creative Reference", md)
        self.assertIn("### Strategy 1 — The morning search", md)
        for gone in ("## Executive Summary", "## The Landscape", "## Content Format Patterns", "## About Adant AI"):
            self.assertNotIn(gone, md)
        self.assertNotIn("## Recommended Hashtags", md)

    def test_markdown_renders_the_hashtag_recommendation_before_the_strategies(self) -> None:
        data = brief_data()
        data["hashtags"] = {
            "max_per_post": 5,
            "pools": {"brand": ["#acme"], "niche": ["#morningroutine", "#coffee"], "competitor": ["#rival"], "community": ["#coffeetok"]},
            "sets": {
                "tiktok": {"default": ["#acme", "#morningroutine", "#coffee", "#rival", "#coffeetok"], "competitor": ["#acme", "#rival", "#coffee"]},
                "youtube": {"default": ["#acme", "#coffee", "#rival"], "competitor": ["#acme", "#rival", "#coffee"]},
            },
        }
        data["strategies"]["items"][0]["hashtags"] = ["#acme", "#morningroutine", "#coffeetok"]
        md = build_markdown(data)
        self.assertIn("## Recommended Hashtags", md)
        self.assertIn("**At most 5 per post", md)
        self.assertIn("- **Brand:** #acme", md)
        self.assertIn("| TikTok | #acme #morningroutine #coffee #rival #coffeetok | #acme #rival #coffee |", md)
        self.assertNotIn("| Instagram Reels |", md)
        self.assertIn("**Hashtags:** #acme #morningroutine #coffeetok", md)
        self.assertLess(md.index("## Recommended Hashtags"), md.index("### Strategy 1"))
        # Without ads the brief still renders the section, once.
        data["meta_ads"] = {"ads": []}
        self.assertEqual(build_markdown(data).count("## Recommended Hashtags"), 1)


if __name__ == "__main__":
    unittest.main()
