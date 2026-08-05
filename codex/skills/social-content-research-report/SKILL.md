---
name: social-content-research-report
description: >-
  Generate a Social Content Research deck (13 landscape 16:9 slides, Adant AI
  brand) from cross-platform research data — TikTok, Instagram Reels + Meta Ads,
  YouTube Shorts. Content-focused, NOT a pitch: no pricing, no deliverables. ~10
  contents per platform (brand/competitor + organic creators), diverse formats,
  max 3 videos per account. Closes with a one-page About Adant AI product
  overview and "Let's connect" slide. Use with the initial-social-content-research workflow.
---

# Social Content Research Report

Generate a **Social Content Research** deck: 1280×720 landscape slides in the **Bunli/Adant design system** — Dark Ink surfaces (`#0c0a09`, card `#16130f`) for cover and closing slides, warm light surfaces (`#f5f5f4`, white cards, `#e7e5e4` hairlines) for content slides, EB Garamond 300 serif headlines with *italic terracotta accents* (`<em>` in any headline renders italic `#c0653f` on light / `#e8a888` on dark), Inter body, JetBrains Mono for stats/labels/metrics, aurora radial glows (`#5ea0ff`/`#9b7be8`/`#f0a07a`), film-grain + vignette video cards, and an aurora gradient-border recommendation card. Print-safe: no `filter: blur`, no `background-clip: text` (Chrome printToPDF can't render either — glows are plain radial-gradients, gradient text is replaced by solid accents). This is the **content-research sibling** of `client-pitch-slides`, different intent:

| | `client-pitch-slides` | **`social-content-research-report`** |
|---|---|---|
| Intent | Sell an engagement | **Show what content works in the niche** |
| Pricing / Deliverables slides | Yes (slides 11-12) | **None** |
| Contents per platform | 3-5 examples | **~10 (2 slides per platform: brand + organic)** |
| Agency intro | About + Cases slide | **Folded into the final "Let's connect" slide** |
| Brand mark | SHORTFLOW | **ADANT AI** |

## Slide Catalog (13)

1. **Cover (dark)** — "Social Content Research" category, client name in giant serif, subtitle, prepared-for, date
2. **Executive Summary** — 3 numbered findings + "What This Means For Content" block
3. **The Landscape** — tight 2-3 sentence paragraph + big hero stat card
4. **Competitive Field** — 3 tier rows (leader / active / the opening)
5. **TikTok — Brand & Competitor Content** — 5 portrait video cards
6. **TikTok — Organic Creator Content** — 5 portrait video cards
7. **Instagram — Brand & Competitor Reels** — 5 cards
8. **Instagram — Organic Creator Reels** — 5 cards
9. **Meta Ads — Creative Reference** — 3×2 ad creative grid (each card deep-links to its specific ad in the Ad Library via `ad_id`; keyword search only as fallback)
10. **YouTube Shorts — Brand & Competitor** — 5 cards
11. **YouTube Shorts — Organic Creators** — 5 cards
12. **Content Format Patterns** — 2×2 format cards synthesizing what works cross-platform
13. **About Adant AI (dark)** — headline "Research to action. *Built for you.*", concise product overview, 3 capability cards, optional case-study phones populated only with verified public or user-approved evidence, adant.ai button + `contact@anyloop.ai`

## Content Rules (the whole point of this report)

- **~10 contents per platform** — 5 brand/competitor + 5 organic creator per platform (8+ acceptable, flag below that). Meta Ads adds 6 more creatives on the Instagram side.
- **Minimum engagement (organic creators only)** — creator cards need **≥50K views/likes**; when a niche is thin, the floor relaxes to **≥10K**, never lower. `build_deck.py` warns on 10K-50K creator cards and flags anything under 10K for removal. **Brand/competitor cards have no engagement floor at all**: never pre-filter them at 10K (or any other threshold); show the top official posts available because weak brand numbers are themselves a finding. If no official brand/competitor content is found, the deck renders a brand-specific empty state without implying that a view floor was applied.
- **Max 3 videos per account** across a platform — enforced by `build_deck.py` as a warning (`--strict` makes it fail). Diversity of voices beats depth on one account.
- **Diverse content formats** — each video card carries a format tag (POV SKIT, TALKING HEAD, STREET INTERVIEW, UGC DEMO, MEME, VLOG…). Aim for 3+ distinct formats per platform; the validator flags less.
- **No market-state claims** the research can't support. No pricing, no deliverables, no engagement scope anywhere.

## Usage

Final report files are named `{product_name}_social_content_research_{date}` (lowercase product slug, date as `YYYY-MM-DD`), e.g. `example-product_social_content_research_YYYY-MM-DD.pdf`. The deck ships as **PDF + markdown** (HTML kept as the clickable review copy).

1. Consolidate research into `report_data.json` (schema below).
2. Build the HTML + markdown:

```bash
uv run --project skills/social-content-research-report/runtime \
  skills/social-content-research-report/runtime/build_deck.py \
  --data {brandFolder}/report_data.json \
  -o {brandFolder}/{product_name}_social_content_research_{date}.html \
  --md {brandFolder}/{product_name}_social_content_research_{date}.md
```

3. Render the PDF with the `slide-pdf-generator` skill:

```bash
python3 skills/slide-pdf-generator/runtime/to_pdf.py \
  {brandFolder}/{product_name}_social_content_research_{date}.html \
  {brandFolder}/{product_name}_social_content_research_{date}.pdf --wait 8
```

## `report_data.json` Schema

```json
{
  "cover": {
    "clientName": "Example App",
    "reportSubtitle": "What short-form content wins in GenZ dating, and where Example App fits.",
    "clientContact": "Example Team",
    "reportDate": "Month YYYY"
  },
  "exec": {
    "execSummaryHeadline": "GenZ dating content is creator-led, not brand-led.",
    "finding1": "…", "finding2": "…", "finding3": "…",
    "execRecommendation": "…"
  },
  "landscape": {
    "landscapeHeadline": "…", "landscapeCopy": "…",
    "heroStatNumber": "2.3M", "heroStatSup": "+",
    "heroStatLabel": "…", "heroStatPlatforms": "TIKTOK · REELS · YT SHORTS"
  },
  "competitive": {
    "tier1Header": "…", "tier1Brand": "…", "tier1Badge": "Scale", "tier1Desc": "…",
    "tier2Header": "…", "tier2Brand": "…", "tier2Badge": "Active", "tier2Desc": "…",
    "tier3Header": "…", "tier3Brand": "…", "tier3Badge": "Now", "tier3Desc": "…"
  },
  "platforms": {
    "tiktok": {
      "brand_headline": "…", "brand_intro": "…",
      "brand_videos": [
        {"url": "https://www.tiktok.com/@x/video/1", "thumb": "thumbnails/tiktok-1.jpg",
         "handle": "@x", "metric": "1.2M likes", "format": "POV SKIT"}
      ],
      "creator_headline": "…", "creator_intro": "…",
      "creator_videos": [ …same shape… ]
    },
    "instagram": { …same shape… },
    "youtube":   { …same shape… }
  },
  "meta_ads": {
    "headline": "…", "intro": "…", "cropped": false,
    "ads": [{"advertiser": "Example Brand", "ad_id": "1234567890", "thumb": "thumbnails/ad-example.jpg"}]
  },
  "formats": {
    "formatsHeadline": "Four formats the niche rewards.",
    "format1Tag": "…", "format1Name": "…", "format1Desc": "…",
    "format2Tag": "…", "format2Name": "…", "format2Desc": "…",
    "format3Tag": "…", "format3Name": "…", "format3Desc": "…",
    "format4Tag": "…", "format4Name": "…", "format4Desc": "…"
  },
  "connect": {
    "aboutAdantCopy": "<strong>AdAnt AI</strong> turns research into action: live trend data surfaces relevant concepts, then <strong>AI agents and UGC creators</strong> help produce adaptable content across <strong>UGC, animation, and TVC</strong>.",
    "connectUrl": "https://adant.ai", "connectLinkText": "adant.ai",
    "connectContact": "contact@anyloop.ai",
    "heroMetricNumber": "3", "heroMetricLabel": "Social platforms researched",
    "heroMetric2Number": "13", "heroMetric2Label": "Presentation-ready slides",
    "heroMetric3Number": "1", "heroMetric3Label": "Research-to-creative workflow",
    "case1_brand": "Verified Case One", "case1_stat": "Add approved result",
    "case1_url": "https://adant.ai",
    "case1_thumb": "thumbnails/case-1.jpg",
    "case2_brand": "Verified Case Two", "case2_stat": "Add approved result",
    "case2_url": "https://adant.ai",
    "case2_thumb": "thumbnails/case-2.jpg",
    "case3_brand": "Verified Case Three", "case3_stat": "Add approved result",
    "case3_url": "https://adant.ai",
    "case3_thumb": "thumbnails/case-3.jpg"
  }
}
```

Grid blocks (`ttBrandGridHtml`, `adsGridHtml`, …) are generated by `build_deck.py` — never hand-write them. The grid auto-sizes 3/4/5 columns from the video count (5 max per slide).

## Asset Conventions

`thumbnails/` folder sibling to the HTML:

- `tiktok-{video_id}.jpg` — TikTok oEmbed `thumbnail_url` (`https://www.tiktok.com/oembed?url=…`)
- `ig-{shortcode}.jpg` — Instagram Reel poster (yt-dlp or page og:image)
- `yt-{video_id}.jpg` — `yt-dlp --skip-download --write-thumbnail --convert-thumbnails jpg`
- `ad-{slug}.jpg` — Meta Ads creative from `creative_urls` (signed CDN URLs expire in hours — download right after the browse run)
- `case-{n}.jpg` — Adant AI case-study posters (TikTok oEmbed)

Verify no placeholder images before PDF: `find thumbnails -name '*.jpg' -size -15k -print` — anything under 15 KB is suspect.

## Fitting Rules

- Every slide must fit 1280×720 with `overflow: hidden` — cut copy first, never the visual.
- Video slides (`.slide-vids`): title 38px, intro 14px; the 9:16 grid auto-centers. If you change `.vid-grid--5` max-width (1000px), re-test that 5 cards + format pills fit.
- Ads slide fits 6 square creatives; use `"cropped": true` only for Library-page screenshot crops.
- No em/en dashes in body copy; use commas, colons, ` · `. Bold `<strong>` sparingly (numbers, brand names).
- **Keep copy tight — the deck is visual, not an essay.** Hard length guidance: findings ≤ 2 sentences (~180 chars), platform/ads intros 1-2 sentences (~150 chars), tier descriptions ≤ 2 short sentences, format descriptions 1 sentence + one receipt number, recommendation ≤ 2 sentences. If a sentence doesn't carry a number or a decision, cut it.
- Put `<em>…</em>` around ONE key phrase in each headline (`execSummaryHeadline`, `landscapeHeadline`, platform headlines, `adsHeadline`, `formatsHeadline`) — it renders as the design system's italic terracotta accent. Never nest tags inside the `<em>`.
