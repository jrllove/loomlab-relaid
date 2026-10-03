"""Persistent Chromium harness for the LoomLab browser extension."""

from __future__ import annotations

import argparse
import json
import os
import re
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
OBSERVATION_FIELDS = frozenset(
    {
        "browser_state",
        "page_is_chatgpt",
        "authenticated",
        "conversation_ref",
        "conversation_url",
        "response_streaming",
        "reason",
    }
)
OBSERVATION_REASONS = frozenset(
    {
        "ambiguous_active_tab",
        "auth_unknown",
        "composer_unavailable",
        "conflicting_auth_signals",
        "invalid_page_url",
        "modal_open",
        "navigation_unavailable",
        "no_active_tab",
        "not_chatgpt",
        "observation_error",
        "observer_unavailable",
        "page_loading",
        "signed_out",
        "streaming_signal_ambiguous",
        "tab_url_unavailable",
        "unexpected_origin",
        "unsupported_page",
        "unstable_observation",
    }
)


def unknown_observation(reason: str) -> dict[str, object]:
    return {
        "browser_state": "browser_state_unknown",
        "page_is_chatgpt": None,
        "authenticated": None,
        "conversation_ref": None,
        "conversation_url": None,
        "response_streaming": None,
        "reason": reason,
    }


def sanitize_observation(raw: object) -> dict[str, object]:
    """Accept only the extension's small diagnostic schema before printing it."""

    invalid = unknown_observation("observer_protocol_error")
    if not isinstance(raw, dict) or set(raw) != OBSERVATION_FIELDS:
        return invalid
    state = raw["browser_state"]
    if not isinstance(state, str) or state not in {"ready", "streaming", "browser_state_unknown"}:
        return invalid
    if any(
        raw[key] is not None and type(raw[key]) is not bool
        for key in ("page_is_chatgpt", "authenticated", "response_streaming")
    ):
        return invalid
    reason = raw["reason"]
    if reason is not None and (not isinstance(reason, str) or reason not in OBSERVATION_REASONS):
        return invalid
    reference = raw["conversation_ref"]
    url = raw["conversation_url"]
    if (reference is None) != (url is None):
        return invalid
    if reference is not None:
        if not isinstance(reference, str) or not re.fullmatch(r"[A-Za-z0-9-]{8,128}", reference):
            return invalid
        if not isinstance(url, str) or len(url) > 300 or not url.startswith("https://"):
            return invalid
        try:
            parsed = urlsplit(url)
            safe_host = parsed.hostname == "chatgpt.com" and parsed.port is None
            no_credentials = parsed.username is None and parsed.password is None
        except ValueError:
            return invalid
        if (
            not safe_host
            or not no_credentials
            or parsed.query
            or parsed.fragment
            or not re.fullmatch(
                rf"/(?:g/[A-Za-z0-9-]{{8,128}}/)?c/{re.escape(reference)}",
                parsed.path,
            )
        ):
            return invalid
    if state == "ready" and (
        raw["page_is_chatgpt"] is not True
        or raw["authenticated"] is not True
        or raw["response_streaming"] is not False
        or reason is not None
    ):
        return invalid
    if state == "streaming" and (
        raw["page_is_chatgpt"] is not True
        or raw["authenticated"] is not True
        or raw["response_streaming"] is not True
        or reason is not None
    ):
        return invalid
    if state == "browser_state_unknown" and reason is None:
        return invalid
    return {key: raw[key] for key in OBSERVATION_FIELDS}


def observe_browser(context: BrowserContext) -> dict[str, object]:
    """Ask the extension to observe the active tab; never inspect page DOM here."""

    from playwright.sync_api import Error as PlaywrightError

    try:
        workers = [
            worker
            for worker in context.service_workers
            if worker.url.startswith("chrome-extension://")
        ]
        if len(workers) != 1:
            return unknown_observation("observer_unavailable")
        raw = workers[0].evaluate("() => self.loomlabObserve()")
    except PlaywrightError:
        return unknown_observation("observer_unavailable")
    return sanitize_observation(raw)


def prepare_profile_dir(profile_dir: Path, *, require_existing: bool = False) -> Path:
    """Create or validate a user-only Chromium profile directory."""

    profile_dir = profile_dir.expanduser().resolve()
    if require_existing and not profile_dir.is_dir():
        raise FileNotFoundError(f"existing profile directory not found: {profile_dir}")
    if not require_existing:
        profile_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    profile_stat = profile_dir.stat()
    if profile_stat.st_uid != os.geteuid():
        raise PermissionError(
            f"profile directory is not owned by the effective user: {profile_dir}"
        )
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
    profile_dir: Path, *, headless: bool = True, require_existing_profile: bool = False
) -> Iterator[tuple[str, BrowserContext]]:
    """Launch an isolated profile and yield its context after a local PING/PONG."""

    from playwright.sync_api import sync_playwright

    profile_dir = prepare_profile_dir(profile_dir, require_existing=require_existing_profile)
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
            worker = (
                workers[0]
                if workers
                else context.wait_for_event(
                    "serviceworker",
                    predicate=lambda candidate: candidate.url.startswith("chrome-extension://"),
                    timeout=10_000,
                )
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
    parser.add_argument(
        "--observe", action="store_true", help="print one read-only active-tab observation and exit"
    )
    parser.add_argument("--open-url", help="open a URL in a new active tab before observing")
    args = parser.parse_args()
    if args.open_url and not args.observe:
        parser.error("--open-url requires --observe")

    from playwright.sync_api import Error as PlaywrightError

    with browser_session(
        args.profile_dir,
        headless=not args.headed,
        require_existing_profile=args.observe,
    ) as (
        extension_id,
        context,
    ):
        print(
            f"{args.agent}: extension {extension_id} received local PONG; "
            f"profile={args.profile_dir.expanduser().resolve()}",
            flush=True,
        )
        if args.observe:
            if args.open_url:
                try:
                    page = context.new_page()
                    page.goto(args.open_url, wait_until="load", timeout=15_000)
                    page.bring_to_front()
                except PlaywrightError:
                    print(json.dumps(unknown_observation("navigation_unavailable")), flush=True)
                    return
            print(json.dumps(observe_browser(context), sort_keys=True), flush=True)
            return
        print("Chromium is running. Press Ctrl-C to close it.", flush=True)
        try:
            Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
