---
name: social-content-research-report
description: >-
  Generate a Social Content Research deck (13 research slides + an optional
  Sample Content Strategy section, landscape 16:9, Adant AI brand) from
  cross-platform research data — TikTok, Instagram Reels + Meta Ads, YouTube
  Shorts. Content-focused, NOT a pitch: no pricing, no deliverables. ~10
  contents per platform (brand/competitor first, then organic creators), diverse formats,
  max 3 videos per account. Closes with a one-page About Adant AI product
  overview, then copy-paste Adant messages for the top inspiration videos.
  Use with the initial-social-content-research workflow.
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

## Slide Catalog (13 research slides + 7 strategy slides when `strategies` is supplied)

1. **Cover (dark)** — "Social Content Research" category, client name in giant serif, subtitle, prepared-for, date
2. **Executive Summary** — 3 numbered findings + "What This Means For Content". Lead on the **content-type distribution** (which types are occupied and at what ceiling), not a platform recap — platforms get slides 5-11. Every finding carries a measured number.
3. **The Landscape** — tight 2-3 sentence paragraph + big hero stat card
4. **Competitive Field** — 3 tier rows (leader / active / the opening)
5. **TikTok — Brand & Competitor Content** — 5 portrait video cards
6. **TikTok — Organic Creator Content** — 5 portrait video cards
7. **Instagram — Brand & Competitor Reels** — 5 cards
8. **Instagram — Organic Creator Reels** — 5 cards
9. **Meta Ads — Creative Reference** — 3×2 ad creative grid (each card deep-links to its specific ad in the Ad Library via `ad_id`; keyword search only as fallback)
10. **YouTube Shorts — Brand & Competitor** — 5 cards
11. **YouTube Shorts — Organic Creators** — 5 cards
12. **Content Format Patterns** — 2×2 cards for the **four content types** (branded/owned IP · branded commercial · educational story/animation · UGC testimonial; swap or add a type where the category differs). Each card names who occupies that type and its measured ceiling, so the slide maps open ground instead of listing styles.
13. **About Adant AI (dark)** — headline "Research to action. *Built for you.*", concise product overview, 3 capability cards, optional case-study phones populated only with verified public or user-approved evidence, adant.ai button + `contact@anyloop.ai`

### Sample Content Strategy (slides 14+, only when `strategies.items` is non-empty)

14. **Section opener (dark)** — headline + intro, and the **General Instructions** block shown *once* for the whole section (analyze → first-frame review → script rewrite → Seedance 2.0), verbatim from `content-strategy-generator`
15–19. **One slide per strategy** — the inspiration video card (9:16 thumbnail, handle, metric) beside a copy-paste message in the exact `generate_strategies.py` shape:

```text
analyze <inspiration url>

Avatar: <TYPE> — <specific look>

Keep: <what carries over, and why>

Change: <how the product swaps in>

Overlay:
<2-3 short lines, last one the product tag>
```

One idea per line, url alone on the first — that is what keeps the block
copyable out of the PDF without unintended breaks. Blank separators render as
an empty `.msg-gap` div, never `&nbsp;`, so a copy cannot pick up an invisible
U+00A0 that pastes as hidden garbage.

**A PDF text layer is one run per rendered line however it is built**, so a
viewer copy always carries those line breaks. `build_deck.py` therefore also
writes `{output_stem}_strategies.txt` beside the deck — every message in full,
select-all-and-paste — and the markdown deck carries the same blocks fenced.
Point the reader at the .txt when they want to copy, at the PDF when they want
to present. `keep` / `change` supersede
`hook_to_keep` / `what_to_change`; the renderer still accepts the old keys.

20. **Start creating (dark)** — closing headline, the adant.ai button again, and `contact@anyloop.ai`

The section is rendered by `runtime/strategy_slides.py`, which also numbers the pages. Omit `strategies` entirely and the deck stays at 13 slides — older `report_data.json` files keep working unchanged.

## Content Rules (the whole point of this report)

