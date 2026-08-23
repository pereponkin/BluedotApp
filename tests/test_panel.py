import asyncio
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from bluedot_agent.gemini import GeminiError
from bluedot_agent.intent import (
    BlueDotIntent,
    GeminiUnavailableError,
    IntentMapper,
)
from bluedot_agent.panel import (
    PANEL_SCRIPT,
    PanelFilterSnapshot,
    PanelHandler,
    panel_init_script,
)
from bluedot_agent.settings import ProviderConfigurationError


class FakeMapper:
    def __init__(self, intent, warning=None):
        self.intent = intent
        self.last_warning = warning

    def map_prompt(self, prompt, preset_name="auto"):
        return self.intent


class Frame:
    url = "https://app.sessions.blue/browse"


class PanelScriptTest(unittest.TestCase):
    def test_script_ships_with_the_package_and_keeps_its_placeholders(self):
        source = PANEL_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("__BLUEDOT_PANEL_RUN_ID__", source)
        self.assertIn("__BLUEDOT_HELP_CONTENT__", source)
        self.assertIn("app.sessions.blue", source)

    def test_init_script_leaves_no_placeholder_behind(self):
        script = panel_init_script("run-id-42")

        self.assertNotIn("__BLUEDOT", script)
        self.assertIn("run-id-42", script)
        self.assertIn("Blue Dot Agent", script)


class PanelHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def test_search_maps_prompt_outside_event_loop(self):
        intent = BlueDotIntent(
            prompt="calm",
            preset_name="rule_based",
            sliders={},
        )

        class ThreadRecordingMapper(FakeMapper):
            thread_id = None

            def map_prompt(self, prompt, preset_name="auto"):
                self.thread_id = threading.get_ident()
                return super().map_prompt(prompt, preset_name)

        async def search(mapped_intent):
            return {
                "applied_sliders": {},
                "missing_sliders": {},
                "exact_count": 0,
                "has_related": False,
            }

        event_loop_thread = threading.get_ident()
        mapper = ThreadRecordingMapper(intent)
        handler = PanelHandler(mapper, search)

        result = await handler(
            {"frame": Frame()},
            {"type": "search", "prompt": "calm"},
        )

        self.assertTrue(result["ok"])
        self.assertNotEqual(mapper.thread_id, event_loop_thread)

    async def test_choose_download_directory_uses_native_picker(self):
        opened_at = []

        async def choose_directory(initial_directory, language):
            opened_at.append(initial_directory)
            self.assertEqual(language, "ru")
            return Path(r"E:\Music\Blue Dot")

        handler = PanelHandler(
            FakeMapper(None),
            lambda intent: None,
            directory_picker=choose_directory,
        )

        result = await handler(
            {"frame": Frame()},
            {
                "type": "choose_download_directory",
                "download_directory": r"D:\Downloads",
            },
        )

        self.assertEqual(opened_at, [Path(r"D:\Downloads")])
        self.assertEqual(
            result,
            {"ok": True, "download_directory": r"E:\Music\Blue Dot"},
        )

    async def test_open_download_command_uses_native_callback(self):
        opened = []
        handler = PanelHandler(
            FakeMapper(None),
            lambda intent: None,
            open_download=lambda: opened.append(True) or True,
        )

        result = await handler({"frame": Frame()}, {"type": "open_download"})

        self.assertEqual(result, {"ok": True})
        self.assertEqual(opened, [True])

    async def test_open_download_command_reports_native_error(self):
        def fail_to_open():
            raise OSError("no association")

        handler = PanelHandler(
            FakeMapper(None),
            lambda intent: None,
            open_download=fail_to_open,
        )

        result = await handler({"frame": Frame()}, {"type": "open_download"})

        self.assertEqual(
            result,
            {"ok": False, "error": "Не удалось открыть скачанный файл."},
        )

    async def test_saved_download_directory_is_applied_to_current_session(self):
        applied = []

        class Store:
            def save(self, **values):
                return {
                    "selected_provider": values["provider"],
                    "providers": {},
                    "download_directory": values["download_directory"],
                }

        handler = PanelHandler(
            FakeMapper(None),
            lambda intent: None,
            Store(),
            download_directory_changed=applied.append,
        )

        result = await handler(
            {"frame": Frame()},
            {
                "type": "save_settings",
                "provider": "gemini",
                "model": "gemini-3.5-flash-lite",
                "download_directory": r"E:\Music\Blue Dot",
                "clear_api_key": False,
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(applied, [Path(r"E:\Music\Blue Dot")])

    async def test_browser_choice_is_saved_for_the_next_launch(self):
        saved = []

        class Store:
            def save(self, **values):
                saved.append(values)
                return {
                    "browser": values["browser"],
                    "selected_provider": values["provider"],
                    "providers": {},
                    "download_directory": r"D:\Downloads",
                }

        handler = PanelHandler(FakeMapper(None), lambda intent: None, Store())

        result = await handler(
            {"frame": Frame()},
            {
                "type": "save_settings",
                "browser": "chrome",
                "provider": "gemini",
                "model": "gemini-3.5-flash-lite",
                "clear_api_key": False,
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(saved[0]["browser"], "chrome")

    async def test_gemini_first_mapper_rejects_startup_without_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(
                GeminiUnavailableError,
                "GEMINI_API_KEY",
            ):
                IntentMapper(gemini_required=True)

    async def test_gemini_first_panel_does_not_fall_back_after_ai_failure(self):
        class BrokenGeminiParser:
            name = "gemini"

            def parse(self, prompt):
                raise GeminiError("offline")

        search_calls = 0

        async def search(intent):
            nonlocal search_calls
            search_calls += 1
            raise AssertionError("search must not run after a Gemini failure")

        handler = PanelHandler(
            IntentMapper(
                auto_parser=BrokenGeminiParser(),
                gemini_required=True,
            ),
            search,
        )
        result = await handler(
            {"frame": Frame()},
            {"type": "search", "prompt": "средневековый вайб"},
        )

        self.assertFalse(result["ok"])
        self.assertIn("Gemini не смог интерпретировать запрос", result["error"])
        self.assertNotIn("offline", result["error"])
        self.assertEqual(search_calls, 0)

    async def test_search_returns_serializable_panel_summary(self):
        intent = BlueDotIntent(
            prompt="calm strings",
            preset_name="gemini",
            sliders={"Mood": (3, 5)},
            tags=["Peaceful"],
            instruments=["Strings"],
        )

        async def search(mapped_intent):
            self.assertIs(mapped_intent, intent)
            return {
                "applied_sliders": {"Mood": (3, 5)},
                "missing_sliders": {},
                "exact_count": 4,
                "has_related": True,
            }

        handler = PanelHandler(
            FakeMapper(intent),
            search,
        )

        result = await handler(
            {"frame": Frame()},
            {"type": "search", "prompt": " calm strings "},
        )

        self.assertEqual(
            result,
            {
                "ok": True,
                "prompt": "calm strings",
                "parser": "gemini",
                "warning": None,
                "applied_sliders": {"Mood": [3, 5]},
                "categories": {
                    "Tags": ["Peaceful"],
                    "Instruments": ["Strings"],
                },
                "missing_sliders": {},
                "exact_count": 4,
                "has_related": True,
            },
        )

    async def test_invalid_binding_requests_are_rejected_before_mapping(self):
        class ExplodingMapper:
            last_warning = None

            def map_prompt(self, prompt, preset_name="auto"):
                raise AssertionError("mapper must not be called")

        async def search(intent):
            raise AssertionError("search must not be called")

        handler = PanelHandler(ExplodingMapper(), search)
        cases = [
            (
                {"frame": type("Frame", (), {"url": "https://example.com"})()},
                {"type": "search", "prompt": "calm"},
            ),
            ({"frame": Frame()}, {"type": "open-settings", "prompt": "calm"}),
            ({"frame": Frame()}, {"type": "search", "prompt": "   "}),
            ({"frame": Frame()}, {"type": "search", "prompt": "x" * 1001}),
            ({"frame": Frame()}, ["search", "calm"]),
        ]

        for source, command in cases:
            with self.subTest(command=command):
                result = await handler(source, command)
                self.assertFalse(result["ok"])
                self.assertIn("error", result)

    async def test_parallel_search_is_rejected_without_a_second_run(self):
        intent = BlueDotIntent(
            prompt="calm",
            preset_name="rule_based",
            sliders={"Mood": (3, 5)},
        )
        started = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def search(mapped_intent):
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return {
                "applied_sliders": {"Mood": (3, 5)},
                "missing_sliders": {},
                "exact_count": 1,
                "has_related": False,
            }

        handler = PanelHandler(FakeMapper(intent), search)
        first = asyncio.create_task(
            handler({"frame": Frame()}, {"type": "search", "prompt": "calm"})
        )
        await started.wait()

        second = await handler(
            {"frame": Frame()},
            {"type": "search", "prompt": "another"},
        )
        release.set()
        first_result = await first

        self.assertTrue(first_result["ok"])
        self.assertFalse(second["ok"])
        self.assertIn("выполняется", second["error"])
        self.assertEqual(calls, 1)

    async def test_search_errors_are_safe_and_do_not_leave_handler_busy(self):
        intent = BlueDotIntent(
            prompt="calm",
            preset_name="rule_based",
            sliders={"Mood": (3, 5)},
        )
        calls = 0

        async def search(mapped_intent):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("secret-token-value")
            return {
                "applied_sliders": {"Mood": (3, 5)},
                "missing_sliders": {},
                "exact_count": 1,
                "has_related": False,
            }

        handler = PanelHandler(FakeMapper(intent), search)
        first = await handler(
            {"frame": Frame()},
            {"type": "search", "prompt": "calm"},
        )
        second = await handler(
            {"frame": Frame()},
            {"type": "search", "prompt": "calm"},
        )

        self.assertFalse(first["ok"])
        self.assertNotIn("secret-token-value", first["error"])
        self.assertTrue(second["ok"])

    async def test_settings_commands_return_public_state_and_save_selection(self):
        public_state = {
            "selected_provider": "gemini",
            "providers": {
                "gemini": {
                    "id": "gemini",
                    "label": "Google AI Studio (Gemini)",
                    "model": "gemini-3.5-flash-lite",
                    "recommended_models": ["gemini-3.5-flash-lite"],
                    "has_api_key": False,
                }
            },
        }

        class Store:
            saved = None

            def public_state(self):
                return public_state

            def save(self, **values):
                self.saved = values
                return {
                    **public_state,
                    "selected_provider": values["provider"],
                }

        store = Store()
        handler = PanelHandler(FakeMapper(None), lambda intent: None, store)

        loaded = await handler(
            {"frame": Frame()},
            {"type": "get_settings"},
        )
        saved = await handler(
            {"frame": Frame()},
            {
                "type": "save_settings",
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "clear_api_key": False,
            },
        )

        self.assertEqual(loaded, {"ok": True, "settings": public_state})
        self.assertEqual(saved["settings"]["selected_provider"], "groq")
        self.assertEqual(
            store.saved,
            {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "clear_api_key": False,
            },
        )
        self.assertNotIn(
            "api_key",
            saved["settings"]["providers"]["gemini"],
        )

    async def test_language_command_saves_and_returns_public_settings(self):
        class Store:
            def save_language(self, language):
                return {"language": language}

        handler = PanelHandler(FakeMapper(None), lambda intent: None, Store())

        result = await handler(
            {"frame": Frame()},
            {"type": "set_language", "language": "en"},
        )

        self.assertEqual(result, {"ok": True, "settings": {"language": "en"}})

    async def test_api_key_is_collected_outside_browser_command(self):
        class Store:
            saved = None

            def save(self, **values):
                self.saved = values
                return {
                    "selected_provider": values["provider"],
                    "providers": {
                        values["provider"]: {
                            "id": values["provider"],
                            "label": "Groq",
                            "model": values["model"],
                            "recommended_models": [],
                            "has_api_key": True,
                        }
                    },
                }

        prompted_for = []

        async def prompt(provider_label, language):
            prompted_for.append(provider_label)
            self.assertEqual(language, "ru")
            return "desktop-secret"

        store = Store()
        handler = PanelHandler(
            FakeMapper(None),
            lambda intent: None,
            store,
            prompt,
        )
        command = {
            "type": "set_api_key",
            "provider": "groq",
            "model": "openai/gpt-oss-120b",
        }

        result = await handler({"frame": Frame()}, command)

        self.assertTrue(result["ok"])
        self.assertEqual(prompted_for, ["Groq"])
        self.assertEqual(store.saved["api_key"], "desktop-secret")
        self.assertNotIn("api_key", command)
        self.assertNotIn("desktop-secret", repr(command))
        self.assertNotIn("desktop-secret", repr(result))

    async def test_search_history_is_replayed_by_index_without_remapping(self):
        intent = BlueDotIntent(
            prompt="calm strings",
            preset_name="gemini",
            sliders={"Mood": (3, 5)},
            tags=["Peaceful"],
        )
        snapshot = PanelFilterSnapshot(
            range_filters=[
                {
                    "filterName": "Mood",
                    "displayName": "Mood",
                    "min": 3,
                    "max": 5,
                    "characteristic": True,
                }
            ],
            selectable_filters=[{"filterName": "tags", "filterValue": "Peaceful"}],
            requested_sliders={"Mood": (3, 5)},
        )
        restored = []

        async def search(mapped_intent):
            return {
                "applied_sliders": {"Mood": (3, 5)},
                "missing_sliders": {},
                "exact_count": 4,
                "has_related": True,
                "snapshot": snapshot,
            }

        async def restore(requested_snapshot):
            restored.append(requested_snapshot)
            return {
                "applied_sliders": {"Mood": (3, 5)},
                "missing_sliders": {},
                "exact_count": 4,
                "has_related": False,
            }

        handler = PanelHandler(FakeMapper(intent), search, restore=restore)

        searched = await handler(
            {"frame": Frame()},
            {"type": "search", "prompt": "calm strings"},
        )
        self.assertEqual(searched["history_index"], 0)

        replayed = await handler({"frame": Frame()}, {"type": "restore", "index": 0})

        self.assertTrue(replayed["ok"])
        self.assertEqual(restored, [snapshot])
        self.assertEqual(replayed["result"]["prompt"], "calm strings")
        self.assertEqual(replayed["result"]["parser"], "gemini")
        self.assertEqual(replayed["result"]["categories"], {"Tags": ["Peaceful"]})
        self.assertEqual(replayed["result"]["exact_count"], 4)
        self.assertFalse(replayed["result"]["has_related"])

    async def test_baseline_history_entry_clears_every_filter(self):
        restored = []

        async def search(intent):
            raise AssertionError("search must not be called")

        async def restore(snapshot):
            restored.append(snapshot)
            return {
                "applied_sliders": {},
                "missing_sliders": {},
                "exact_count": 0,
                "has_related": False,
            }

        handler = PanelHandler(FakeMapper(None), search, restore=restore)

        result = await handler({"frame": Frame()}, {"type": "restore", "index": -1})

        self.assertEqual(result, {"ok": True, "result": None})
        self.assertEqual(restored, [PanelFilterSnapshot()])
        self.assertEqual(restored[0].filter_names(), [])

    async def test_unusable_history_entries_are_rejected(self):
        async def search(intent):
            raise AssertionError("search must not be called")

        async def restore(snapshot):
            raise AssertionError("restore must not be called")

        handler = PanelHandler(FakeMapper(None), search, restore=restore)

        for index in [0, 7, -2, "0", 1.0, True, None]:
            with self.subTest(index=index):
                result = await handler(
                    {"frame": Frame()},
                    {"type": "restore", "index": index},
                )
                self.assertFalse(result["ok"])
                self.assertIn("error", result)

    async def test_invalid_settings_are_reported_without_searching(self):
        class Store:
            def save(self, **values):
                raise ProviderConfigurationError("Укажите модель.")

        async def search(intent):
            raise AssertionError("search must not run")

        handler = PanelHandler(FakeMapper(None), search, Store())
        result = await handler(
            {"frame": Frame()},
            {
                "type": "save_settings",
                "provider": "groq",
                "model": "",
                "clear_api_key": False,
            },
        )

        self.assertEqual(result, {"ok": False, "error": "Укажите модель."})


if __name__ == "__main__":
    unittest.main()
