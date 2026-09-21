---
name: content-research
description: Research products, social videos and content strategies through the same durable server jobs as AdAnt Studio, then save an evidence-backed report. No local runtime, browser, or PDF rendering required.
---

# Content Research

Follow the [authentication preflight](../adant/references/authentication.md).
Before paid work, verify that `adant_research_profile`, `adant_research_collect`,
`adant_research_analyze`, `adant_research_seeds`, `adant_research_status` and
`adant_research_save` are available. A missing tool is a capability gap; stop
with the observed error rather than starting a local research workflow.

Read and follow the [shared web research procedure](references/workflow.md).
Its scope, evidence standards, seed exclusions, hashtag rules and report
contract are generated from AdAnt's web workflow and apply to both hosts.

Create a fresh UUID as `researchId` for this run and retain it in the
conversation. Pass it to profile, collect, seeds, analyze and save, with a
stable `idempotency_key` per distinct operation. Resume with the same IDs and
identical arguments; a new run needs a new researchId. Never reuse another
run's analysis references as proof that this run watched its videos.

Profile, seed reads and analysis return an `operationId` immediately. Call
`adant_research_status(operationId=..., waitSeconds=25)` until it completes
or fails, updating the user at least once a minute. Keep the exact operation
ID across interruptions: running means work continues on the server. Local
sleep does not cancel queued jobs; host reasoning resumes when the host does.
On resume, recover completed results before evaluating the remaining budget.

Compose the report directly in `adant_research_save`'s `data` argument, with
`source: "codex"` or `"claude"` for the active host. Public thumbnail URLs are
stored by the server. Return the saved report's ID/URL and evidence gaps;
PDF export is on the report page. An incomplete evidence set gets a partial
report. Never substitute `research_run`, browser gap filling, local files,
HTML/PDF rendering or an upload sequence for the server workflow.
