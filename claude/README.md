# AdAnt for Claude Code

Run AdAnt's current server agents from Claude Code: research products and competitors,
listen to Reddit and X, find creators, analyze videos, create or clone ads, edit
videos, and plan TikTok/Instagram posts and recurring tasks.

Connect the plugin to `https://api.adant.ai/mcp` using AdAnt OAuth. Install from
[the public marketplace](https://github.com/anyloop/agent-plugin), complete the
AdAnt connection prompt and start a new task to discover its tools. See the
public repository's [installation guides](https://github.com/anyloop/agent-plugin/tree/main/docs).

## What runs where

The plugin contains thin workflow adapters. AdAnt executes its private agent
skills, data collection, analysis, media generation and task scheduling on its
servers. Agent work, paid data and media use AdAnt credits **in addition to** the
coding agent's credits; read-only account/status operations may be free.
Agree on agent and media budgets before starting. Model or agent availability
and feature restrictions come from the authenticated account's capabilities.

The plugin installs only the remote AdAnt MCP. No local research server, Python,
uv, Chrome automation, social research login or provider API key is required.
For local assets use the AdAnt upload flow or upload through Studio.

## Workflows

- `content-research`: product, competitor and social research with saved reports.
- `adant-social-listening`: Reddit/X findings and reply drafts; does not post replies.
- `adant-find-creators`: evidence-backed creator shortlists; no automatic outreach.
- `adant-analyze`: video structure and creative analysis.
- `adant-create-ad` / `adant-clone-ad`: complete creative projects.
- `adant-video-editor`: editing, captions, stitching and rendering.
- `adant-social-manager`: account audits, TikTok/Instagram posts and recurring tasks.
- `adant-init`: connection and capability verification.

Projects return durable ids. Resume the same project after disconnection; do
not resubmit paid work with a new key. Review actual credit usage and returned
artifacts. Pending work is not a completed report, render or published post.
Publishing and scheduling require explicit confirmation. Some platform consent,
TikTok posting choices and editable forms must be completed at the returned
Studio link. The plugin does not invent account settings or bypass those forms.
Creator discovery does not establish that a person offers video-editing services
or is available to hire; the video editor workflow edits media in AdAnt.

If authentication fails, reconnect the existing AdAnt connection and retain
project ids. Missing tools alone do not prove an expired login. Never use a
browser scraper or another provider to bypass unavailable AdAnt capabilities.

For help, contact [AdAnt support](mailto:contact@anyloop.ai).

Budget thresholds check estimated next-turn and generation admission. They do
not hard-cap in-flight or concurrent spending; final usage can exceed them.
Review actual returned usage rather than treating an estimate as a final charge.

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
