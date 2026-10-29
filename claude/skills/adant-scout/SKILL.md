---
name: adant-scout
description: Find relevant Reddit/X conversations and real creators through AdAnt’s cloud Scout.
---

# AdAnt Scout

Follow the [authentication preflight](../adant/references/authentication.md)
and [durable task procedure](../adant/references/projects.md).

Select the Scout specialist by the requested outcome:

- Reddit listening: `agentKey: "adant-reddit-listener"`, `projectType: "social_listening"`.
- X/Twitter listening: `agentKey: "adant-x-listener"`, `projectType: "social_listening"`.
- Real UGC creators/influencers: `agentKey: "adant-creator-scout"`, `projectType: "creator_discovery"`.

Unspecified listening defaults to Reddit. For both platforms, complete Reddit
then start X, preserve both task ids and return both reports; do not claim one
platform covered the other. Include the product, audience, competitors,
watchlist, own handles and requested timeframe. Listening yields reply drafts,
not posted replies. Creator scouting preserves the user’s hard filters and
source strategy; no automatic outreach or claims of hiring availability.

The host agent handles conversation and planning. Execute the work through
`adant_agent_start`; AdAnt runs the current private cloud skills through its
own APIs. Discover account access first; never export private skill code or
substitute local/provider execution when a specialist is unavailable.
