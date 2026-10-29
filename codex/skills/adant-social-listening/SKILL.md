---
name: adant-social-listening
description: Listen to Reddit and X for brand, competitor and buyer conversations through AdAnt; draft replies without posting.
---

# Adant Social Listening

Before work, follow the [authentication preflight](../adant/references/authentication.md).

Follow the [durable project procedure](../adant/references/projects.md).

Use `projectType: "social_listening"`. Name Reddit, X or both explicitly in the
brief with product, audience, competitors, topics, watched accounts/subreddits,
recency and the requested report. Include an existing report/watchlist when
available. Ask for sourced conversation findings and reply drafts. Listening
does not post, comment, like, vote, follow, repost or message. Never claim that
a drafted reply was sent. Recurring listening belongs to the AdAnt social
manager task workflow, with the user-approved cadence and timezone.

Follow [Scout routing](../adant-scout/SKILL.md): choose the Reddit or X
`agentKey` explicitly, default to Reddit when no platform is named, and run
Reddit then X when both are requested. Use `adant_agent_start`.
