#!/usr/bin/env python3
"""Convert an HTML slide deck to an exact-size landscape PDF through Chrome CDP."""

import argparse
import asyncio
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def find_chrome() -> str:
    """Find Chrome or use the explicit ADANT_CHROME_PATH override."""
    candidates = [
        os.environ.get("ADANT_CHROME_PATH"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise FileNotFoundError("Google Chrome not found; set ADANT_CHROME_PATH")


def find_free_port() -> int:
    """Select an available local port instead of terminating an existing process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def generate_pdf(
    file_url: str,
    out_path: str,
    width_px: int,
    height_px: int,
    wait_seconds: float,
    cdp_port: int,
) -> None:
    """Generate a PDF via Chrome CDP with exact page dimensions."""
    import websockets

    new_tab_raw = urllib.request.urlopen(
        urllib.request.Request(
            f"http://localhost:{cdp_port}/json/new?about:blank",
            method="PUT",
        ),
        timeout=10,
    ).read()
    new_tab = json.loads(new_tab_raw)
    ws_url = new_tab["webSocketDebuggerUrl"]
    tab_id = new_tab["id"]

    try:
        async with websockets.connect(ws_url, max_size=50_000_000) as ws:
            msg_id = 1

            async def send(method: str, params: dict | None = None) -> dict:
                nonlocal msg_id
                message = {"id": msg_id, "method": method}
                if params:
                    message["params"] = params
                msg_id += 1
                await ws.send(json.dumps(message))
                while True:
                    response = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                    if response.get("id") == message["id"]:
                        if "error" in response:
                            print(f"CDP error: {response['error']}", file=sys.stderr)
                        return response

            await send("Page.enable")
            await send("Page.navigate", {"url": file_url})
            await asyncio.sleep(wait_seconds)
            result = await send(
                "Page.printToPDF",
                {
                    "landscape": True,
                    "printBackground": True,
                    "paperWidth": width_px / 96.0,
                    "paperHeight": height_px / 96.0,
                    "marginTop": 0,
                    "marginBottom": 0,
                    "marginLeft": 0,
                    "marginRight": 0,
                    "displayHeaderFooter": False,
                    "preferCSSPageSize": False,
                },
            )
            if "result" not in result:
                raise RuntimeError(f"printToPDF failed: {json.dumps(result)}")

            pdf_data = base64.b64decode(result["result"]["data"])
            Path(out_path).write_bytes(pdf_data)
            print(f"PDF saved: {out_path} ({len(pdf_data) // 1024} KB)")
    finally:
        try:
            urllib.request.urlopen(
                f"http://localhost:{cdp_port}/json/close/{tab_id}", timeout=5
            )
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert HTML slides to landscape PDF")
    parser.add_argument("input", help="Input HTML file")
    parser.add_argument("output", help="Output PDF file")
    parser.add_argument("--width", type=int, default=1280, help="Slide width in px")
    parser.add_argument("--height", type=int, default=720, help="Slide height in px")
    parser.add_argument(
        "--wait", type=float, default=5.0, help="Page-load wait in seconds"
    )
    args = parser.parse_args()

    file_url = f"file://{Path(args.input).resolve()}"
    out_path = str(Path(args.output).resolve())
    chrome_bin = find_chrome()
    cdp_port = find_free_port()
    chrome = subprocess.Popen(
        [
            chrome_bin,
            "--headless=new",
            f"--remote-debugging-port={cdp_port}",
            "--remote-allow-origins=*",
            "--disable-gpu",
            "--no-sandbox",
            "--no-first-run",
            f"--window-size={args.width},{args.height}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        for _ in range(15):
            time.sleep(1)
            try:
                urllib.request.urlopen(
                    f"http://localhost:{cdp_port}/json/version", timeout=2
                )
                break
            except Exception:
                pass
        else:
            raise RuntimeError("Chrome CDP did not become ready")

        asyncio.run(
            generate_pdf(
                file_url,
                out_path,
                args.width,
                args.height,
                args.wait,
                cdp_port,
            )
        )
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()


if __name__ == "__main__":
    main()
