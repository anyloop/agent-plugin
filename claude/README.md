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

Social research runs through the same durable server jobs as the web app:
profile, collect, analyze and save. The installed AdAnt connection is the only
research prerequisite; local tools, `uv`, Chrome, social logins, and provider
keys are not required. The plugin checks remote authentication and capability
availability before work. Queued jobs survive a disconnected or sleeping
computer and resume by operation ID; host reasoning resumes with the host.

Reports are saved directly to Studio with their evidence references and
original thumbnail URLs. Export a PDF from the report page when needed.
The shared research procedure is generated from the web workflow and checked
for drift for both plugin hosts. Local tools remain for explicit local-file
media, document export and browser investigation, outside normal research.

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
