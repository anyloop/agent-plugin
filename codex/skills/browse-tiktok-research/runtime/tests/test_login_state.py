import json
import sqlite3
import sys
import time
from pathlib import Path

import browse


def _write_cookie(
    profile: Path,
    *,
    host: str = ".tiktok.com",
    name: str = "sessionid",
    expires_offset: int = 3600,
) -> None:
    cookie_db = profile / "Default" / "Cookies"
    cookie_db.parent.mkdir(parents=True)
    expires_utc = int((time.time() + 11_644_473_600 + expires_offset) * 1_000_000)
    with sqlite3.connect(cookie_db) as connection:
        connection.execute(
            "CREATE TABLE cookies (host_key TEXT, name TEXT, encrypted_value BLOB, "
            "is_persistent INTEGER, expires_utc INTEGER)"
        )
        connection.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?, ?)",
            (host, name, b"encrypted", 1, expires_utc),
        )


def test_login_state_requires_live_tiktok_cookie(tmp_path, monkeypatch):
    monkeypatch.setattr(browse, "CDP_PROFILE_DIR", tmp_path)
    assert browse._check_tiktok_login() is False

    _write_cookie(tmp_path)
    assert browse._check_tiktok_login() is True


def test_login_state_rejects_expired_or_wrong_domain_cookie(tmp_path, monkeypatch):
    monkeypatch.setattr(browse, "CDP_PROFILE_DIR", tmp_path)
    _write_cookie(tmp_path, expires_offset=-60)
    assert browse._check_tiktok_login() is False

    wrong_profile = tmp_path / "wrong-domain"
    monkeypatch.setattr(browse, "CDP_PROFILE_DIR", wrong_profile)
    _write_cookie(wrong_profile, host="nottiktok.com")
    assert browse._check_tiktok_login() is False


def test_login_state_is_unknown_when_cookie_store_is_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(browse, "CDP_PROFILE_DIR", tmp_path)
    cookie_db = tmp_path / "Default" / "Cookies"
    cookie_db.parent.mkdir(parents=True)
    cookie_db.write_text("not sqlite")
    assert browse._check_tiktok_login() is None


def test_login_check_outputs_json_without_launching_chrome(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(browse, "CDP_PROFILE_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["browse.py", "--login-check"])
    monkeypatch.setattr(
        browse.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("launched Chrome")),
    )

    browse.main()

    assert json.loads(capsys.readouterr().out) == {
        "logged_in": False,
        "platform": "tiktok",
    }


def test_login_opens_visible_browser_when_profile_is_available(tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(browse, "CDP_PROFILE_DIR", tmp_path)
    monkeypatch.setattr(browse, "_profile_is_available_for_login", lambda: True)
    monkeypatch.setattr(browse.sys, "platform", "darwin")
    monkeypatch.setattr(
        browse.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("macOS must use Launch Services")
        ),
    )
    monkeypatch.setattr(
        browse.subprocess,
        "run",
        lambda args, **_kwargs: launched.append(args),
    )

    browse.login_to_tiktok()

    assert len(launched) == 3
    assert launched[0][:4] == ["open", "-na", "Google Chrome", "--args"]
    assert "--new-window" in launched[0]
    assert "--headless=new" not in launched[0]
    assert "https://www.tiktok.com/login" in launched[0]
    assert launched[1:] == [
        ["osascript", "-e", 'tell application "Google Chrome" to activate'],
        ["osascript", "-e", 'tell application "Google Chrome" to activate'],
    ]


def test_visible_login_keeps_direct_launch_fallback_outside_macos(
    tmp_path, monkeypatch
):
    launched = []
    monkeypatch.setattr(browse, "CDP_PROFILE_DIR", tmp_path)
    monkeypatch.setattr(browse.sys, "platform", "linux")
    monkeypatch.setattr(
        browse.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("non-macOS must not use Launch Services")
        ),
    )
    monkeypatch.setattr(
        browse.subprocess,
        "Popen",
        lambda args, **_kwargs: launched.append(args),
    )

    browse._launch_visible_login_browser("https://www.tiktok.com/login")

    assert launched[0][0] == browse.CHROME_BIN
    assert "--new-window" in launched[0]


