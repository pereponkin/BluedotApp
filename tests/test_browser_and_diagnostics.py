import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from bluedot_agent.browser import launch_context, prepare_profile_dir, profile_dir_for
from bluedot_agent.bluedot import BlueDotAdapter
from bluedot_agent.diagnostics import PendingTasks, redact, redact_payload_text, write_json_log


class BrowserAndDiagnosticsTest(unittest.TestCase):
    def test_firefox_keeps_existing_profile_and_chrome_is_separate(self):
        state_dir = Path(r"C:\State\BlueDotAgent")

        self.assertEqual(
            profile_dir_for("firefox", state_dir=state_dir),
            state_dir / "profile",
        )
        self.assertEqual(
            profile_dir_for("chrome", state_dir=state_dir),
            state_dir / "profile-chrome",
        )

    def test_adapter_uses_browser_specific_profile(self):
        state_dir = Path(r"C:\State\BlueDotAgent")

        adapter = BlueDotAdapter(browser="chrome", state_dir=state_dir)

        self.assertEqual(adapter.browser, "chrome")
        self.assertEqual(adapter.profile_dir, state_dir / "profile-chrome")

    def test_profile_migration_keeps_auth_and_excludes_cache_and_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "legacy"
            target = root / "state" / "profile"
            (legacy / "cache2").mkdir(parents=True)
            (legacy / "cookies.sqlite").write_text("auth")
            (legacy / "cache2" / "cache.bin").write_text("large")
            (legacy / "parent.lock").write_text("stale")
            self.assertTrue(prepare_profile_dir(target, legacy))
            self.assertEqual((target / "cookies.sqlite").read_text(), "auth")
            self.assertFalse((target / "cache2").exists())
            self.assertFalse((target / "parent.lock").exists())

    def test_redaction_hides_secrets_but_keeps_musical_key(self):
        result = redact(
            {
                "authorization": "Bearer secret",
                "url": "https://example.test/path?token=secret",
                "key": "C minor",
                "nested": {"access_token": "secret"},
            }
        )
        self.assertEqual(result["authorization"], "[REDACTED]")
        self.assertEqual(result["url"], "https://example.test/path")
        self.assertEqual(result["key"], "C minor")
        self.assertEqual(result["nested"]["access_token"], "[REDACTED]")

    def test_redaction_strips_queries_from_urls_in_lists(self):
        result = redact(
            {"resources": ["https://example.test/script.js?token=secret", "plain text"]}
        )

        self.assertEqual(result["resources"][0], "https://example.test/script.js")
        self.assertEqual(result["resources"][1], "plain text")

    def test_log_retention_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            log_dir = Path(directory)
            for index in range(4):
                write_json_log("probe", {"token": str(index)}, log_dir=log_dir, keep=2)
            paths = list(log_dir.glob("probe_*.json"))
            self.assertEqual(len(paths), 2)
            self.assertNotIn("3", json.loads(paths[0].read_text())["token"])

    def test_embedded_json_payload_is_redacted(self):
        value = redact_payload_text('{"access_token":"secret","key":"F Major"}')
        self.assertNotIn("secret", value)
        self.assertIn("F Major", value)


class PendingTasksTest(unittest.IsolatedAsyncioTestCase):
    async def test_headed_browser_uses_native_resizable_viewport(self):
        captured = {}

        class Firefox:
            async def launch_persistent_context(self, **options):
                captured.update(options)
                return object()

        playwright = type("Playwright", (), {"firefox": Firefox()})()
        with tempfile.TemporaryDirectory() as directory:
            await launch_context(
                playwright,
                Path(directory) / "profile",
                headed=True,
            )

        self.assertTrue(captured["no_viewport"])
        self.assertNotIn("viewport", captured)

    async def test_chrome_uses_the_installed_stable_channel(self):
        captured = {}

        class Chromium:
            async def launch_persistent_context(self, **options):
                captured.update(options)
                return object()

        playwright = type("Playwright", (), {"chromium": Chromium()})()
        with tempfile.TemporaryDirectory() as directory:
            await launch_context(
                playwright,
                Path(directory) / "profile",
                headed=True,
                browser="chrome",
            )

        self.assertEqual(captured["channel"], "chrome")
        self.assertNotIn("firefox_user_prefs", captured)

    async def test_chrome_profile_does_not_import_legacy_firefox_data(self):
        class Chromium:
            async def launch_persistent_context(self, **options):
                return object()

        playwright = type("Playwright", (), {"chromium": Chromium()})()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "legacy-firefox"
            profile = root / "profile-chrome"
            legacy.mkdir()
            (legacy / "cookies.sqlite").write_text("firefox auth")

            await launch_context(
                playwright,
                profile,
                headed=True,
                browser="chrome",
                legacy_profile_dir=legacy,
            )

            self.assertFalse((profile / "cookies.sqlite").exists())

    async def test_drain_waits_for_scheduled_diagnostic_work(self):
        events = []
        pending = PendingTasks()

        async def record_later():
            await asyncio.sleep(0.01)
            events.append("recorded")

        pending.create(record_later())
        await pending.drain()

        self.assertEqual(events, ["recorded"])


if __name__ == "__main__":
    unittest.main()
