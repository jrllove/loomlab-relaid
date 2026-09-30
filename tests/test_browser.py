"""Loopback and optional real-Chromium checks for the browser smoke harness."""

import os
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from loomlab.browser import EXTENSION_DIR, PingHandler, browser_session, prepare_profile_dir


class FakeSocket:
    def __init__(self, request: bytes) -> None:
        self.input = BytesIO(request)
        self.output = BytesIO()

    def makefile(self, mode: str, buffering: int) -> BytesIO:
        return self.input if mode == "rb" else self.output

    def sendall(self, data: bytes) -> None:
        self.output.write(data)


class BrowserHarnessTests(unittest.TestCase):
    def test_new_profile_is_user_only(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile = Path(temp_dir) / "forge-profile"
            self.assertEqual(prepare_profile_dir(profile), profile.resolve())
            self.assertEqual(profile.stat().st_uid, os.geteuid())
            self.assertEqual(profile.stat().st_mode & 0o077, 0)

    def test_unsafe_existing_profile_is_rejected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile = Path(temp_dir) / "forge-profile"
            profile.mkdir()
            profile.chmod(0o755)
            with self.assertRaisesRegex(PermissionError, "group or other access"):
                prepare_profile_dir(profile)

    def test_profile_owned_by_another_user_is_rejected(self) -> None:
        with TemporaryDirectory() as temp_dir:
            profile = Path(temp_dir) / "forge-profile"
            profile.mkdir(mode=0o700)
            with patch("loomlab.browser.os.geteuid", return_value=os.geteuid() + 1):
                with self.assertRaisesRegex(PermissionError, "not owned by the effective user"):
                    prepare_profile_dir(profile)

    def test_ping_handler(self) -> None:
        for body, status, expected in (
            (b"PING", b"200 OK", b"PONG"),
            (b"OTHER", b"400", b""),
        ):
            with self.subTest(body=body):
                request = (
                    b"POST /ping HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: "
                    + str(len(body)).encode()
                    + b"\r\n\r\n"
                    + body
                )
                socket = FakeSocket(request)
                PingHandler(socket, ("127.0.0.1", 12345), object())
                response = socket.output.getvalue()
                self.assertIn(status, response)
                self.assertTrue(response.endswith(expected))

    def test_extension_files_exist(self) -> None:
        self.assertTrue((EXTENSION_DIR / "manifest.json").is_file())
        self.assertTrue((EXTENSION_DIR / "worker.js").is_file())
        self.assertTrue((EXTENSION_DIR / "proof.html").is_file())

    def test_headless_extension_and_profile_persistence(self) -> None:
        require_browser = os.environ.get("LOOMLAB_REQUIRE_BROWSER") == "1"
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            message = "Playwright is not installed; install the browser extra"
            if require_browser:
                self.fail(message)
            self.skipTest(message)

        with sync_playwright() as playwright:
            if not Path(playwright.chromium.executable_path).is_file():
                message = "Chromium is not installed; run python -m playwright install chromium"
                if require_browser:
                    self.fail(message)
                self.skipTest(message)

        with TemporaryDirectory() as temp_dir:
            profile = Path(temp_dir) / "forge-profile"
            with browser_session(profile) as (extension_id, context):
                page = context.new_page()
                page.goto(f"chrome-extension://{extension_id}/proof.html")
                self.assertIn("LoomLab Test Ping", page.locator("body").inner_text())
                page.evaluate("localStorage.setItem('loomlab-profile-proof', 'persisted')")

            with browser_session(profile) as (second_id, context):
                self.assertEqual(second_id, extension_id)
                page = context.new_page()
                page.goto(f"chrome-extension://{second_id}/proof.html")
                self.assertEqual(
                    page.evaluate("localStorage.getItem('loomlab-profile-proof')"), "persisted"
                )
