#!/bin/sh
set -eu

case "${1:-}" in
  ''|--check-runtime|--prepare) ;;
  *) printf '%s\n' 'adant-local: unknown bootstrap option' >&2; exit 2 ;;
esac

# GUI hosts start MCP servers with a minimal PATH. Locate uv in its standard
# install directories, then let uv provision Python and the locked environment.
find_uv() {
  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return 0
  fi

  for candidate in \
    "$HOME/.local/bin/uv" \
    "$HOME/.cargo/bin/uv" \
    "$HOME/.linuxbrew/bin/uv" \
    "/opt/homebrew/bin/uv" \
    "/home/linuxbrew/.linuxbrew/bin/uv" \
    "/usr/local/bin/uv" \
    "/usr/bin/uv"
  do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

if ! uv_bin="$(find_uv)"; then
  printf '%s\n' \
    "adant-local: uv is required but was not found." \
    "Run the plugin's local-server/setup.sh --install-runtime, then reconnect the local MCP server." \
    "Python does not need to be installed; uv provisions it automatically." >&2
  exit 127
fi

server_root="$(CDPATH= cd "$(dirname "$0")" && pwd)"
export PATH="$(dirname "$uv_bin")${PATH:+:$PATH}"

case "${1:-}" in
  --check-runtime) exec "$uv_bin" --version ;;
  --prepare) exec "$uv_bin" sync --frozen --no-dev --project "$server_root" ;;
esac

exec "$uv_bin" run \
  --frozen \
  --no-dev \
  --project "$server_root" \
  "$server_root/src/adant_local/server.py"
