# Social research setup

The single AdAnt plugin covers the complete creative loop:

```text
Product research → Trend discovery → Strategy → Media and ad generation
```

AdAnt account access and generation use the plugin's one OAuth MCP connection.
Some research skills run local, locked Python adapters because TikTok,
Instagram, Meta Ads Library, and YouTube do not share that AdAnt session.

## Local prerequisites

Check everything in one pass instead of discovering gaps mid-run:

```bash
python3 <plugin root>/runtime/doctor.py
```

The doctor reports Python, `uv`, Node.js, Chrome, `yt-dlp`, AdAnt
authentication, and both platform sessions together, each failure with its fix
command. It only reads state; it never opens windows or starts a login flow.


- Python 3.11 or newer and `uv`.
- Google Chrome.
- `GEMINI_API_KEY` for skills that use Gemini search, browser control, or video
  understanding.
- `yt-dlp` for inspiration-video analysis.
- An interactive TikTok or Instagram login when those platforms require it.

Never paste keys or cookies into chat or commit them to a project. Provide keys
through the process environment. The plugin does not copy or display browser
cookies.

## Keep runtime data outside the plugin

Choose a writable research workspace and place persistent browser state below
it:

```bash
export ADANT_SOCIAL_DATA_DIR="/absolute/path/to/research/.runtime"
```

Store reports, downloads, screenshots, history, and generated decks in the
same external workspace. Installed plugin directories may be replaced during
an update and must remain free of credentials and user data.

## Host support

The same social skills ship for Codex and local Claude Code. Browser-dependent
workflows require a local desktop environment; remote or web-only agent hosts
may provide research through their own browsing tools but cannot run the local
Chrome adapters directly.
