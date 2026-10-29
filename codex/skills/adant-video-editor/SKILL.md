---
name: adant-video-editor
description: Edit, caption, stitch and render videos with AdAnt server agents and the account-enabled video editor.
---

# Adant Video Editor

Before work, follow the [authentication preflight](../adant/references/authentication.md).

Follow the [durable project procedure](../adant/references/projects.md).
Select `agentKey: "adant-video-editor"` with `adant_agent_start` after checking capabilities.

Use `projectType: "video_editing"`. Supply existing project/media references or
completed uploads, exact edit instructions, target duration/aspect ratio and
export requirements. AdAnt owns the editing tools and rendering. Honor returned
capability limits; never build an HTML canvas substitute or use a local renderer
to evade the AdAnt workflow. Report the actual render/artifact state.
This edits videos; it does not find or hire human editors.
