---
name: trend-video-understanding
description: Analyze the supplied videos only, including creative structure and promotion evidence.
---

# Trend Video Understanding

Before work, follow the [authentication preflight](../adant/references/authentication.md).

Follow the [durable project procedure](../adant/references/projects.md).

Use the [analysis entrypoint](../adant-analyze/SKILL.md) with
`projectType: "video_analysis"`. Analyze the supplied videos only, including creative structure and promotion evidence.
Pass the requested scope and reference URLs/report ids in the project brief.
The server owns data acquisition, private skills, analysis and report delivery.
Preserve citations and evidence gaps; do not substitute local/browser execution.

Select `agentKey: "adant-social-video"` with `adant_agent_start`.
