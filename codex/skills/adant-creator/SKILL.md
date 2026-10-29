---
name: adant-creator
description: Analyze, create, clone and edit videos through AdAnt’s cloud Creator.
---

# AdAnt Creator

Follow the [authentication preflight](../adant/references/authentication.md)
and [durable task procedure](../adant/references/projects.md).

Select `agentKey: "adant-social-video"` for production and analysis. Use
`projectType: "video_analysis"` for analysis only, `clone` for a reference remake,
and `product_ugc`, `template`, `avatar_video` or `custom` for production.
For an existing video timeline, use `agentKey: "adant-video-editor"` with
`projectType: "video_editing"`; new footage remains production. Pass the
existing task/media references and exact desired changes; editing an existing
Studio timeline may require its original task rather than a fresh project.
Do not generate for an analysis-only request. With only a product and an ad
request, offer optional research once and explain its credit cost; do not
start research without the user selecting it. A supplied video, template,
script or strategy can go directly to production.

The host agent handles conversation and planning. Execute the work through
`adant_agent_start`; AdAnt runs the current private cloud skills through its
own APIs. Discover account access first; never export private skill code or
substitute local/provider execution when a specialist is unavailable.
