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
Gemini/provider key. Local tools require `uv`, which provisions the locked
Python runtime automatically, so no system Python or Node.js install is needed.
Before authenticated work, the plugin verifies the remote AdAnt connection and
any required local credential. A failed or unverified connection stops the
workflow with the observed error and host-specific recovery instructions.
Platform search uses AdAnt's suppliers without a user social account. Chrome
is used for public/existing-session gap filling and PDF export; inaccessible
pages are evidence gaps, not instructions to sign in to TikTok or Instagram.
Hosts that cannot render the live MCP App receive a tokenized local-only
progress URL.

## Support

For product information, visit [adant.ai](https://adant.ai). For help, email
[contact@anyloop.ai](mailto:contact@anyloop.ai).

## Local runtime setup and recovery

If the local MCP server reports that uv is missing, run
`sh /absolute/path/to/plugin/local-server/setup.sh --install-runtime`, or ask
AdAnt initialization to repair the local runtime. This installs uv from Astral
without changing shell profiles and prepares the locked Python environment
outside the MCP startup timeout. Reconnect the local MCP server afterward; if
the host has no reconnect control, start a new task with your original request.
Restarting the desktop app does not install missing dependencies.

You can combine initialization and work in that task: “Initialize AdAnt, then
research this product: <URL>.” No separate post-initialization task is needed.
