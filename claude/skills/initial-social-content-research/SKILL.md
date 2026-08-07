---
name: initial-social-content-research
description: >-
  Run end-to-end initial social content research from a product URL and brief:
  research the product and competitors, discover TikTok, Instagram Reels, Meta
  Ads, and YouTube Shorts content, curate cross-platform examples, and generate
  a 20-slide AdAnt research report that closes with copy-paste Adant messages
  for the top 5 inspiration videos. Use when an agent needs a first-pass social
  landscape, competitor/content audit, or research deck for a product or brand.
---

# Initial Social Content Research

Produce a source-labeled research workspace and a 20-page content research deck:
13 research pages, then a Sample Content Strategy section that turns the 5
strongest inspiration videos into copy-paste Adant messages. Treat this as
research, not a sales pitch: exclude pricing and deliverables.

## Resolve paths and inputs

1. Resolve `SKILL_DIR` as the directory containing this file and `PLUGIN_ROOT`
   as its grandparent (`SKILL_DIR/../..`). Never assume the caller's current
   directory contains `skills/`.
2. Choose a writable `WORKSPACE_ROOT` outside `PLUGIN_ROOT`. Put every generated
   artifact, browser profile, thumbnail, and report there.
   Set `ADANT_SOCIAL_DATA_DIR` to `WORKSPACE_ROOT/.runtime` before invoking any
   browser component so persistent profiles never land in the plugin install.
3. Obtain only missing required inputs: product website URL and natural-language
   product context. Default `preparedFor` to blank, `timeRange` to `3months`,
   and `targetCountry` to `US` unless the user specifies them.
4. Read [references/initial-social-content-research.anyt](references/initial-social-content-research.anyt)
   before execution for the exact CLI flags, intermediate schemas, curation
   thresholds, and report mapping. Translate every relative `skills/...` path
   in that reference to an absolute path below `PLUGIN_ROOT`.

## Preflight

- Require Python 3.11+, `uv`, Node.js/npm, and Google Chrome. Confirm AdAnt CLI
  authentication with a read-only command such as `npx @anyloop/adant-cli credit balance`;
  if missing, ask for `npx @anyloop/adant-cli auth login`. Never request a Gemini or other
  upstream model-provider key and never write credentials into the plugin or project.
- Explain that TikTok and Instagram may require an interactive login in the
  dedicated research browser. Do not copy, expose, or log cookie contents.
- Read a component skill's `SKILL.md` before invoking its runtime. Model-backed
  components use authenticated AdAnt agent or media API calls; browsing and report
  components remain deterministic/local.
- Preserve raw source URLs and label fallbacks in JSON. Never present inferred
  or search-fallback metrics as directly browsed platform data.

## Run the workflow

1. **Product profile:** run `product-research` with the URL and notes. Read its
   `brand_folder`, create that folder below `WORKSPACE_ROOT`, and place the
   profile there.
2. **Competitors:** run `competitor-research`; derive confirmed competitors from
   Tier 1 and Tier 2. In autonomous mode, accept those tiers and record that
   choice. Otherwise, offer one concise review checkpoint.
3. **Keywords:** run the TikTok and Instagram keyword skills and derive a
   YouTube-native list. For apps, retain explicit `app`, `app review`, and
   category-app variants in organic searches.
4. **Platform research:** run TikTok, Instagram Reels, Meta Ads Library, and
   YouTube Shorts research. Parallelize only independent processes and never
   launch two instances that compete for the same fixed CDP port. Use the
   documented fallbacks when login or indexing blocks a platform and record the
   fallback source.
5. **Curation:** select roughly five official brand/competitor examples and five
   organic creator examples per organic platform. Apply the reference's
   engagement floors to creators only, keep no more than three videos per
   account, and cover at least three formats per platform.
6. **Report data:** assemble `report_data.json` from evidence, not invented
   claims. Include direct platform/ad URLs, source labels, and local thumbnails.
7. **Sample content strategy:** pick the 5 strongest inspiration videos from the
   curated set — rank by engagement, then cloneability and format diversity, at
   most one per account and at least two platforms. Write each as a
   `strategies.items` entry using the `social-content-strategist` block shape
   (avatar, hook to keep, what to change, 2-3 overlay lines). Read that skill's
   `SKILL.md` first; the deck reuses its General Instructions verbatim.
8. **Report:** run `social-content-research-report`, then
   `slide-pdf-generator`, using absolute runtime paths under `PLUGIN_ROOT` and
   output paths under `WORKSPACE_ROOT`.

## Verify and deliver

- Confirm the HTML, Markdown, and PDF exist.
- Confirm the PDF has exactly 20 landscape pages (13 research + opener + 5
  strategies + closing), no placeholder/gray thumbnail boxes, no clipped
  content, and no pricing or deliverables.
- Confirm every featured example has a usable URL, account, metric, format, and
  source label; disclose missing or fallback platform coverage.
- Confirm each of the 5 strategy messages names a real inspiration URL that also
  appears in the research slides, and that no URL or account repeats across
  them.
- Return clickable paths to the report and a short inventory of intermediate
  artifacts. Do not claim completion if the report renderer or required
  validation fails.
