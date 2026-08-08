import tempfile
import unittest
from pathlib import Path

from bluedot_agent.launcher import (
    InstanceAlreadyRunning,
    InstanceLock,
    chrome_is_available,
    resolve_browser,
)


class FakeSettings:
    def __init__(self, browser=None):
        self.saved_browser = browser

    def has_saved_browser(self):
        return self.saved_browser is not None

    def browser(self):
        return self.saved_browser or "firefox"

    def save_browser(self, browser):
        self.saved_browser = browser


class BrowserResolutionTest(unittest.TestCase):
    def test_cli_then_environment_then_saved_browser_precedence(self):
        settings = FakeSettings("firefox")

        self.assertEqual(
            resolve_browser(
                cli_browser="chrome",
                environ={"BLUEDOT_BROWSER": "firefox"},
                settings=settings,
                chooser=lambda: self.fail("chooser must not run"),
            ),
            "chrome",
        )
        self.assertEqual(
            resolve_browser(
                cli_browser=None,
                environ={"BLUEDOT_BROWSER": "chrome"},
                settings=settings,
                chooser=lambda: self.fail("chooser must not run"),
            ),
            "chrome",
        )
        self.assertEqual(
            resolve_browser(
                cli_browser=None,
                environ={},
                settings=settings,
                chooser=lambda: self.fail("chooser must not run"),
            ),
            "firefox",
        )

    def test_first_launch_asks_once_and_saves_the_choice(self):
        settings = FakeSettings()
        calls = 0

        def choose():
            nonlocal calls
            calls += 1
            return "chrome"

        self.assertEqual(
            resolve_browser(
                cli_browser=None,
                environ={},
                settings=settings,
                chooser=choose,
            ),
            "chrome",
        )
        self.assertEqual(settings.saved_browser, "chrome")
        self.assertEqual(calls, 1)

    def test_chrome_detection_accepts_installed_application(self):
        self.assertTrue(
            chrome_is_available(
                platform="darwin",
                exists=lambda path: path == Path("/Applications/Google Chrome.app"),
                which=lambda name: None,
            )
        )

    def test_chrome_detection_rejects_missing_application(self):
        self.assertFalse(
            chrome_is_available(
                platform="darwin",
                exists=lambda path: False,
                which=lambda name: None,
            )
        )


class InstanceLockTest(unittest.TestCase):
    def test_second_instance_is_rejected_until_the_first_releases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent.lock"
            with InstanceLock(path):
                with self.assertRaises(InstanceAlreadyRunning):
                    with InstanceLock(path):
                        self.fail("second lock must not be acquired")
            with InstanceLock(path):
                pass


if __name__ == "__main__":
    unittest.main()
