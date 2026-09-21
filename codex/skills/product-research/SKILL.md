---
name: product-research
description: Turn a product URL and notes into a sourced profile through AdAnt's durable server profile job.
---

# Product Research

Before work, follow the [authentication preflight](../adant/references/authentication.md);
return early with the observed error if required authentication fails.

Use the profile stage of the [content research workflow](../content-research/SKILL.md): call `adant_research_profile` and wait with `adant_research_status`. Return the sourced product facts, audience, benefits, differentiators, claims, voice, assets and gaps. Separate inference from observed facts. Do not run unrelated collection or report stages for a profile-only request.
