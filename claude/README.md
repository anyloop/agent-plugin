# AdAnt for Claude Code

The AdAnt Claude Code plugin connects Claude to AdAnt's hosted MCP server and
adds one workflow surface for social research, strategy, media generation, and
creating or cloning short-form ads.

## Install

```bash
claude plugin marketplace add https://github.com/anyloop/agent-plugin.git
claude plugin install adant@adant-ai
claude mcp login plugin:adant:adant
```

Confirm the connection with `claude mcp get plugin:adant:adant`, then start a
new Claude Code conversation so the plugin skills and tools are loaded.

If authentication needs an interactive terminal, run:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/skills/adant-claude-setup/scripts/login-adant.sh"
```

Social-research model work uses the installed AdAnt connection to mint a
short-lived, scoped local token; it does not require a second CLI login or a
Gemini/provider key. Local tools require `uv` and Chrome; `uv` provisions the
locked Python runtime automatically, so no system Python or Node.js install is
needed. Some searches also require an interactive TikTok or Instagram session.
Hosts that cannot render the live MCP App receive a tokenized local-only
progress URL.

## Support

For product information, visit [adant.ai](https://adant.ai). For help, email
[contact@anyloop.ai](mailto:contact@anyloop.ai).
