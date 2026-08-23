import threading
import unittest
from unittest.mock import patch

from bluedot_agent import secret_prompt


class SecretPromptTest(unittest.TestCase):
    def test_dialog_itself_is_raised_and_entry_receives_forced_focus(self):
        calls = []

        class Dialog:
            def attributes(self, name, value):
                calls.append(("attributes", name, value))

            def lift(self):
                calls.append(("lift",))

            def focus_force(self):
                calls.append(("dialog_focus",))

        class Entry:
            def focus_force(self):
                calls.append(("entry_focus",))

        secret_prompt._activate_dialog(Dialog(), Entry())

        self.assertEqual(
            calls,
            [
                ("attributes", "-topmost", True),
                ("lift",),
                ("dialog_focus",),
                ("entry_focus",),
            ],
        )

    def test_ctrl_physical_v_pastes_with_russian_keysym(self):
        generated = []

        class Entry:
            def event_generate(self, event):
                generated.append(event)

        event = type(
            "Event",
            (),
            {"keycode": 86, "keysym": "Cyrillic_em"},
        )()

        result = secret_prompt._paste_control_v(event, Entry())

        self.assertEqual(result, "break")
        self.assertEqual(generated, ["<<Paste>>"])

    def test_other_control_key_is_not_intercepted(self):
        class Entry:
            def event_generate(self, event):
                raise AssertionError("paste must not be generated")

        event = type("Event", (), {"keycode": 67, "keysym": "Cyrillic_es"})()

        self.assertIsNone(secret_prompt._paste_control_v(event, Entry()))

    def test_cmd_physical_v_pastes_on_macos(self):
        generated = []

        class Entry:
            def event_generate(self, event):
                generated.append(event)

        event = type("Event", (), {"keycode": 9, "keysym": "Cyrillic_em"})()

        self.assertEqual(secret_prompt._paste_command_v(event, Entry()), "break")
        self.assertEqual(generated, ["<<Paste>>"])


class PromptThreadingTest(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_creates_tk_dialog_on_calling_thread(self):
        calling_thread = threading.get_ident()
        dialog_threads = []

        def fake_dialog(provider_label, language):
            dialog_threads.append(threading.get_ident())
            self.assertEqual(language, "ru")
            return "secret"

        with patch.object(
            secret_prompt,
            "_prompt_for_api_key_sync",
            side_effect=fake_dialog,
        ):
            result = await secret_prompt.prompt_for_api_key("Mistral")

        self.assertEqual(result, "secret")
        self.assertEqual(dialog_threads, [calling_thread])


if __name__ == "__main__":
    unittest.main()
