"""Local credential verification; remote MCP OAuth belongs to the host."""

from adant_local import api


def local_auth_check() -> dict:
    try:
        api.verify_token(api.load_token())
    except api.ApiError as exc:
        return {
            "name": "adant-auth",
            "ok": False if exc.code in {"not-authenticated", "access-denied"} else None,
            "detail": f"local credential: {exc.code}: {exc}",
            "fix": exc.fix or "Retry local verification after resolving the reported service error",
            "required": True,
        }
    return {
        "name": "adant-auth",
        "ok": True,
        "detail": "local credential verified; remote MCP OAuth not checked",
        "fix": None,
        "required": True,
    }
