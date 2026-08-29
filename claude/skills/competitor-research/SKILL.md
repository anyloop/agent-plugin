---
name: competitor-research
description: Identify true product competitors, distinguish adjacent tools, and gather bounded website/social evidence through AdAnt research tools.
---

# Competitor Research

Call `doctor`; if authentication is missing, mint `research` and bootstrap it
without exposing the token. Run `research_run` phase `competitors` with the
client, product description, website, user-supplied competitors, maximum count,
and an output artifact.

Judge competitors by the user's decision layer, not shared technology. Group
the market into capability clusters and classify each candidate as direct,
partial, adjacent, substitute, or non-competitor. Preserve user-named companies
even when evidence changes their classification.

When browser evidence is needed, use the `control-in-app-browser` skill and its
browser-client selection flow; the runtime prefers the persistent in-app
Browser with Chrome/CDP fallback through the platform phases. Keep browser work
bounded and close workflow-owned tabs.

For each candidate return: product/URL, classification, target user, overlapping
job, key capabilities, differentiators, pricing/positioning evidence, social
proof, sources, confidence, and open questions. End with a comparison matrix and
the 3-5 competitors that most affect positioning.
