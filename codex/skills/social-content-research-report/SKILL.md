---
name: social-content-research-report
description: Build and deliver the fixed 13-slide AdAnt social-content research report from validated research data, including thumbnails, markdown, PDF, and optional Studio save.
---

# Social Content Research Report

Require validated report data. Call `research_run` phase `report` variant `build`
with strict validation to produce HTML and markdown, then variant `pdf` for the
PDF. Slide order is fixed: brand/competitor first, then organic creator evidence.

The 13 slides cover: title, product/audience, landscape, TikTok brand, TikTok
creators, Instagram brand, Instagram creators, YouTube brand, YouTube creators,
Meta ads, cross-platform patterns, five primary strategies, and next steps with
three reserves. Missing thumbnails use an intentional placeholder; missing
required evidence fails strict mode.

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
