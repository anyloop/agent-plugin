# AdAnt Agent Plugin

Research current social trends, build strategies, and create or clone short-form
video ads with AdAnt from Codex or Claude Code. One plugin connects each host to
the authenticated AdAnt MCP server at `https://api.adant.ai/mcp`.

## What's included

- `codex/` — the Codex plugin package and MCP configuration.
- `claude/` — the Claude Code plugin package and MCP configuration.
- `.agents/plugins/marketplace.json` — the Codex marketplace catalog.
- `.claude-plugin/marketplace.json` — the Claude Code marketplace catalog.

## Install in ChatGPT desktop

Open **Plugins**, add `https://github.com/anyloop/agent-plugin.git` as a personal
marketplace on `main`, then install AdAnt from **Personal** and complete the
connection prompt. Start a new task after installation. If a connection needs
repair in that fresh task, reopen AdAnt under **Installed** or **Personal**;
the desktop app does not require the separate `codex` terminal command.

## Install in Codex CLI

```bash
codex plugin marketplace add anyloop/agent-plugin --ref main
codex plugin add adant@adant-ai
```

Codex CLI opens AdAnt OAuth during installation. To reconnect later, run
`codex mcp login adant` only from a terminal where the Codex CLI is installed.
See [the Codex guide](docs/codex-install.md).

## Install in Claude Code

```bash
claude plugin marketplace add https://github.com/anyloop/agent-plugin.git
claude plugin install adant@adant-ai
claude mcp login plugin:adant:adant
```

See [the Claude Code guide](docs/claude-code-install.md) for verification,
reconnection, and update steps.

See [Social research setup](docs/social-research.md) for local prerequisites,
platform sessions, and workspace safety.

## Try it

- “Create a 15-second vertical product ad with AdAnt.”
- “Clone this reference ad for my product, but keep my brand voice.”
- “Research current TikTok, Instagram, and YouTube trends for this product.”
- “Turn this research into eight distinct content strategies.”

Generation can spend AdAnt credits. The packaged skills require confirmation
before submitting credit-spending work. Project ownership comes from the AdAnt
account authorized through OAuth; the AdAnt MCP does not ask for or store API
keys.

AdAnt account access uses one MCP login. Some local social-research adapters
also require Python 3.11+, `uv`, Chrome, a user-provided Gemini API key, or an
interactive TikTok/Instagram session. These credentials are used by their
respective local or third-party tools and must never be committed to a project.

## Support

For product information, visit [adant.ai](https://adant.ai). For help, email
[contact@anyloop.ai](mailto:contact@anyloop.ai). Please report suspected
security issues privately as described in [SECURITY.md](SECURITY.md).
