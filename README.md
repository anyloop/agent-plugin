# AdAnt agent plugin

Research, listen, discover creators, analyze videos, create and edit ads, and
schedule TikTok/Instagram content through AdAnt's authenticated server agents.

## Use AdAnt in Claude

**claude.ai and Claude Desktop.** Open Settings → Connectors, choose Add custom
connector, name it AdAnt, and enter this URL. Select Connect and sign in to
AdAnt. On Team and Enterprise plans, an owner adds the connector first.

```text
https://api.adant.ai/mcp
```

**Claude Code.** Install the plugin, then run `/mcp` in a session, choose
`plugin:adant:adant`, and sign in to AdAnt:

```bash
claude plugin install adant --marketplace anyloop/agent-plugin
```

**Skills for other agents.** `npx skills add anyloop/agent-plugin` installs the
skills. They call AdAnt's MCP server, so also connect `https://api.adant.ai/mcp`
in that agent.

Step-by-step page: [adant.ai/claude-plugin](https://adant.ai/claude-plugin).

## What you can ask

- “Research my product: https://example.com.”
- “Find what is working on TikTok and Instagram for this product and its
  competitors.”
- “Turn this research into eight content strategies.”
- “Create a 15-second vertical product ad with an AI creator.”

## ChatGPT and Codex

Add this repository as the `adant-ai` marketplace and install AdAnt. Complete
AdAnt OAuth; no provider API keys or local research runtime are needed. See
[ChatGPT and Codex](https://adant.ai/chatgpt-plugin) and
[the Codex guide](docs/codex-install.md).

## More

- [Install in Claude Code](docs/claude-code-install.md)
- [Research and agent workflows](docs/social-research.md)

## Credits and confirmation

AdAnt runs its private skills and paid data/media operations on its servers.
AdAnt credits are separate from your coding agent's credits. No numeric budget
is needed to start requested work, and limits you supply are respected. Resume
durable projects by id. Read-only account and status requests may be free.
Capabilities depend on your AdAnt account.

Research, listening, creator discovery, creation, editing and recurring tasks
use AdAnt's agents. Listening produces drafts, not posted replies. Publishing
and scheduling require confirmation; platform consent and some editable forms
open in Studio. A creator shortlist does not prove hiring availability.

The repository is generated from AdAnt's application source. Please report
issues through [AdAnt support](mailto:contact@anyloop.ai); do not commit tokens,
private media, customer reports or credentials.

Budget thresholds you choose to set check estimated next-turn and generation admission. They do
not hard-cap in-flight or concurrent spending; final usage can exceed them.
Review actual returned usage rather than treating an estimate as a final charge.

## Meet the ants

![Strategist](https://adant.ai/agents/heads/content-strategist-kit.png)
![Scout](https://adant.ai/agents/heads/social-scout-kit.png)
![Creator](https://adant.ai/agents/heads/video-creator-kit.png)
![Manager](https://adant.ai/agents/heads/social-manager-kit.png)

Invoke AdAnt and say “Introduce the team,” or share your product website URL.
Your first response introduces the four ants with the same animated portraits
as Studio (text fallback in terminals). After connection and credit checks, a
bare product URL starts Strategist research followed by Scout listening on
Reddit and X. You get saved reports and suggestions for Creator and Manager;
video creation and calendar work begin when you request them. Explicit tasks
keep their scope. Installation alone does not send a chat message.

## Cloud roles in your coding task

Your host subscription agent handles the conversation, planning and review.
AdAnt executes each requested task through its authenticated APIs using the
same private cloud specialists and current skills:

| Role | Work |
| --- | --- |
| Strategist | Product/competitor research and saved content strategies |
| Scout | Reddit/X listening and creator shortlists |
| Creator | Video analysis, creation, cloning and timeline editing |
| Manager | Account planning, posts and recurring AdAnt tasks |

Start with `adant_get_capabilities`, then `adant_agent_start` with an available
`agentKey` and supported `projectType`. Recover prior work with
`adant_list_agent_tasks`; continue using its existing project id. The optional
Ads Buyer pilot is exposed only when the account allows it. No private skill
bodies or executable research code are distributed in the plugin.

Native scheduled-task confirmations carry the proposed fields for review;
TikTok posting settings and platform consent still use Studio when required.
Account gates and consent requirements match the cloud; installation alone
does not enable a restricted capability.
