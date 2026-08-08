import tempfile
import unittest
from pathlib import Path, PureWindowsPath

from bluedot_agent.config import default_state_directory
from bluedot_agent.settings import MacKeychainStore, ProviderSettingsStore


class PlatformPathsTest(unittest.TestCase):
    def test_macos_state_lives_in_application_support(self):
        self.assertEqual(
            default_state_directory(
                platform="darwin",
                environ={},
                home=Path("/Users/tester"),
            ),
            Path("/Users/tester/Library/Application Support/BlueDotAgent"),
        )

    def test_windows_state_uses_local_app_data(self):
        result = default_state_directory(
                platform="win32",
                environ={"LOCALAPPDATA": r"C:\Users\Tester\AppData\Local"},
                home=Path(r"C:\Users\Tester"),
            )

        self.assertEqual(
            PureWindowsPath(str(result)),
            PureWindowsPath(r"C:\Users\Tester\AppData\Local\BlueDotAgent"),
        )


class MacKeychainStoreTest(unittest.TestCase):
    def test_keychain_backend_never_writes_the_key_to_settings(self):
        class Backend:
            def __init__(self):
                self.values = {}

            def get(self, account):
                return self.values.get(account)

            def set(self, account, value):
                self.values[account] = value

            def delete(self, account):
                self.values.pop(account, None)

        backend = Backend()
        keychain = MacKeychainStore(backend=backend)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = ProviderSettingsStore(
                path=path,
                secret_store=keychain,
                environ={},
            )
            store.save(
                provider="mistral",
                model="mistral-small-latest",
                api_key="mac-secret",
            )

            self.assertEqual(store.credentials().api_key, "mac-secret")
            self.assertNotIn("mac-secret", path.read_text(encoding="utf-8"))
            self.assertTrue(store.public_state()["providers"]["mistral"]["has_api_key"])

        self.assertEqual(backend.values["mistral"], "mac-secret")


if __name__ == "__main__":
    unittest.main()