def test_login_refuses_active_profile_owner_and_keeps_locks(
    tmp_path, monkeypatch
):
    lock = tmp_path / "SingletonLock"
    tmp_path.mkdir(exist_ok=True)
    lock.write_text("live")
    monkeypatch.setattr(browse, "CDP_PROFILE_DIR", tmp_path)
    monkeypatch.setattr(browse, "_profile_is_available_for_login", lambda: False)
    monkeypatch.setattr(
        browse.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("launched Chrome")),
    )

    browse.login_to_tiktok()

    assert lock.exists()


def test_research_refuses_active_sign_in_profile_and_keeps_locks(tmp_path, monkeypatch):
    lock = tmp_path / "SingletonLock"
    tmp_path.mkdir(exist_ok=True)
    lock.write_text("live")
    monkeypatch.setattr(browse, "CDP_PROFILE_DIR", tmp_path)
    monkeypatch.setattr(browse, "_owned_research_browser_pid", lambda: 42)
    monkeypatch.setattr(browse, "_is_research_browser_running", lambda: False)
    monkeypatch.setattr(
        browse.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("launched Chrome")),
    )

    assert browse._ensure_chrome_with_cdp() is False
    assert lock.exists()


def test_research_refuses_foreign_cdp_listener(monkeypatch):
    monkeypatch.setattr(browse, "_owned_research_browser_pid", lambda: None)
    monkeypatch.setattr(browse, "_is_research_browser_running", lambda: True)

    assert browse._ensure_chrome_with_cdp() is False


def test_research_correlates_profile_owner_with_cdp_listener(monkeypatch):
    monkeypatch.setattr(browse, "_owned_research_browser_pid", lambda: 42)
    monkeypatch.setattr(browse, "_is_research_browser_running", lambda: True)
    monkeypatch.setattr(browse, "_cdp_listener_pid", lambda: 43)
    assert browse._ensure_chrome_with_cdp() is False

    monkeypatch.setattr(browse, "_cdp_listener_pid", lambda: 42)
    assert browse._ensure_chrome_with_cdp() is True


def test_profile_availability_depends_only_on_exact_profile_owner(monkeypatch):
    monkeypatch.setattr(browse, "_owned_research_browser_pid", lambda: None)
    assert browse._profile_is_available_for_login() is True
    monkeypatch.setattr(browse, "_owned_research_browser_pid", lambda: 42)
    assert browse._profile_is_available_for_login() is False


def test_browser_ownership_requires_exact_process_arguments():
    profile = "--user-data-dir=/tmp/research-profile"
    port = "--remote-debugging-port=9333"
    command = f"chrome {profile} {port}"

    assert browse._command_has_exact_argument(command, profile)
    assert browse._command_has_exact_argument(command, port)
    assert not browse._command_has_exact_argument(
        f"chrome {profile}-backup {port}", profile
    )
    assert not browse._command_has_exact_argument(
        f"chrome {profile} {port}0", port
    )


def test_owned_pid_requires_chrome_and_exact_profile(tmp_path, monkeypatch):
    profile_arg = f"--user-data-dir={tmp_path.resolve()}"
    port_arg = "--remote-debugging-port=9333"
    commands = "\n".join(
        [
            f"41 python {profile_arg} {port_arg}",
            f"42 {browse.CHROME_BIN} {profile_arg}-backup {port_arg}",
            f"43 {browse.CHROME_BIN} {profile_arg}",
        ]
    )
    result = type("Result", (), {"stdout": commands})()
    monkeypatch.setattr(browse, "CDP_PROFILE_DIR", tmp_path)
    monkeypatch.setattr(browse.subprocess, "run", lambda *_args, **_kwargs: result)

    assert browse._owned_research_browser_pid() == 43
