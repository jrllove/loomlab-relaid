"""Persistent Chromium smoke harness for the LoomLab test extension."""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext


EXTENSION_DIR = Path(__file__).resolve().parent / "test_extension"
EXTENSION_NAME = "LoomLab Test Ping"


def prepare_profile_dir(profile_dir: Path) -> Path:
    """Create or validate a user-only Chromium profile directory."""

    profile_dir = profile_dir.expanduser().resolve()
    profile_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    profile_stat = profile_dir.stat()
    if profile_stat.st_uid != os.geteuid():
        raise PermissionError(f"profile directory is not owned by the effective user: {profile_dir}")
    if profile_stat.st_mode & 0o077:
        raise PermissionError(f"profile directory allows group or other access: {profile_dir}")
    return profile_dir


class PingHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "invalid Content-Length")
            return
        if length < 0 or length > 16:
            self.send_error(400, "invalid PING length")
            return
        body = self.rfile.read(length)
        if self.path != "/ping" or body != b"PING":
            self.send_error(400, "expected POST /ping with PING")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "4")
        self.end_headers()
        self.wfile.write(b"PONG")

    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def local_ping_server() -> Iterator[str]:
    """Accept one extension PING at a time on loopback and reply PONG."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), PingHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/ping"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@contextmanager
def browser_session(
    profile_dir: Path, *, headless: bool = True
) -> Iterator[tuple[str, BrowserContext]]:
    """Launch an isolated profile and yield its context after a local PING/PONG."""

    from playwright.sync_api import sync_playwright

    profile_dir = prepare_profile_dir(profile_dir)
    extension_dir = EXTENSION_DIR.resolve()

    with local_ping_server() as ping_url, sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            channel="chromium",
            headless=headless,
            args=[
                f"--disable-extensions-except={extension_dir}",
                f"--load-extension={extension_dir}",
            ],
        )
        try:
            workers = [
                worker
                for worker in context.service_workers
                if worker.url.startswith("chrome-extension://")
            ]
            worker = workers[0] if workers else context.wait_for_event(
                "serviceworker",
                predicate=lambda candidate: candidate.url.startswith("chrome-extension://"),
                timeout=10_000,
            )
            if worker.evaluate("chrome.runtime.getManifest().name") != EXTENSION_NAME:
                raise RuntimeError("unexpected extension service worker")
            if worker.evaluate("url => self.loomlabPing(url)", ping_url) != "PONG":
                raise RuntimeError("test extension did not receive local PONG")
            extension_id = urlsplit(worker.url).hostname
            if not extension_id:
                raise RuntimeError("test extension has no ID")
            yield extension_id, context
        finally:
            context.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, help="agent name for the startup report")
    parser.add_argument(
        "--profile-dir",
        required=True,
        type=Path,
        help="dedicated persistent Chromium user-data directory",
    )
    parser.add_argument(
        "--headed", action="store_true", help="show Chromium instead of headless mode"
    )
    args = parser.parse_args()

    with browser_session(args.profile_dir, headless=not args.headed) as (
        extension_id,
        _,
    ):
        print(
            f"{args.agent}: extension {extension_id} received local PONG; "
            f"profile={args.profile_dir.expanduser().resolve()}",
            flush=True,
        )
        print("Chromium is running. Press Ctrl-C to close it.", flush=True)
        try:
            Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
