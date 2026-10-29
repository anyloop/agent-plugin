---
name: adant-manager
description: Plan and manage social accounts, TikTok/Instagram posts and recurring AdAnt tasks through the cloud Manager.
---

# AdAnt Manager

Follow the [authentication preflight](../adant/references/authentication.md)
and [durable task procedure](../adant/references/projects.md).

Use `agentKey: "adant-social-manager"` with `projectType: "social_publishing"`.
Include account/platform, content references, goal and requested dates/cadence.
Ask the server to read existing accounts, posts/tasks and timezone before any
change. Recurring work belongs to AdAnt, not the coding host scheduler.
It runs the cloud role on the agreed cadence and spends AdAnt credits.

For a `scheduled_task` interaction, show the returned proposed settings and
collect the user’s choices; submit only supported fields through the native
response schema. List/reuse existing tasks before proposing another.
TikTok posting privacy, interactions and commercial disclosure remain the
user’s choices; follow any required Studio consent link. A pending form or
approved proposal is not proof that a post was published or a task was saved.

The host agent handles conversation and planning. Execute the work through
`adant_agent_start`; AdAnt runs the current private cloud skills through its
own APIs. Discover account access first; never export private skill code or
substitute local/provider execution when a specialist is unavailable.
