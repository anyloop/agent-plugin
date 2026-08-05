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

The AdAnt account uses this single MCP login. Local social-research adapters
may additionally require Python 3.11+, `uv`, Chrome, a Gemini API key, and an
interactive TikTok or Instagram session.

## Support

For product information, visit [adant.ai](https://adant.ai). For help, email
[contact@anyloop.ai](mailto:contact@anyloop.ai).
