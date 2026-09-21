---
name: adant
description: Use AdAnt through its authenticated remote and local MCP tools for credits, media models, generation, jobs, local-file media, and creative workflows. Trigger when the user mentions AdAnt, requests AI ad media, or provides a local asset for AdAnt processing.
---

# Use AdAnt

Before work, follow the [authentication preflight](references/authentication.md);
return early with its recovery instructions if a required check fails.

Use only the connected AdAnt MCP tools. Never ask for provider keys or replace a
missing AdAnt tool with an unrelated generator.

## Choose the surface

- Remote `adant_*` tools: credits, capabilities, model discovery, generation,
  durable jobs, library data, uploads, reports, and creative projects.
- Local `media_local`: upload, analyze, or edit a file from the user's machine.
- `adant-create-ad` / `adant-clone-ad`: multi-step ads with approvals.
- `content-research` / `initial-social-content-research`: server research and a saved Studio report.
- `social-content-strategist`: new content ideas from example videos, a
  report, or a niche, delivered as a saved strategy brief with one-click Create in Studio and on-demand PDF export.
- `adant-init`: first-run connection and readiness help.

Report missing tools using the preflight evidence; do not infer OAuth failure
from absence alone or prescribe a restart without a diagnosed cause.

## Remote media workflow

1. Use `adant_get_capabilities` when availability is uncertain.
2. Discover with `adant_list_media_models`; inspect model-specific controls
   with `adant_get_media_model`.
3. Present the exact model, count, dimensions/duration, and quoted credits.
4. Obtain explicit approval before a credit-spending call.
5. Call the matching generate tool with a fresh idempotency key.
6. Report the durable job id. Read it later with `adant_get_media_job`; cancel
   only with explicit authorization.

Do not invent controls or claim completion while a job is queued/running. Reuse
an idempotency key only for the identical logical request.

## Local files

Call `doctor` first. If local authentication is absent, mint the minimum scopes
needed by passing the fields of its `device` to `adant_mint_local_token`; pass
the token directly to `auth_bootstrap` and never echo it in chat.

- Upload: `media_local(action="upload", path=<file>, params={})`.
- Analyze: use action `analyze` with `prompt` and optional `response_format`,
  `model`, and `output_path`.
- Edit: use action `edit` with `prompt` and optional `mask_path`, model/quality,
  output, and wait controls.

Local media requires the `media` scope. Report delivery may additionally request
`report`; research uses `research`.

## Creative projects

Start once, persist the returned project id, and resume with the project tools.
Present every question, picker, or generation confirmation to the user and
respond using the exact interaction id. Never infer approval, expose hidden
reasoning, or hammer a progress tool in one turn.

Finish with the adapter used, model, credit estimate/usage, job or project ids,
artifact links/paths, current state, and any exact pending decision.
