---
name: social-content-research-report
description: Save research and strategy briefs directly to AdAnt Studio with evidence checks and on-demand PDF export.
---

# Social Content Research Report

Before work, follow the [authentication preflight](../adant/references/authentication.md);
return early with the observed error if required authentication fails.

Follow the report contract and save stage of the [content research workflow](../content-research/SKILL.md). Compose `data`, preserve original thumbnail URLs, candidate tiers, sources, gaps, and this run's analysisArtifactId values. Use `adant_research_save` with the same researchId and a stable key. Return the actual saved ID/URL and warnings. PDF export is available from that report page; no local rendering or upload is required. Full reports show brand/competitor evidence before creator evidence; idea requests use `layout: "strategy_brief"`.
