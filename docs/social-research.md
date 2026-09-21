# Social research

Codex and Claude Code use the same AdAnt server research workflow as Studio:
profile the product, collect social evidence, analyze selected videos, and
save a report. Start with `$adant-init` or ask for research directly.

## Prerequisites

Authorize the remote AdAnt connection. Research does not require a local
runtime, Chrome, social-account login, provider key, or local file uploads.
If a required remote tool is absent, the plugin names the capability gap
before paid work; update/reconnect the plugin as appropriate for the observed
host status. Missing local tools do not prevent server research.

## Resume and delivery

Each run retains a research ID, operation IDs and idempotency keys. Profile,
seed metadata and analysis jobs execute on the server and survive a sleeping
or disconnected desktop. The host recovers their results before continuing;
reasoning between stages still requires the host to run.

The report is saved directly to AdAnt Studio. Original thumbnail URLs are
stored by the server, and video evidence references are checked during save.
Insufficient evidence produces an explicitly partial report with named gaps.
Use the report page to export PDF; research does not render a local deck.

The full research and fresh-ideas skills share the web workflow's selection,
seed exclusion, hashtag, attempt-budget and report rules. Local tools remain
available for explicitly requested local media, document exports and browser
investigation; their setup is independent of research.
