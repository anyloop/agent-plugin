"""Authenticated AdAnt agent inference for packaged research skills.

This adapter deliberately shells out without a shell so prompts and user input are
passed as literal arguments. AdAnt owns the model credentials and usage accounting;
plugin users only authenticate with AdAnt.
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any


ADANT_CLI = ["npx", "--yes", "@anyloop/adant-cli"]
AUTH_ERROR_MARKERS = (
    "http 401",
    "status: 401",
    "not authenticated",
    "authentication required",
    "not logged in",
    "unauthorized",
)


class AdantAgentError(RuntimeError):
    """Raised when the authenticated AdAnt CLI cannot complete a request."""


def _run(args: list[str], timeout: int) -> str:
    try:
        result = subprocess.run(
            [*ADANT_CLI, *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise AdantAgentError("Node.js/npx is required to run AdAnt research.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        if any(marker in detail.lower() for marker in AUTH_ERROR_MARKERS):
            detail = (
                "AdAnt authentication is required. Run "
                "`npx @anyloop/adant-cli auth login` in your system terminal, then "
                "retry. No Gemini API key is needed."
            )
        raise AdantAgentError(detail) from exc
    except subprocess.TimeoutExpired as exc:
        raise AdantAgentError("AdAnt research timed out; retry the step.") from exc
    return result.stdout.strip()


def _parse_json(text: str) -> Any:
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    cleaned = re.sub(r",\s*([}\]])", r"\1", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        first_object = cleaned.find("{")
        last_object = cleaned.rfind("}")
        if first_object >= 0 and last_object > first_object:
            return json.loads(cleaned[first_object : last_object + 1])
        first_array = cleaned.find("[")
        last_array = cleaned.rfind("]")
        if first_array >= 0 and last_array > first_array:
            return json.loads(cleaned[first_array : last_array + 1])
        raise


def ask_adant(
    prompt: str,
    *,
    json_output: bool = True,
    title: str = "Plugin research",
    timeout: int = 900,
) -> Any:
    """Run one isolated AdAnt agent turn and return JSON or response text."""

    created = _run(
        [
            "session",
            "create",
            "--agent",
            "adant-agent",
            "--title",
            title,
            "--json",
        ],
        timeout=120,
    )
    session_id = json.loads(created)["id"]
    try:
        response = _run(
            ["session", "chat", prompt, "--session_id", session_id],
            timeout=timeout,
        )
        return _parse_json(response) if json_output else response
    finally:
        try:
            _run(["session", "delete", "--session_id", session_id], timeout=60)
        except AdantAgentError:
            pass
