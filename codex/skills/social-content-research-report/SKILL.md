---
name: social-content-research-report
description: Build and deliver the fixed 13-slide AdAnt social-content research report — or its strategy-brief subset — from validated research data, including thumbnails, markdown, PDF, and optional Studio save.
---

# Social Content Research Report

Local rendering needs no AdAnt login. Before any Studio save or upload, follow
[authentication preflight](../adant/references/authentication.md); return early
from the save on failure and deliver existing local artifacts with the exact error.

Require validated report data. Call `research_run` phase `report` variant `build`
with strict validation to produce HTML and markdown, then variant `pdf` for the
PDF. Slide order is fixed: brand/competitor first, then organic creator evidence.

The 13 slides cover: title, product/audience, landscape, TikTok brand, TikTok
creators, Instagram brand, Instagram creators, YouTube brand, YouTube creators,
Meta ads, cross-platform patterns, five primary strategies, and next steps with
three reserves. Missing thumbnails use an intentional placeholder; missing
required evidence fails strict mode.

## Strategy briefs

Each of the five strategy cards ends in one copy-paste brief, and it is exactly
three lines — the report builder renders it, so never hand-write one:

```text
analyze <inspiration video url>
Recreate the video for <cover.clientName, or the strategy's own `product`>
Change the Avatar: <avatar>
```

The brief asks for a CLOSE recreation. It carries no "keep", "change", "style",
or "overlay" direction: those briefed a bigger departure than the source
warranted, and a proven video is worth cloning because it is reproduced, not
re-premised. Keep writing `keep`, `change`, and `overlays` onto each strategy —
they still render as report context — they are just not pasted.

Those three lines are also what ROUTES the paste: `analyze <url>` plus a source
and a modification note is the high-fidelity-video-clone trigger, so a brief
missing the `analyze` opener or the avatar note can land in template-led
generation instead. Set `cover.clientName` to a brand name or a product URL;
either reads correctly. Per-strategy `product` overrides it for one card.

## Strategy brief layout

`report_data.json` may carry `"layout": "strategy_brief"` — the
social-content-strategist skill's deliverable. The builder then keeps only the
cover, the platform slides whose slot holds videos, the Meta Ads slide when
`meta_ads.ads` is non-empty, and the strategy section, renumbered from the
cover. Strict mode drops the per-page minimum and the format-mix checks for a
brief (a scoped run has fewer videos by design); the per-account cap and the
creator floors still apply. The narrative sections (`exec`, `landscape`,
`competitive`, `formats`, `connect`) are omitted from the data. The save
handoff below is unchanged; the server files a brief under its own report
kind, so it never becomes a new version of the product's full research report.

## Save to AdAnt

1. Call `report_local(action="manifest", params={data, pdf, html, audit})`.
2. Pass its `files` to remote `adant_prepare_uploads`.
3. Call `report_local(action="upload", params={manifest, slots})`.
4. Pass successful uploads to remote `adant_complete_uploads`.
5. Call `report_local(action="payload", params={data, manifest, completed,
   uploads, source})`.
6. Pass its payload to `adant_save_product_report`.

Never report success without the save result's report id and URL. If any handoff
stage fails, deliver the local HTML/PDF/markdown, identify the failed stage, and
say AdAnt Studio was not updated.
