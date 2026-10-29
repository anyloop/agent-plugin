# Research and agent workflows

Start with `$adant-init` to verify the remote AdAnt connection and capabilities,
then state the product, references, goal, scope and budget in ordinary language.

Research and strategy requests start durable `research` projects. AdAnt owns
the current research skills, supplier acquisition, analysis and saved reports.
Listening uses `social_listening`, creator discovery uses `creator_discovery`,
editing uses `video_editing`, and posts or recurring tasks use `social_publishing`.
Ad creation and cloning use the corresponding creative project types.

Agent work, paid data and media consume AdAnt credits separately from the host
coding agent. The plugin checks capabilities and agrees on agent/media budgets.
Status and account reads may be free. Missing features are reported rather than
replaced with local/browser collection or third-party APIs.

Save the returned project id. Resume that project after an interrupted task or
reconnect; an uncertain retry keeps the same idempotency key and arguments.
The plugin returns the actual state, artifacts, usage and pending decisions.
A pending project is not complete and a partial report keeps its evidence gaps.

The installed plugin needs no Python, uv, browser automation or social research
login. Private workflows and execution remain on AdAnt. Upload local references
with the remote upload flow or through Studio; local paths alone are not assets.

Listening drafts are not published replies. TikTok/Instagram posting and schedule
changes require user confirmation; platform consent and some forms use the
returned Studio link. Recurring tasks run in AdAnt and use AdAnt credits.

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
