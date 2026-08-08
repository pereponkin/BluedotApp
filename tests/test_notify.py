import unittest
from io import StringIO
from unittest.mock import patch

from bluedot_agent.notify import APP_TITLE, _show_message_box, report_failure


class ReportFailureTest(unittest.TestCase):
    def test_lines_go_to_the_console_when_one_exists(self):
        output = StringIO()
        with (
            patch("sys.stdout", output),
            patch("bluedot_agent.notify._show_message_box") as message_box,
        ):
            report_failure(["Что-то сломалось.", "Деталь: RuntimeError"])

        self.assertEqual(
            output.getvalue().splitlines(),
            ["Что-то сломалось.", "Деталь: RuntimeError"],
        )
        message_box.assert_not_called()

    def test_window_replaces_the_console_when_the_launcher_hides_it(self):
        with (
            patch("sys.stdout", None),
            patch("bluedot_agent.notify._show_message_box") as message_box,
        ):
            report_failure(["Что-то сломалось.", "Деталь: RuntimeError"])

        message_box.assert_called_once_with(
            APP_TITLE,
            "Что-то сломалось.\nДеталь: RuntimeError",
        )

    def test_message_box_is_skipped_outside_windows(self):
        with patch("sys.platform", "linux"):
            self.assertIsNone(_show_message_box("title", "text"))

    def test_macos_failure_uses_system_dialog(self):
        with (
            patch("sys.platform", "darwin"),
            patch("bluedot_agent.notify.subprocess.run") as run,
        ):
            _show_message_box("Blue Dot Agent", "Ошибка")

        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][0], "/usr/bin/osascript")


if __name__ == "__main__":
    unittest.main()
