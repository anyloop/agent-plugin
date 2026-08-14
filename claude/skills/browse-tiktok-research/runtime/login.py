#!/usr/bin/env python3
"""
TikTok Login Helper
Manages TikTok authentication for the search skill.

Supports two login methods:
1. --from-chrome: Import session from your existing Chrome browser (preferred)
2. Interactive: Opens a browser window for manual login

Login state is preserved between runs via persistent browser profile.
Run with: uv run --project runtime runtime/login.py
"""

import json
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import COOKIES_PATH, PROFILE_DIR

SESSION_COOKIE_NAMES = ("sessionid", "sessionid_ss", "sid_guard", "sid_tt", "passport_csrf_token")

# Chrome profile location on macOS
CHROME_PROFILE_DIR = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"


def _has_session_cookies(cookies: list[dict]) -> list[str]:
    """Check if cookies contain TikTok session identifiers."""
    return [c["name"] for c in cookies if c["name"] in SESSION_COOKIE_NAMES]


def is_logged_in() -> bool:
    """
    Check if a valid TikTok login exists by verifying browser profile and cookies.

    Returns True if we have a browser profile with session cookies.
    """
    if not PROFILE_DIR.exists() or not any(PROFILE_DIR.iterdir()):
        return False

    if not COOKIES_PATH.exists():
        return False

    try:
        cookies = json.loads(COOKIES_PATH.read_text())
        session = _has_session_cookies(cookies)
        return len(session) > 0
    except Exception:
        return False


def import_from_chrome() -> bool:
    """
    Import TikTok login session from the user's existing Chrome browser.

    Copies essential profile data from Chrome's Default profile into
    the skill's persistent profile directory. This allows using the
    same TikTok session without re-logging in.
    """
    chrome_default = CHROME_PROFILE_DIR / "Default"

    if not chrome_default.exists():
        print("Chrome profile not found at expected location.")
        print(f"  Expected: {chrome_default}")
        return False

    print("Importing TikTok session from Chrome...")

    # Prepare the skill's browser profile directory
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    default_dir = PROFILE_DIR / "Default"
    if default_dir.exists():
        shutil.rmtree(default_dir, ignore_errors=True)
    default_dir.mkdir(parents=True, exist_ok=True)

    # Copy essential files from Chrome profile
    essential_files = [
        "Cookies",
        "Cookies-journal",
        "Preferences",
        "Secure Preferences",
    ]
    copied = 0
    for fname in essential_files:
        src = chrome_default / fname
        if src.exists():
            shutil.copy2(src, default_dir / fname)
            copied += 1

    # Copy Local State from Chrome root
    local_state = CHROME_PROFILE_DIR / "Local State"
    if local_state.exists():
        shutil.copy2(local_state, PROFILE_DIR / "Local State")
        copied += 1

    # Copy Local Storage for session data
    local_storage = chrome_default / "Local Storage"
    if local_storage.exists():
        shutil.copytree(local_storage, default_dir / "Local Storage", dirs_exist_ok=True)
        copied += 1

    if copied == 0:
        print("No Chrome profile files found to copy.")
        return False

    print(f"Copied {copied} profile components from Chrome.")

    # Verify by launching headless and checking cookies
    print("Verifying TikTok session...")
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=True,
                viewport={"width": 1280, "height": 720},
                locale="en-US",
                channel="chrome",
                args=["--mute-audio", "--autoplay-policy=document-user-activation-required"],
            )

            page = context.new_page()
            page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            cookies = context.cookies()
            COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
            COOKIES_PATH.write_text(json.dumps(cookies, indent=2))

            session = _has_session_cookies(cookies)
            page.close()
            context.close()

            if session:
                print(f"Session cookies found: {', '.join(session)}")
                print("Chrome import successful! TikTok session is active.")
                return True

            print(f"Imported {len(cookies)} cookies but no TikTok session cookies found.")
            print("You may not be logged into TikTok in Chrome.")
            print("Try logging into TikTok in Chrome first, then re-run with --from-chrome.")
            return False
    except Exception as e:
        print(f"Verification failed: {e}")
        print("Profile was imported but could not be verified. Try running a search.")
        return True  # Profile was copied, may still work


