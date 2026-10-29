---
name: adant-social-manager
description: Plan, schedule and publish TikTok and Instagram content, manage accounts and recurring AdAnt tasks.
---

# Adant Social Manager

Before work, follow the [authentication preflight](../adant/references/authentication.md).

Follow the [durable project procedure](../adant/references/projects.md).
Select `agentKey: "adant-social-manager"` with `adant_agent_start` after checking capabilities.

Use `projectType: "social_publishing"`. State the intended account, platform,
video/library references, caption constraints and requested schedule. Ask AdAnt
to read connected accounts, existing posts/tasks and the account clock/timezone
before planning or changing anything; do not create duplicate tasks on resume.
Resolve ambiguous dates or a missing timezone before scheduling. Distinguish
a one-time post from a recurring agent task; recurring work uses AdAnt, not
the coding host scheduler, and subsequent runs consume AdAnt credits.

Publishing, connecting/disconnecting accounts and schedule changes require the
returned confirmation or Studio form. For TikTok direct posts the user chooses
privacy, interactions and commercial disclosure. Never preselect those fields,
claim a draft is published, or bypass a reconnect/plan/feature restriction.
Relay the returned post/task id and actual status, including failures.
