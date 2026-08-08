import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bluedot_agent.browser_install import (
    configure_browser_cache,
    install_firefox,
)


class BrowserInstallTest(unittest.TestCase):
    def test_browser_cache_is_kept_in_agent_state(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory)
            environ = {}

            path = configure_browser_cache(state_dir=state_dir, environ=environ)

            self.assertEqual(path, state_dir / "browsers")
            self.assertEqual(environ["PLAYWRIGHT_BROWSERS_PATH"], str(path))

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
