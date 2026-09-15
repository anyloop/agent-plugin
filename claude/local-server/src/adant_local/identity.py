"""Where this install keeps its data, and who it says it is.

Both live here for one reason: the device id is half of a credential. Local
`alt_*` tokens are bound to it server-side — `findActiveByHash(hash, deviceIdHash)`
matches on both — so a process that answers "who am I" differently from the
process that minted the token authenticates as nobody, and the server can only
answer 401. That failure carries no clue about its cause, which is exactly why
there must be one implementation rather than one per client.

Stdlib only, deliberately: `api.py` runs inside the local server with httpx
available, `inference.py` runs inside each phase's own `uv` project where it
is not. Both import this module, so keep it importable from both.
"""

from __future__ import annotations

import json
import os
import platform
import secrets
from pathlib import Path


def data_dir() -> Path:
    """The plugin's per-install data directory, host-provided or defaulted."""
    root = (
        os.environ.get("PLUGIN_DATA", "").strip()
        or os.environ.get("CLAUDE_PLUGIN_DATA", "").strip()
    )
    return Path(root) if root else Path.home() / ".adant" / "plugin-data"


def token_file() -> Path:
    return data_dir() / "local-token.json"


def device_identity() -> dict[str, str]:
    """Return a stable opaque id and recognizable name for this install.

    Creates the identity on first use. Every later caller reads it back, so
    the id a token was minted for is the id every request presents.
    """
    identity_file = data_dir() / "device.json"
    try:
        saved = json.loads(identity_file.read_text())
        device_id = saved["device_id"]
        device_name = saved["device_name"]
        if isinstance(device_id, str) and isinstance(device_name, str):
            return {"device_id": device_id, "device_name": device_name}
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        pass

    node = platform.node().strip()
    system = platform.system().strip() or "Local device"
    device_name = f"{system} · {node}" if node else system
    identity = {
        "device_id": secrets.token_urlsafe(32),
        "device_name": device_name[:100],
    }
    identity_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = identity_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(identity))
    temporary.chmod(0o600)
    temporary.replace(identity_file)
    return identity


def device_id() -> str:
    return device_identity()["device_id"]
