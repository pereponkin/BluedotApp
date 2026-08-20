import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class ReleaseConfigurationTest(unittest.TestCase):
    def test_release_builds_all_requested_packages_and_self_tests_them(self):
        text = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )

        for artifact in (
            "BlueDotAgent-Setup-Windows-x64",
            "BlueDotAgent-Windows-x64.zip",
            "SHA256SUMS.txt",
        ):
            self.assertIn(artifact, text)
        self.assertIn("architecture: x64", text)
        self.assertIn("architecture: arm64", text)
        self.assertIn("BlueDotAgent-macOS-${{ matrix.architecture }}.zip", text)
        self.assertIn("--self-test','--require-frozen','--browser','firefox", text)
        self.assertIn("Expand-Archive", text)
        self.assertIn("ditto -x -k", text)
        self.assertIn("codesign --force --deep --sign -", text)
        self.assertIn("browser cache leaked into the compact package", text)
        self.assertNotIn("notary", text.casefold())
        self.assertNotIn("playwright install firefox", text)

    def test_workflows_are_valid_yaml(self):
        for name in ("ci.yml", "release.yml"):
            loaded = yaml.safe_load(
                (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            )
            self.assertIsInstance(loaded, dict)

    def test_pyinstaller_build_is_onedir_and_windowed(self):
        text = (ROOT / "BlueDotAgent.spec").read_text(encoding="utf-8")

        self.assertIn("console=False", text)
        self.assertIn("COLLECT(", text)
        self.assertNotIn("onefile", text.casefold())
        self.assertIn("without_playwright_browsers", text)
        self.assertIn('".local-browsers" not in str(part)', text)

    def test_windows_uninstaller_offers_optional_user_data_removal(self):
        text = (ROOT / "installer" / "BlueDotAgent.iss").read_text(
            encoding="utf-8"
        )

        self.assertIn("CurUninstallStepChanged", text)
        self.assertIn("UninstallSilent", text)
        self.assertIn("MB_YESNO or MB_DEFBUTTON2", text)
        self.assertIn(
            "ExpandConstant('{localappdata}\\BlueDotAgent'), True, True, True",
            text,
        )


if __name__ == "__main__":
    unittest.main()