def login_and_save_cookies(timeout_seconds: int = 180) -> bool:
    """
    Open a visible browser with a persistent profile for TikTok login.

    Automatically detects when the user has logged in by polling for
    session cookies and URL changes. No manual terminal input needed.
    The browser profile persists between runs, so login state is kept.
    """
    COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    print("Opening TikTok login page...")
    print("Please log in to your TikTok account in the browser window.")
    print("After logging in, the browser will close automatically.\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            channel="chrome",
            args=["--mute-audio", "--autoplay-policy=document-user-activation-required"],
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded", timeout=30000)

        print(f"Waiting for login... (timeout: {timeout_seconds}s)")
        start = time.time()
        logged_in = False

        while time.time() - start < timeout_seconds:
            time.sleep(3)

            cookies = context.cookies()
            found = _has_session_cookies(cookies)
            if found:
                print(f"Session cookies detected: {', '.join(found)}")
                logged_in = True
                break

            current_url = page.url
            if "/login" not in current_url and "tiktok.com" in current_url:
                print(f"Login page left, now at: {current_url}")
                logged_in = True
                break

        if not logged_in:
            cookies = context.cookies()
            found = _has_session_cookies(cookies)
            if found:
                logged_in = True
            elif "/login" not in page.url:
                logged_in = True

        if not logged_in:
            print("Timeout: login not detected. Please try again.")
            print("Tip: Use --from-chrome to import your existing Chrome session instead.")
            context.close()
            return False

        # Navigate to For You page to collect full cookies
        try:
            page.goto("https://www.tiktok.com/foryou", wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)
        except Exception:
            pass

        cookies = context.cookies()
        COOKIES_PATH.write_text(json.dumps(cookies, indent=2))
        print(f"\nCookies saved to: {COOKIES_PATH}")
        print(f"Total cookies: {len(cookies)}")

        session_cookies = _has_session_cookies(cookies)
        if session_cookies:
            print(f"Session cookies found: {', '.join(session_cookies)}")
            print("Login successful!")
            context.close()
            return True

        title = page.title()
        if "log in" not in title.lower():
            print("Browser profile appears logged in (persistent state saved).")
            context.close()
            return True

        print("Warning: No session cookies detected. Login may not have completed.")
        context.close()
        return False


def check_login_status() -> bool:
    """Check if valid TikTok cookies or persistent profile exist."""
    has_profile = PROFILE_DIR.exists() and any(PROFILE_DIR.iterdir())
    has_cookies = COOKIES_PATH.exists()

    if has_profile:
        print("Persistent browser profile found.")
        if has_cookies:
            try:
                cookies = json.loads(COOKIES_PATH.read_text())
                session = _has_session_cookies(cookies)
                if session:
                    print(f"Session cookies: {', '.join(session)}")
                    print("Status: Logged in")
                    return True
                print(f"Profile has {len(cookies)} cookies (no explicit session cookie).")
                print("Status: May be logged in. Run a search to verify.")
                return True
            except Exception:
                pass
        print("Profile exists but no cookies file. Try running a search to verify.")
        return True

    if not has_cookies:
        print("No saved cookies or browser profile found.")
        print("Run 'uv run --project runtime runtime/login.py --from-chrome' to import Chrome session.")
        return False

    return False


def login_via_system_chrome(timeout_seconds: int = 180) -> bool:
    """
    Open TikTok login in the user's actual Chrome browser, then import session.

    This opens TikTok in the user's default Chrome (with all their existing tabs,
    bookmarks, extensions etc.), waits for them to log in, then imports the cookies.
    """
    import subprocess

    print("Opening TikTok in your Chrome browser...")
    print("Please log in to TikTok in the browser window that opens.")
    print(f"Once logged in, come back here. Waiting up to {timeout_seconds}s...\n")

    # Open TikTok login in user's Chrome
    subprocess.run(["open", "-a", "Google Chrome", "https://www.tiktok.com/login"], check=False)

    # Wait for user to log in, then import from Chrome
    print("After logging in to TikTok in Chrome, press Enter here to import your session...")
    print("(Or wait - we'll auto-check periodically)")

    import select

    start = time.time()
    while time.time() - start < timeout_seconds:
        # Check if user pressed Enter (non-blocking)
        ready, _, _ = select.select([sys.stdin], [], [], 10)
        if ready:
            sys.stdin.readline()
            break
        # Auto-check every 10 seconds
        print("  Checking Chrome for TikTok session...")

    print("\nImporting session from Chrome...")
    return import_from_chrome()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="TikTok login helper")
    parser.add_argument("--check", action="store_true", help="Check login status without opening browser")
    parser.add_argument(
        "--from-chrome",
        action="store_true",
        help="Import TikTok session from your existing Chrome browser (no new browser opened)",
    )
    parser.add_argument(
        "--open-chrome",
        action="store_true",
        help="Open TikTok login in your actual Chrome browser, then import session (default)",
    )
    args = parser.parse_args()

    if args.check:
        success = check_login_status()
    elif args.from_chrome:
        success = import_from_chrome()
    elif args.open_chrome:
        success = login_via_system_chrome()
    else:
        # Default: try importing from Chrome first, fall back to interactive
        print("Trying to import existing TikTok session from Chrome...")
        success = import_from_chrome()
        if not success:
            print("\nNo existing session found. Opening Chrome for login...")
            success = login_via_system_chrome()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
