import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bluedot_agent.cli import (
    _build_parser,
    _runtime_browser,
    _run_search_command,
    _visible_sliders,
    main,
)
from bluedot_agent.intent import BlueDotIntent, GeminiUnavailableError
from bluedot_agent.models import BlueDotResult, SearchReport


class CliFallbackTest(unittest.TestCase):
    def test_missing_saved_chrome_can_switch_to_and_install_firefox(self):
        class Settings:
            def __init__(self):
                self.saved = "chrome"

            def has_saved_browser(self):
                return True

            def browser(self):
                return self.saved

            def save_browser(self, browser):
                self.saved = browser

        settings = Settings()
        with (
            patch("bluedot_agent.cli.chrome_is_available", return_value=False),
            patch("bluedot_agent.cli.choose_browser", return_value="firefox"),
            patch("bluedot_agent.cli.ensure_firefox_installed") as install,
        ):
            browser = _runtime_browser(SimpleNamespace(browser=None), settings)

        self.assertEqual(browser, "firefox")
        self.assertEqual(settings.saved, "firefox")
        install.assert_called_once_with()

    def test_panel_command_starts_panel_browser(self):
        settings = SimpleNamespace(download_directory=lambda: Path(r"D:\Downloads"))
        with (
            patch("sys.argv", ["bluedot-agent", "panel"]),
            patch("bluedot_agent.cli.BlueDotAdapter", autospec=True) as adapter_type,
            patch("bluedot_agent.cli.StartupTimer") as timer_type,
            patch("bluedot_agent.cli._runtime_settings", return_value=settings),
            patch("bluedot_agent.cli._runtime_browser", return_value="firefox"),
            patch("bluedot_agent.cli.InstanceLock"),
        ):
            main()

        timer = timer_type.return_value
        self.assertEqual(
            [call.args[0] for call in timer.mark.call_args_list],
            ["cli_ready", "adapter_ready", "process_exit"],
        )
        adapter_type.assert_called_once_with(
            headed=True,
            browser="firefox",
            download_directory=settings.download_directory(),
        )
        adapter_type.return_value.panel.assert_awaited_once_with(
            startup_timer=timer,
            settings=settings,
        )

    def test_panel_command_reports_missing_gemini_without_opening_browser(self):
        output = StringIO()
        with (
            patch("sys.argv", ["bluedot-agent", "panel"]),
            patch("bluedot_agent.cli.BlueDotAdapter", autospec=True) as adapter_type,
            patch("bluedot_agent.cli.StartupTimer") as timer_type,
            patch(
                "bluedot_agent.cli._runtime_settings",
                return_value=SimpleNamespace(
                    download_directory=lambda: Path(r"D:\Downloads")
                ),
            ),
            patch("bluedot_agent.cli._runtime_browser", return_value="firefox"),
            patch("bluedot_agent.cli.InstanceLock"),
            patch("sys.stdout", output),
        ):
            adapter_type.return_value.panel.side_effect = GeminiUnavailableError(
                "Gemini не настроен. Задайте GEMINI_API_KEY."
            )
            main()

        timer_type.return_value.mark.assert_any_call("startup_failed")
        self.assertIn("GEMINI_API_KEY", output.getvalue())
        self.assertNotIn("Playwright", output.getvalue())

    def test_panel_command_logs_unexpected_runtime_failure(self):
        output = StringIO()
        with (
            patch("sys.argv", ["bluedot-agent", "panel"]),
            patch("bluedot_agent.cli.BlueDotAdapter", autospec=True) as adapter_type,
            patch("bluedot_agent.cli.StartupTimer") as timer_type,
            patch(
                "bluedot_agent.cli._runtime_settings",
                return_value=SimpleNamespace(
                    download_directory=lambda: Path(r"D:\Downloads")
                ),
            ),
            patch("bluedot_agent.cli._runtime_browser", return_value="firefox"),
            patch("bluedot_agent.cli.InstanceLock"),
            patch("sys.stdout", output),
        ):
            adapter_type.return_value.panel.side_effect = RuntimeError(
                "browser worker stopped"
            )
            timer_type.return_value.path = Path(r"C:\log\startup.log")
            main()

        timer = timer_type.return_value
        timer.mark.assert_any_call(
            "runtime_failed",
            detail="RuntimeError: browser worker stopped",
        )
        timer.mark.assert_any_call("process_exit")
        reported = output.getvalue()
        self.assertIn("browser worker stopped", reported)
        self.assertIn("RuntimeError", reported)
        self.assertIn(r"C:\log\startup.log", reported)

    def test_panel_failure_reaches_the_user_without_a_console(self):
        with (
            patch("sys.argv", ["bluedot-agent", "panel"]),
            patch("bluedot_agent.cli.BlueDotAdapter", autospec=True) as adapter_type,
            patch("bluedot_agent.cli.StartupTimer"),
            patch(
                "bluedot_agent.cli._runtime_settings",
                return_value=SimpleNamespace(
                    download_directory=lambda: Path(r"D:\Downloads")
                ),
            ),
            patch("bluedot_agent.cli._runtime_browser", return_value="firefox"),
            patch("bluedot_agent.cli.InstanceLock"),
            patch("sys.stdout", None),
            patch("bluedot_agent.notify._show_message_box") as message_box,
        ):
            adapter_type.return_value.panel.side_effect = RuntimeError(
                "browser worker stopped"
            )
            main()

        message_box.assert_called_once()
        self.assertIn("browser worker stopped", message_box.call_args.args[1])

    def test_every_command_reaches_its_own_handler(self):
        parser = _build_parser()
        commands = parser._subparsers._group_actions[0].choices

        for name, subparser in commands.items():
            with self.subTest(command=name):
                handler = subparser.get_default("func")
                self.assertIsNotNone(handler, f"{name} не связана с обработчиком")
                self.assertTrue(handler.__name__.startswith("_command_"))

    def test_auto_search_broadens_gemini_intent(self):
        intent = BlueDotIntent(
            prompt="test",
            preset_name="gemini",
            sliders={"Mood": (3, 4)},
        )
        empty = SearchReport("test", "gemini", {"Mood": (3, 4)}, [])
        found = SearchReport(
            "test",
            "gemini",
            {"Mood": (2, 5)},
            [BlueDotResult(title="Found")],
        )
        args = SimpleNamespace(
            dry_run=False,
            debug_dom=False,
            auto=True,
            prompt="test",
            preset="auto",
            limit=10,
            keep_open=False,
            include_advanced=True,
            json=False,
        )

        with (
            patch("bluedot_agent.cli.BlueDotAdapter", autospec=True) as adapter_type,
            patch(
                "bluedot_agent.cli._runtime_settings",
                return_value=SimpleNamespace(
                    download_directory=lambda: Path(r"D:\Downloads")
                ),
            ),
            patch("bluedot_agent.cli._runtime_browser", return_value="firefox"),
            patch("bluedot_agent.cli.print_search_report") as print_search_report,
        ):
            adapter_type.return_value.search.side_effect = [empty, found]
            _run_search_command(args, None, intent)

        search = adapter_type.return_value.search
        self.assertEqual(search.await_count, 2)
        self.assertEqual(
            search.await_args_list[0].kwargs,
            {"limit": 10, "keep_open": False, "include_advanced": True},
        )
        fallback_intent = search.await_args_list[1].args[0]
        self.assertEqual(fallback_intent.preset_name, "gemini")
        self.assertEqual(fallback_intent.sliders["Mood"], (2, 5))
        self.assertEqual(
            print_search_report.call_args.args[0].fallback_used,
            "broadened_filters",
        )

    def test_visible_sliders_default_to_basic_only(self):
        sliders = {
            "Mood": (2, 5),
            "Density": (1, 3),
            "Melody": (1, 5),
            "Tension": (1, 3),
            "Rhythm": (1, 3),
        }

        self.assertEqual(
            _visible_sliders(sliders),
            {
                "Mood": (2, 5),
                "Density": (1, 3),
            },
        )

    def test_visible_sliders_can_include_advanced(self):
        sliders = {
            "Mood": (2, 5),
            "Density": (1, 3),
            "Melody": (1, 5),
            "Tension": (1, 3),
            "Rhythm": (1, 3),
        }

        self.assertEqual(_visible_sliders(sliders, include_advanced=True), sliders)


if __name__ == "__main__":
    unittest.main()
