import json
import os
import tempfile
import unittest
from pathlib import Path

from bluedot_agent.settings import (
    ProviderConfigurationError,
    ProviderSettingsStore,
    WindowsDataProtector,
)


class ReversingProtector:
    def protect(self, value: bytes) -> bytes:
        return value[::-1]

    def unprotect(self, value: bytes) -> bytes:
        return value[::-1]


class ProviderSettingsStoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "settings.json"
        self.store = ProviderSettingsStore(
            path=self.path,
            protector=ReversingProtector(),
            environ={},
        )

    def test_saved_key_is_encrypted_and_never_returned_to_the_panel(self):
        public = self.store.save(
            provider="groq",
            model="openai/gpt-oss-120b",
            api_key="groq-secret",
        )

        raw = self.path.read_text(encoding="utf-8")
        self.assertNotIn("groq-secret", raw)
        self.assertNotIn("api_key", public)
        for provider in public["providers"].values():
            self.assertNotIn("api_key", provider)
            self.assertNotIn("protected_api_key", provider)
        self.assertEqual(public["selected_provider"], "groq")
        self.assertTrue(public["providers"]["groq"]["has_api_key"])

        credentials = self.store.credentials()
        self.assertEqual(credentials.provider, "groq")
        self.assertEqual(credentials.model, "openai/gpt-oss-120b")
        self.assertEqual(credentials.api_key, "groq-secret")

    def test_download_directory_defaults_to_system_folder_and_persists(self):
        default_directory = Path(self.temporary_directory.name) / "Downloads"
        selected_directory = Path(self.temporary_directory.name) / "Blue Dot"
        store = ProviderSettingsStore(
            path=self.path,
            protector=ReversingProtector(),
            environ={},
            default_download_directory=lambda: default_directory,
        )

        self.assertEqual(
            store.public_state()["download_directory"],
            str(default_directory),
        )

        public = store.save(
            provider="gemini",
            model="gemini-3.5-flash-lite",
            download_directory=str(selected_directory),
        )

        self.assertEqual(public["download_directory"], str(selected_directory))
        reloaded = ProviderSettingsStore(
            path=self.path,
            protector=ReversingProtector(),
            environ={},
            default_download_directory=lambda: default_directory,
        )
        self.assertEqual(
            reloaded.public_state()["download_directory"],
            str(selected_directory),
        )

    def test_version_one_settings_migrate_to_firefox_browser(self):
        self.path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "selected_provider": "gemini",
                    "providers": {},
                }
            ),
            encoding="utf-8",
        )

        public = self.store.public_state()

        self.assertEqual(public["browser"], "firefox")
        migrated = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(migrated["version"], 2)
        self.assertEqual(migrated["browser"], "firefox")

    def test_browser_selection_is_validated_and_persisted(self):
        public = self.store.save(
            provider="gemini",
            model="gemini-3.5-flash-lite",
            browser="chrome",
        )

        self.assertEqual(public["browser"], "chrome")
        with self.assertRaisesRegex(ProviderConfigurationError, "браузер"):
            self.store.save(
                provider="gemini",
                model="gemini-3.5-flash-lite",
                browser="safari",
            )

    def test_blank_key_preserves_saved_key_and_explicit_clear_removes_it(self):
        self.store.save(
            provider="gemini",
            model="gemini-3.5-flash-lite",
            api_key="saved-secret",
        )

        self.store.save(
            provider="gemini",
            model="gemini-3.5-flash",
            api_key="",
        )
        self.assertEqual(self.store.credentials().api_key, "saved-secret")

        public = self.store.save(
            provider="gemini",
            model="gemini-3.5-flash",
            clear_api_key=True,
        )
        self.assertFalse(public["providers"]["gemini"]["has_api_key"])
        with self.assertRaisesRegex(ProviderConfigurationError, "API"):
            self.store.credentials()

    def test_environment_key_is_used_without_being_written_to_disk(self):
        store = ProviderSettingsStore(
            path=self.path,
            protector=ReversingProtector(),
            environ={"MISTRAL_API_KEY": "environment-secret"},
        )

        store.save(provider="mistral", model="mistral-small-latest")

        self.assertEqual(store.credentials().api_key, "environment-secret")
        self.assertNotIn(
            "environment-secret",
            self.path.read_text(encoding="utf-8"),
        )
        self.assertTrue(
            store.public_state()["providers"]["mistral"]["has_api_key"]
        )

    def test_provider_and_model_are_validated(self):
        with self.assertRaisesRegex(ProviderConfigurationError, "провайдер"):
            self.store.save(provider="unknown", model="anything")
        with self.assertRaisesRegex(ProviderConfigurationError, "модел"):
            self.store.save(provider="groq", model="  ")

    def test_retired_cerebras_is_removed_and_falls_back_to_gemini(self):
        original = {
            "version": 1,
            "selected_provider": "cerebras",
            "providers": {
                "cerebras": {
                    "model": "gpt-oss-120b",
                    "protected_api_key": "encrypted-old-key",
                }
            },
        }
        self.path.write_text(
            json.dumps(original),
            encoding="utf-8",
        )

        public = self.store.public_state()

        self.assertEqual(public["selected_provider"], "gemini")
        self.assertNotIn("cerebras", public["providers"])
        migrated = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(migrated["selected_provider"], "gemini")
        self.assertEqual(migrated["providers"], {})
        self.assertNotIn("encrypted-old-key", self.path.read_text(encoding="utf-8"))

    def test_retired_openrouter_free_120b_migrates_without_losing_key(self):
        self.store.save(
            provider="openrouter",
            model="openai/gpt-oss-120b:free",
            api_key="openrouter-secret",
        )

        public = self.store.public_state()
        credentials = self.store.credentials()

        self.assertEqual(
            public["providers"]["openrouter"]["model"],
            "openai/gpt-oss-20b:free",
        )
        self.assertEqual(credentials.model, "openai/gpt-oss-20b:free")
        self.assertEqual(credentials.api_key, "openrouter-secret")

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI integration test")
    def test_real_dpapi_round_trip_survives_store_reload(self):
        first = ProviderSettingsStore(
            path=self.path,
            protector=WindowsDataProtector(),
            environ={},
        )
        first.save(
            provider="mistral",
            model="mistral-small-latest",
            api_key="real-dpapi-secret",
        )
        second = ProviderSettingsStore(
            path=self.path,
            protector=WindowsDataProtector(),
            environ={},
        )

        self.assertEqual(second.credentials().api_key, "real-dpapi-secret")
        self.assertNotIn(
            "real-dpapi-secret",
            self.path.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