- **Slide order is fixed: brand/competitor first, then organic creator, per platform.** Brand content establishes the category context and positioning before the deck shows creator formats a reader can adapt. The body stays organised BY PLATFORM — content types are a cross-cutting tag, never a regrouping.
- **~10 contents per platform** — target 5 brand/competitor + 5 organic creator cards; **4 per page is the production minimum**. `build_deck.py --strict` rejects any page below four instead of allowing one full page to mask an empty sibling page. Meta Ads adds 6 more creatives on the Instagram side.
- **Do not turn an empty card slot into report copy.** Hand a thin brand or creator pool back to `initial-social-content-research`; run every primary query batch, then reserve batches while the page remains below four. Continue toward five relevant cards from a 12-candidate buffer. The expansion must include entity-qualified content-type phrases and hashtags mined from relevant candidates. Never render below four cards; methodology stays in `curation_audit.json`, never on the slide.
- **Minimum engagement (organic creators only)** — creator cards start at **≥50K views/likes**. Relax to **≥10K**, then **≥1K**, only after targeted product, competitor, use-case, content-type, and relevant-hashtag top-ups cannot fill five cards. A no-minimum verified-niche fallback is the last resolution when four relevant cards still cannot be filled at 1K. Any sub-50K floor requires `creator_top_up_complete: true` plus a concrete gap note; the relevance gate never relaxes. `build_deck.py` surfaces incomplete fallback evidence for review. **Brand/competitor cards have no engagement floor at all**: use the strongest official posts and disclosed or clearly attributable paid creator/KOC/KOL placements, because partnership UGC is part of the brand's distribution strategy.
- **Max 3 videos per account** across a platform — enforced by `build_deck.py` as a warning (`--strict` makes it fail). Diversity of voices beats depth on one account.
- **On-category only** — every card must show the client's or a named competitor's product, show the job the product does, or state the problem it solves. Content that merely shares a technology, aesthetic, or topic does not qualify no matter how it performs, and it usually performs better: an AI-generated crime drama at 301K likes and an "Usher but make it AI" remix at 104K both out-ranked every genuine AI-character-app post in one run. Curate for relevance first, then rank the survivors by engagement.
- **Diverse content formats** — each video card carries a format tag (POV SKIT, TALKING HEAD, STREET INTERVIEW, UGC DEMO, MEME, VLOG…). Aim for 3+ distinct formats per platform; the validator flags less.
- **Diverse content types** — once both platform pages meet the four-card minimum, require at least three distinct content types across them. Use content-type expansion queries before accepting a one-lane deck.
- **No market-state claims** the research can't support. No pricing, no deliverables, no engagement scope anywhere. When a slot is empty because a platform was never reached (login wall, dead fallback), set `brand_empty_note` / `creator_empty_note` to say so — the default empty state blames the engagement floor, which turns a coverage gap into a false finding about the niche.
- **An empty result is never a market claim.** `meta_ads.empty_note` must describe the capture, not the category: "these advertisers returned no ads in this run" is supportable, "nobody in this category advertises" is not. One deck asserted a whole category ran no paid social while Alarmy, Opal and WakeClock were all live — the searches had silently returned zero for five of six queries.
- **Slides contain insights, not the audit trail.** Never put rejected candidates, excluded titles, failed or zero-result queries, blank captions, missing handles, threshold exceptions, or search methodology in reader-facing copy. Preserve all of that evidence in `curation_audit.json`. If a coverage limitation changes the conclusion, compress it to one clause and state only the resulting decision.
- **Video-card pages get one short insight, maximum two sentences.** This applies to every `brand_intro`, `creator_intro`, and `meta_ads.intro`. Prefer one sentence; use two only when the second changes the decision. The cards already carry the account, metric, and format, so the intro must not narrate each card.

Bad: "Canva has the highest eligible post at 57K. Several product candidates were excluded because handles were missing, four searches returned blank captions, and no official TPT or Tes channel appeared."

Good: "Canva leads YouTube at 57K views; Twinkl and Teach Starter remain below 3K. Tutorials are the clearest brand format."

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
uv run --project skills/slide-pdf-generator/runtime \
  skills/slide-pdf-generator/runtime/to_pdf.py \
  {brandFolder}/{product_name}_social_content_research_{date}.html \
  {brandFolder}/{product_name}_social_content_research_{date}.pdf --wait 25
```

`--wait` is a readiness cap, not a fixed sleep: rendering continues as soon as
the document, fonts, images, and two layout frames are ready.

4. Save it to AdAnt — see **Save to AdAnt** below.

## Save to AdAnt (the handoff)

The deck's copy-paste messages are the fallback. The real handoff saves the
report into the user's AdAnt Drive, where every strategy has a **Start in
Studio** button that opens a project with the brief as its first message.
It needs the AdAnt Remote MCP (`adant_*` tools) — skip the whole section
when those tools are not connected, and say so in the closing message.

`runtime/handoff.py` does the file work around three MCP calls:

```bash
REPORT_RUNTIME="skills/social-content-research-report/runtime"
H="$REPORT_RUNTIME/handoff.py"
# 1. list every thumbnail + the deck files → the adant_prepare_uploads input
uv run --project "$REPORT_RUNTIME" "$H" manifest --data {brandFolder}/report_data.json \
  --pdf {brandFolder}/{stem}.pdf --html {brandFolder}/{stem}.html \
  --audit {brandFolder}/curation_audit.json -o {brandFolder}/.handoff/manifest.json
```

2. Call `adant_prepare_uploads` with the manifest's `files` array and write
   the tool result to `{brandFolder}/.handoff/slots.json`.

```bash
# 3. PUT each file to its presigned URL → the adant_complete_uploads input
uv run --project "$REPORT_RUNTIME" "$H" upload \
  --manifest {brandFolder}/.handoff/manifest.json \
  --slots {brandFolder}/.handoff/slots.json -o {brandFolder}/.handoff/uploads.json
