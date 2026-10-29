---
name: adant-ads-buyer
description: Use the account-enabled AdAnt Ads Buyer pilot for Meta campaigns and reporting.
---

# AdAnt Ads Buyer

Follow the [authentication preflight](../adant/references/authentication.md)
and [durable task procedure](../adant/references/projects.md).

Use `agentKey: "adant-meta-ads"` with `projectType: "meta_ads"` only when
capabilities say it is available. Include the finished creative, connected
account and campaign goal. Making creative belongs to the Creator.
Campaign creation and going live are separate decisions; preserve every
returned confirmation and platform-consent requirement. Never infer spend
authorization from a creative-production request. Report actual campaign
state and evidence, not assumed reach or returns.

The host agent handles conversation and planning. Execute the work through
`adant_agent_start`; AdAnt runs the current private cloud skills through its
own APIs. Discover account access first; never export private skill code or
substitute local/provider execution when a specialist is unavailable.
