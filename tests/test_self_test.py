import unittest
from pathlib import Path
from unittest.mock import patch

from bluedot_agent.self_test import run_self_test


class SelfTestTest(unittest.TestCase):
    def test_source_self_test_checks_resources_and_reports_runtime(self):
        with (
            patch(
                "bluedot_agent.self_test.browser_readiness",
                return_value=(True, "download_required"),
            ),
            patch("bluedot_agent.self_test._state_directory_writable", return_value=True),
            patch("bluedot_agent.self_test._secret_storage_available", return_value=True),
        ):
            result = run_self_test(browser="firefox")

        self.assertTrue(result["ok"])
        self.assertEqual(result["browser"], "firefox")
        self.assertTrue(result["checks"]["resources"])
        self.assertTrue(Path(result["state_directory"]).is_absolute())
        self.assertIn("frozen", result)
        self.assertEqual(result["browser_status"], "download_required")

    def test_missing_selected_browser_fails_self_test(self):
        with (
            patch(
                "bluedot_agent.self_test.browser_readiness",
                return_value=(False, "missing"),
            ),
            patch("bluedot_agent.self_test._state_directory_writable", return_value=True),
            patch("bluedot_agent.self_test._secret_storage_available", return_value=True),
        ):
            result = run_self_test(browser="chrome")

        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["browser"])

    def test_release_mode_requires_frozen_runtime(self):
        with (
            patch(
                "bluedot_agent.self_test.browser_readiness",
                return_value=(True, "download_required"),
            ),
            patch("bluedot_agent.self_test._state_directory_writable", return_value=True),
            patch("bluedot_agent.self_test._secret_storage_available", return_value=True),
        ):
            result = run_self_test(browser="firefox", require_frozen=True)

        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["frozen_runtime"])


if __name__ == "__main__":
    unittest.main()