```

4. Call `adant_complete_uploads` with `uploads.json`'s `uploads` array and
   write the result to `{brandFolder}/.handoff/completed.json`.

```bash
# 5. assemble the adant_save_product_report input
uv run --project "$REPORT_RUNTIME" "$H" payload \
  --data {brandFolder}/report_data.json \
  --manifest {brandFolder}/.handoff/manifest.json \
  --completed {brandFolder}/.handoff/completed.json \
  --uploads {brandFolder}/.handoff/uploads.json \
  --source chatgpt -o {brandFolder}/.handoff/save.json
```

6. Call `adant_save_product_report` with `save.json`'s `payload`. The result
   carries `url` (the Studio report page), `versionNo`, and `warnings[]`.

Rules:

- **Re-running for the same product in one conversation: pass
  `--report-id <reportId>` from the previous save** so the new version joins
  the existing report instead of forking a lineage on a renamed client.
  Saving is append-only; nothing is overwritten.
- `payload` writes each strategy's exact `message` (via `strategy_message`)
  into the data — the web sends it verbatim, so never edit the brief by hand
  after this step.
- `--source` is `chatgpt`, `codex`, or `claude` — whichever host is running.
- Read `warnings[]` back to the user in one line when non-empty (missing
  thumbnails, empty `keep`/`change`, a `format` that is really a relationship
  label). They are the server telling the skill what to fix next run.
- Close with the link: "Saved to your AdAnt Drive — open it at <url> to read
  the report and start any strategy in Studio." Keep the copy-paste blocks in
  the PDF; they are the offline path.

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
      "creator_videos": [ …same shape… ],
      "brand_empty_note": "optional — replaces the empty-state sentence",
      "creator_empty_note": "optional — same, for the creator slot"
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
  "strategies": {
    "headline": "Five videos to clone. <em>Start here.</em>",
    "intro": "Each slide pairs one proven video from this research with a message you can paste straight into Adant.",
    "closingHeadline": "Paste a message. <em>Get a video.</em>",
    "closingCopy": "Open Adant, paste any of the five messages, review the first frame, then generate.",
    "items": [
      {
        "title": "The 3am doomscroll confession",
        "platform": "tiktok",
        "format": "POV SKIT",
        "metric": "1.2M likes",
        "posted": "YYYY-MM-DD",
        "handle": "@examplecreator",
        "url": "https://www.tiktok.com/@examplecreator/video/1",
        "thumb": "thumbnails/tiktok-1.jpg",
        "why_this_video": "One sentence carrying the number or decision that earned it a slot.",
        "avatar": "TYPE — specific look. UGC / Animation (3D|anime|2D|Pixar|claymation|ink-wash) / Commercial / Cinematic actor / Narrator-only / Product-only, derived from the video's analysis — never defaulted to UGC",
        "keep": "the reuse axis and why: the hook | the viral format | the visual style | the structure | the pacing | the format inverted",
        "change": "one sentence — how the product swaps in",
        "style": "optional extra art-direction line",
        "overlays": ["short overlay line", "second line", "Example Product: Ingredient Scanner"]
      }
    ]
  },
  "connect": {
    "aboutAdantCopy": "<strong>AdAnt AI</strong> turns research into action: live trend data surfaces relevant concepts, then <strong>AI agents and UGC creators</strong> help produce adaptable content across <strong>UGC, animation, and TVC</strong>.",
    "connectUrl": "https://adant.ai", "connectLinkText": "adant.ai",
    "connectContact": "contact@anyloop.ai",
    "heroMetricNumber": "3", "heroMetricLabel": "Social platforms researched",
    "heroMetric2Number": "20", "heroMetric2Label": "Presentation-ready slides",
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
- **Keep copy tight — the deck is visual, not an essay.** Enforced budgets: cover subtitle ≤140 characters/2 sentences; findings, recommendation, and landscape copy ≤180 characters/2 sentences each; platform/ads intros ≤160 characters/2 sentences; tier and format descriptions ≤140 characters/1 sentence; strategy intro/closing ≤160 characters/2 sentences; `why_this_video` ≤140 characters/1 sentence. Prefer one sentence everywhere. Run `build_deck.py --strict`; oversized copy or audit-language on video-card pages fails validation. If a sentence explains the research process instead of carrying a number, insight, or decision, move it to `curation_audit.json`.
- Strategy slides (`.strat-slide`) fit a message of roughly 12 monospace lines beside the 224px video card. Keep `why_this_video` to one sentence, `avatar` / `hook_to_keep` / `what_to_change` to one sentence each, and overlays to 3 short lines — a longer message overflows the card.
- Put `<em>…</em>` around ONE key phrase in each headline (`execSummaryHeadline`, `landscapeHeadline`, platform headlines, `adsHeadline`, `formatsHeadline`) — it renders as the design system's italic terracotta accent. Never nest tags inside the `<em>`.
