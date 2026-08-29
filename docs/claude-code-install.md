# Install AdAnt in Claude Code

## Requirements

- A current local Claude Code installation with plugin support.
- A browser for AdAnt sign-in and OAuth consent.
- `uv` for local research tools. `uv` provisions Python automatically.

Remote Claude surfaces may not support local marketplace installation or the
interactive login flow. Complete setup in local Claude Code.

## Install

```bash
claude plugin marketplace add https://github.com/anyloop/agent-plugin.git
claude plugin install adant@adant-ai
```

## Sign in

The plugin-managed MCP server is named `plugin:adant:adant`:

```bash
claude mcp login plugin:adant:adant
```

If the command needs a true interactive terminal, use the packaged helper:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/skills/adant-claude-setup/scripts/login-adant.sh"
```

## Verify

```bash
claude plugin list
claude mcp get plugin:adant:adant
```

Start a new Claude Code conversation after installation so the AdAnt skills
and tools are loaded. Reconnect if the MCP reports `insufficient_scope`.

## Update

```bash
claude plugin marketplace update adant-ai
claude plugin update adant@adant-ai
```

Start a new conversation after updating.

## Remove

```bash
claude plugin uninstall adant@adant-ai
claude plugin marketplace remove adant-ai
```
