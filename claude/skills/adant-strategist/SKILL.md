---
name: adant-strategist
description: Research products, competitors and social content and build saved strategies through AdAnt’s cloud Strategist.
---

# AdAnt Strategist

Follow the [authentication preflight](../adant/references/authentication.md)
and [durable task procedure](../adant/references/projects.md).

Use `agentKey: "adant-research-agent"` and `projectType: "research"`.
Pass the product, requested research scope, source reports and seed references.
The server owns discovery, analysis, evidence standards and report creation.
Use the same task for report revisions. Preserve source report ids and citations;
never rebuild a report from a truncated digest or invent missing evidence.

The host agent handles conversation and planning. Execute the work through
`adant_agent_start`; AdAnt runs the current private cloud skills through its
own APIs. Discover account access first; never export private skill code or
substitute local/provider execution when a specialist is unavailable.
