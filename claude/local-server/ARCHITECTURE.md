# AdAnt plugin v2 local server

Implementation of `docs/design/plugin-v2-refactor-2026-08.md` — one standard
plugin: thin skills + remote MCP + one local stdio MCP + widgets. Tool
contracts are frozen in `docs/design/plugin-v2-r1-schemas.md`.

- `local-server/` — `adant-local`, the FastMCP stdio server owning
  everything that must run on the user's machine: doctor preflight,
  research fan-out, platform sessions, scoped local-file media upload /
  analysis / editing, durable workflow/budget gates, and the live progress
  panel. The panel is built with the official MCP Apps SDK into a content-hashed
  single-file asset and has a tokenized 127.0.0.1 HTTP fallback. The POSIX
  launcher locates `uv`; `uv` provisions Python and the frozen production
  environment, so users do not need a system Python installation.
  Run: `uv run adant-local` · Test: `uv run pytest`.

R1 became the default research execution surface in #596. R2 removed the v1
runtime after moving its token-authenticated inference client here. The shared
event format and workflow plan keep existing workspaces readable without a
parallel execution path.

The remote half stays in `apps/server`: its 20 base tools consume a committed
contract generated from OpenAPI operation IDs, while creative-project,
local-token, and report workflow tools remain hand-authored. This keeps local
browsing and file work separate from the remotely governed API surface.
