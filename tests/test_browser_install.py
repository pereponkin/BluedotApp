import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bluedot_agent.browser_install import (
    configure_browser_cache,
    ensure_firefox_installed,
    install_firefox,
)


class BrowserInstallTest(unittest.TestCase):
    def test_source_launch_reuses_installed_playwright_firefox(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "playwright" / "driver" / "package"
            local_browsers = package / ".local-browsers"
            local_browsers.mkdir(parents=True)
            environ = {}
            with (
                patch(
                    "bluedot_agent.browser_install.compute_driver_executable",
                    return_value=(root / "node", package / "cli.js"),
                ),
                patch(
                    "bluedot_agent.browser_install.firefox_is_installed",
                    return_value=True,
                ),
                patch("bluedot_agent.browser_install._download_firefox_dialog") as dialog,
            ):
                ensure_firefox_installed(
                    state_dir=root / "state",
                    environ=environ,
                    frozen=False,
                )

        self.assertEqual(
            environ["PLAYWRIGHT_BROWSERS_PATH"],
            str(local_browsers),
        )
        dialog.assert_not_called()

    def test_browser_cache_is_kept_in_agent_state(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory)
            environ = {}

            path = configure_browser_cache(state_dir=state_dir, environ=environ)

            self.assertEqual(path, state_dir / "browsers")
            self.assertEqual(environ["PLAYWRIGHT_BROWSERS_PATH"], str(path))

    def test_frozen_app_ignores_development_browser_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "playwright" / "driver" / "package"
            (package / ".local-browsers").mkdir(parents=True)
            environ = {}
            with (
                patch(
                    "bluedot_agent.browser_install.compute_driver_executable",
                    return_value=(root / "node", package / "cli.js"),
                ),
                patch(
                    "bluedot_agent.browser_install.firefox_is_installed",
                    return_value=True,
                ),
                patch("bluedot_agent.browser_install._download_firefox_dialog") as dialog,
            ):
                ensure_firefox_installed(
                    state_dir=root / "state",
                    environ=environ,
                    frozen=True,
                )

        self.assertEqual(
            environ["PLAYWRIGHT_BROWSERS_PATH"],
            str(root / "state" / "browsers"),
        )
        dialog.assert_not_called()

    def test_firefox_installer_uses_packaged_driver_and_agent_cache(self):
        calls = []

        def run(command, **options):
            calls.append((command, options))
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "browsers"
            with patch(
                "bluedot_agent.browser_install.compute_driver_executable",
                return_value=("node", "cli.js"),
            ):
                install_firefox(cache, run=run)

        self.assertEqual(calls[0][0], ["node", "cli.js", "install", "firefox"])
        self.assertEqual(
            calls[0][1]["env"]["PLAYWRIGHT_BROWSERS_PATH"],
            str(cache),
        )
        self.assertFalse(calls[0][1]["check"])

    def test_failed_download_is_reported(self):
        def run(command, **options):
            return subprocess.CompletedProcess(command, 1)

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch(
                    "bluedot_agent.browser_install.compute_driver_executable",
                    return_value=("node", "cli.js"),
                ),
                self.assertRaisesRegex(RuntimeError, "Firefox"),
            ):
                install_firefox(Path(directory), run=run)


if __name__ == "__main__":
    unittest.main()
