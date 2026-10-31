---
name: adant
description: Run AdAnt's authenticated server agents for research, social listening, creator discovery, video analysis, ad creation, video editing, scheduling and TikTok/Instagram publishing. Also manage AdAnt media, credits and library assets. Use when a user shares a product or brand URL with AdAnt to introduce the ant team and start a research and social-listening brief.
---

# Use AdAnt

On the first AdAnt interaction, follow the [team welcome and product URL kickoff](references/welcome.md). A bare product URL requests research plus Reddit/X listening, subject to user-supplied limits and capability checks. Explicit narrower requests take precedence.

Follow the [authentication preflight](references/authentication.md), then
[the durable project procedure](references/projects.md) for substantive work.
The host subscription agent handles the conversation, planning and review.
Use `adant_agent_start` to execute substantive work on AdAnt’s cloud specialists;
AdAnt runs their current private skills and tools on its own servers.
Agent work, paid data and media consume AdAnt credits in addition to the
coding agent's credits. Report actual usage; do not promise every read is paid.

## Choose the cloud role

Read `adant_get_capabilities`: use each agent’s `role`, `projectTypes` and
`taskApi`, and select only an available `agentKey`. The named role adapters are
`adant-strategist`, `adant-scout`, `adant-creator` and `adant-manager`.
The optional Ads Buyer pilot uses `adant-ads-buyer` when enabled.

For work spanning roles, the host keeps the plan and runs the tasks in dependency
order, passing saved report/task/artifact references between them. Preserve all
returned ids; never silently add paid research or generation.

## Route the request

| Request | Project type / skill |
| --- | --- |
| Product, competitor, social content or strategy research | `research` / `content-research` |
| Reddit or X listening and reply drafts | `social_listening` / `adant-social-listening` |
| Find UGC creators or influencers | `creator_discovery` / `adant-find-creators` |
| Create a complete ad | `adant-create-ad` |
| Clone or adapt a reference ad | `clone` / `adant-clone-ad` |
| Edit, caption, stitch or render a video | `video_editing` / `adant-video-editor` |
| Analyze a reference video | `video_analysis` / `adant-analyze` |
| Account audit, recurring tasks, TikTok/Instagram posts | `social_publishing` / `adant-social-manager` |
| Initialize or repair the connection | `adant-init` |

Keep execution in the authenticated AdAnt tools. Missing capabilities are
reported as gaps; never substitute browser scraping, local research scripts,
a provider API, a host automation, or a separate coding agent for paid AdAnt
work. Do not download or reconstruct AdAnt's private agent instructions.

## One explicit media asset

For an explicit single image, video or voice request, discover models with
`adant_list_media_models` / `adant_get_media_model`, present the model and
available credit estimate, and explain that generation consumes AdAnt credits.
Proceed with the requested generation without asking for a numeric budget or
exact-cost approval; respect any limits the user supplied.
Call the matching remote generation tool with a fresh idempotency key.
Read the returned job with `adant_get_media_job`; reuse the original key and
identical arguments for an uncertain retry. Never invent model controls.

## References and local files

Use owner-scoped library tools or the remote prepare/upload/complete flow.
Upload only to the returned upload destination, then complete the upload and
use its verified file id. A prepared slot is not a completed file. If the host
cannot transfer the bytes, ask the user to upload in Studio and reuse the
returned asset; do not pretend a local path is server-visible. No local MCP
server, social login, Python runtime or provider key is required.

Return the project/job id, current status, saved report or artifact links,
actual AdAnt usage and any pending user decision. Queued work is not complete.
