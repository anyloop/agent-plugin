# Repair a missing local runtime

Use this only for an installation or repair request after confirming the local
launcher cannot find uv. This prepares dependencies; research and generation
still run through MCP tools.

Resolve `../../..` from this reference directory to the installed plugin root.
Run `sh "<plugin-root>/local-server/setup.sh" --install-runtime` using the
absolute resolved path. The script downloads Astral's official uv installer
over HTTPS when uv is missing, installs to `~/.local/bin` without modifying shell
profiles, and prepares the locked Python environment. Follow host permissions;
do not repeatedly retry network or permission failures. Report the actual error.

After success, use an available host MCP reconnect control, then re-check tools.
If no control is available, ask for a new task with the original request. A full
app restart is a last resort for stale host state, not a dependency fix.
