#!/bin/sh
set -eu

# Explicit first-run preparation, outside the host's MCP handshake timeout.
server_root="$(CDPATH= cd "$(dirname "$0")" && pwd)"
if [ "${1:-}" != "--install-runtime" ]; then
  printf '%s\n' 'Usage: sh setup.sh --install-runtime' >&2
  exit 2
fi

# Reuse the launcher's discovery, including GUI hosts with a minimal PATH.
if ! sh "$server_root/bootstrap.sh" --check-runtime >/dev/null 2>&1; then
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT HUP INT TERM
  printf '%s\n' 'adant-local: installing uv without changing shell profiles.' >&2
  curl --proto '=https' --tlsv1.2 -fLsS --connect-timeout 15 --max-time 120 \
    https://astral.sh/uv/install.sh -o "$installer"
  UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh "$installer" >&2
fi

# Warm the locked environment before reconnecting the MCP server.
sh "$server_root/bootstrap.sh" --prepare
printf '%s\n' 'adant-local: runtime ready. Reconnect the local MCP server, or start a new task.' >&2
