import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, Mock, patch

from bluedot_agent.bluedot import BlueDotAdapter, allowed_slider_labels, slider_domain
from bluedot_agent.cli import _visible_sliders
from bluedot_agent.intent import BlueDotIntent
from bluedot_agent.models import BlueDotResult, SearchReport
from bluedot_agent.panel import PanelFilterSnapshot
from bluedot_agent.settings import ProviderSettingsStore


class FakePage:
    async def evaluate(self, script):
        return {"trackLikeTextCount": 7, "skeletonLikeCount": 0}


class FilterPage:
    def __init__(self):
        self.calls = []

    async def evaluate(self, script, payload):
        self.calls.append(payload)
        return {"ok": True, "filters": []}


class CapturePage:
    def __init__(self):
        self.script = ""

    async def evaluate(self, script, phase):
        self.script = script
        return {"phase": phase}


class ReadyPage:
    def __init__(self):
        self.load_states = []

    async def wait_for_load_state(self, state):
        self.load_states.append(state)


class PanelPage:
    def __init__(self):
        self.evaluate_calls = []
        self.route_calls = []
        self.unroute_calls = []
        self.reload_calls = 0

    async def evaluate(self, script, payload):
        self.evaluate_calls.append(payload)
        return {"ok": True, "filters": []}

    async def reload(self, **kwargs):
        self.reload_calls += 1

    async def route(self, url, handler):
        self.route_calls.append((url, handler))

    async def unroute_all(self, behavior):
        self.unroute_calls.append(behavior)


class AsyncPlaywrightManager:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class SliderVocabularyTest(unittest.TestCase):
    def test_advanced_sliders_appear_only_in_advanced_mode(self):
        self.assertEqual(
            allowed_slider_labels(),
            {"Mood", "Density", "Energy", "Gravity", "Ensemble"},
        )
        self.assertEqual(
            allowed_slider_labels(include_advanced=True),
            {
                "Mood",
                "Density",
                "Energy",
                "Gravity",
                "Ensemble",
                "Melody",
                "Tension",
                "Rhythm",
            },
        )

    def test_bpm_and_length_keep_their_own_domains(self):
        self.assertEqual(slider_domain("BPM"), (50, 200))
        self.assertEqual(slider_domain("Length"), (0, 360))
        self.assertEqual(slider_domain("Mood"), (1, 5))

    def test_cli_and_adapter_agree_on_the_visible_sliders(self):
        sliders = {name: (2, 4) for name in allowed_slider_labels(include_advanced=True)}

        self.assertEqual(
            set(_visible_sliders(sliders, include_advanced=True)),
            allowed_slider_labels(include_advanced=True),
        )
        self.assertEqual(
            set(_visible_sliders(sliders)),
            allowed_slider_labels(),
        )


class AdapterAsyncTest(unittest.IsolatedAsyncioTestCase):
    def test_requested_sliders_omit_neutral_full_scale_ranges(self):
        intent = BlueDotIntent(
            prompt="soviet march",
            preset_name="groq",
            sliders={
                "Mood": (1, 5),
                "Density": (1, 5),
                "Energy": (4, 5),
                "Gravity": (3, 5),
                "Ensemble": (1, 5),
                "Melody": (1, 5),
                "Tension": (3, 5),
                "Rhythm": (4, 5),
            },
            bpm=(100, 150),
            length=(60, 180),
        )

        self.assertEqual(
            BlueDotAdapter._requested_sliders(intent, include_advanced=True),
            {
                "Energy": (4, 5),
                "Gravity": (3, 5),
                "Tension": (3, 5),
                "Rhythm": (4, 5),
                "BPM": (100, 150),
                "Length": (60, 180),
            },
        )

    def test_requested_sliders_omit_full_bpm_and_length_ranges(self):
        intent = BlueDotIntent(
            prompt="neutral ranges",
            preset_name="groq",
            sliders={},
            bpm=(50, 200),
            length=(0, 360),
        )

        self.assertEqual(
            BlueDotAdapter._requested_sliders(intent, include_advanced=True),
            {},
        )

    async def test_panel_opens_settings_ui_without_key_or_running_search(self):
        adapter = BlueDotAdapter()
        page = type("Page", (), {"goto": AsyncMock()})()
        context = object()
        startup_timer = Mock()

        with (
            TemporaryDirectory() as directory,
            patch.dict("os.environ", {}, clear=True),
            patch("bluedot_agent.bluedot.async_playwright", return_value=AsyncPlaywrightManager()),
            patch("bluedot_agent.bluedot.install_panel", new=AsyncMock()) as install,
            patch.object(adapter, "_new_context", new=AsyncMock(return_value=context)),
            patch.object(adapter, "_first_page", new=AsyncMock(return_value=page)),
            patch.object(adapter, "_close_context", new=AsyncMock()) as close,
            patch.object(adapter, "_ensure_ready", new=AsyncMock()),
            patch.object(adapter, "_close_add_track_panel", new=AsyncMock()),
            patch.object(adapter, "_pause_all_media", new=AsyncMock()) as pause,
            patch.object(adapter, "_wait_until_closed", new=AsyncMock()),
            patch.object(adapter, "_run_panel_search", new=AsyncMock()) as search,
        ):
            await adapter.panel(
                startup_timer=startup_timer,
                settings=ProviderSettingsStore(path=Path(directory) / "settings.json"),
            )

        install.assert_awaited_once()
        page.goto.assert_awaited_once_with(adapter.url, wait_until="domcontentloaded")
        pause.assert_awaited_once_with(page)
        search.assert_not_awaited()
        close.assert_awaited_once_with(context)
        self.assertEqual(
            [call.args[0] for call in startup_timer.mark.call_args_list],
            [
                "settings_ready",
                "playwright_ready",
                "browser_ready",
                "panel_hooks_ready",
                "dom_loaded",
                "bluedot_ready",
                "startup_complete",
                "browser_context_closed",
            ],
        )

    async def test_browser_page_closes_the_context_when_the_body_raises(self):
        adapter = BlueDotAdapter()
        context = object()

        with (
            patch("bluedot_agent.bluedot.async_playwright", return_value=AsyncPlaywrightManager()),
            patch.object(adapter, "_new_context", new=AsyncMock(return_value=context)),
            patch.object(adapter, "_first_page", new=AsyncMock(return_value=object())),
            patch.object(adapter, "_close_context", new=AsyncMock()) as close,
        ):
            with self.assertRaises(RuntimeError):
                async with adapter._browser_page(open_bluedot=False):
                    raise RuntimeError("что-то пошло не так")

        close.assert_awaited_once_with(context)

    async def test_ready_waits_for_react_provider_not_search_placeholder(self):
        page = ReadyPage()

        with patch(
            "bluedot_agent.bluedot.wait_for_provider",
            new=AsyncMock(return_value={"filters": []}),
        ) as wait:
            await BlueDotAdapter()._ensure_ready(page)

        self.assertEqual(page.load_states, ["domcontentloaded"])
        wait.assert_awaited_once_with(page)

    async def test_session_broadens_rule_intent_without_switching_preset(self):
        intent = BlueDotIntent(
            prompt="test",
            preset_name="rule_based",
            sliders={"Density": (2, 3)},
        )
        mapper = type(
            "Mapper",
            (),
            {"last_warning": None, "map_prompt": lambda self, prompt, preset_name: intent},
        )()
        empty = SearchReport("test", "rule_based", {"Density": (2, 3)}, [])
        found = SearchReport(
            "test",
            "rule_based",
            {"Density": (1, 4)},
            [BlueDotResult(title="Found")],
        )
        adapter = BlueDotAdapter()

        with (
            patch.object(adapter, "_search_page", new=AsyncMock(side_effect=[empty, found])) as search,
            patch("bluedot_agent.bluedot.print_session_report"),
        ):
            report = await adapter._run_session_search(
                None,
                mapper,
                "test",
                preset_name="auto",
                limit=10,
                include_advanced=True,
                auto_fallback=True,
            )

        fallback_intent = search.call_args_list[1].args[1]
        self.assertEqual(fallback_intent.preset_name, "rule_based")
        self.assertEqual(fallback_intent.sliders["Density"], (1, 4))
        self.assertEqual(report.fallback_used, "broadened_filters")

    async def test_dom_state_returns_evaluated_value(self):
        state = await BlueDotAdapter()._read_playlist_dom_state(FakePage())
        self.assertEqual(state["trackLikeTextCount"], 7)

    async def test_playlist_filters_wait_for_single_complete_react_update(self):
        page = FilterPage()
        observed = {
            "filters": [
                {"filterName": "Mood", "filterType": "range", "min": 3, "max": 5},
                {"filterName": "BPM", "filterType": "range", "min": 80, "max": 120},
                {"filterName": "Duration", "filterType": "range", "min": 30, "max": 180},
                {
                    "filterName": "tags",
                    "filterType": "selectable",
                    "filterValue": "Mystery",
                },
                {
                    "filterName": "genres",
                    "filterType": "selectable",
                    "filterValue": "Classical",
                },
            ]
        }

        with patch(
            "bluedot_agent.bluedot.wait_for_filters",
            new=AsyncMock(return_value=observed),
        ) as wait:
            result = await BlueDotAdapter()._set_playlist_filters_via_react_context(
                page,
                [
                    {
                        "filterName": "Mood",
                        "displayName": "Mood",
                        "min": 3,
                        "max": 5,
                        "characteristic": True,
                    },
                    {
                        "filterName": "BPM",
                        "displayName": "BPM",
                        "min": 80,
                        "max": 120,
                        "characteristic": False,
                    },
                    {
                        "filterName": "Duration",
                        "displayName": "Length",
                        "min": 30,
                        "max": 180,
                        "characteristic": False,
                    },
                ],
                [
                    {"filterName": "tags", "filterValue": "Mystery"},
                    {"filterName": "genres", "filterValue": "Classical"},
                ],
            )

        self.assertEqual(len(page.calls), 1)
        self.assertEqual(len(page.calls[0]["rangeFilters"]), 3)
        self.assertEqual(len(page.calls[0]["selectableFilters"]), 2)
        wait.assert_awaited_once_with(page, observed["filters"])
        self.assertEqual(result["filters"], observed["filters"])

    def test_playlist_contract_includes_genres_in_the_single_final_request(self):
        intent = BlueDotIntent(
            prompt="classical strings",
            preset_name="rule_based",
            sliders={"Mood": (3, 5)},
            tags=["Majestic"],
            genres=["Classical"],
            instruments=["Strings"],
            keys=["C"],
        )

        self.assertEqual(
            BlueDotAdapter._playlist_filter_names(intent, intent.sliders),
            ["Mood", "tags", "genres", "instruments", "keys"],
        )
        self.assertEqual(
            BlueDotAdapter._playlist_selectable_filters(intent),
            [
                {"filterName": "tags", "filterValue": "Majestic"},
                {"filterName": "genres", "filterValue": "Classical"},
                {"filterName": "instruments", "filterValue": "Strings"},
                {"filterName": "keys", "filterValue": "C"},
            ],
        )

    async def test_state_probe_does_not_serialize_storage_or_global_values(self):
        page = CapturePage()

        await BlueDotAdapter()._capture_browser_state(page, "initial")

        self.assertNotIn("preview: preview(value)", page.script)
        self.assertNotIn("text = preview(value", page.script)

    async def test_panel_search_uses_one_fresh_gate_and_one_react_update_without_reload(self):
        page = PanelPage()
        intent = BlueDotIntent(
            prompt="mysterious",
            preset_name="rule_based",
            sliders={"Mood": (1, 3)},
            tags=["Mysterious"],
        )
        expected_filters = [
            {"filterType": "range", "filterName": "Mood", "min": 1, "max": 3},
            {
                "filterType": "selectable",
                "filterName": "tags",
                "filterValue": "Mysterious",
            },
        ]

        with (
            patch(
                "bluedot_agent.bluedot.wait_for_filters",
                new=AsyncMock(return_value={"filters": expected_filters}),
            ),
            patch(
                "bluedot_agent.bluedot.wait_for_stable_results",
                new=AsyncMock(
                    return_value={
                        "exactTracksLength": 0,
                        "suggestedTracksLength": 3,
                    }
                ),
            ),
            patch(
                "bluedot_agent.bluedot.read_slider_values",
                new=AsyncMock(return_value={"Mood": [1, 3]}),
            ),
            patch.object(
                BlueDotAdapter,
                "_close_filter_popovers",
                new=AsyncMock(),
            ),
            patch.object(
                BlueDotAdapter,
                "_close_add_track_panel",
                new=AsyncMock(),
            ),
            patch.object(
                BlueDotAdapter,
                "_pause_all_media",
                new=AsyncMock(),
            ),
        ):
            result = await BlueDotAdapter()._run_panel_search(page, intent)

        self.assertEqual(page.unroute_calls, ["ignoreErrors"])
        self.assertEqual(len(page.route_calls), 1)
        self.assertEqual(len(page.evaluate_calls), 1)
        snapshot = result.pop("snapshot")
        self.assertEqual(
            result,
            {
                "applied_sliders": {"Mood": (1, 3)},
                "missing_sliders": {},
                "exact_count": 0,
                "has_related": True,
            },
        )
        self.assertEqual(snapshot.requested_sliders, {"Mood": (1, 3)})
        self.assertEqual(snapshot.filter_names(), ["Mood", "tags"])
        self.assertEqual(
            snapshot.selectable_filters,
            [{"filterName": "tags", "filterValue": "Mysterious"}],
        )

    async def test_history_replay_reapplies_the_stored_filters_without_the_mapper(self):
        page = PanelPage()
        snapshot = PanelFilterSnapshot(
            range_filters=[
                {
                    "filterName": "Mood",
                    "displayName": "Mood",
                    "min": 1,
                    "max": 3,
                    "characteristic": True,
                }
            ],
            selectable_filters=[{"filterName": "tags", "filterValue": "Mysterious"}],
            requested_sliders={"Mood": (1, 3)},
        )
        expected_filters = [
            {"filterType": "range", "filterName": "Mood", "min": 1, "max": 3},
            {
                "filterType": "selectable",
                "filterName": "tags",
                "filterValue": "Mysterious",
            },
        ]

        with (
            patch(
                "bluedot_agent.bluedot.wait_for_filters",
                new=AsyncMock(return_value={"filters": expected_filters}),
            ),
            patch(
                "bluedot_agent.bluedot.wait_for_stable_results",
                new=AsyncMock(
                    return_value={
                        "exactTracksLength": 7,
                        "suggestedTracksLength": 0,
                    }
                ),
            ),
            patch(
                "bluedot_agent.bluedot.read_slider_values",
                new=AsyncMock(return_value={"Mood": [1, 3]}),
            ),
            patch.object(BlueDotAdapter, "_close_filter_popovers", new=AsyncMock()),
            patch.object(BlueDotAdapter, "_close_add_track_panel", new=AsyncMock()),
            patch.object(BlueDotAdapter, "_pause_all_media", new=AsyncMock()),
        ):
            result = await BlueDotAdapter()._apply_panel_snapshot(page, snapshot)

        self.assertEqual(page.unroute_calls, ["ignoreErrors"])
        self.assertEqual(len(page.route_calls), 1)
        self.assertEqual(len(page.evaluate_calls), 1)
        self.assertEqual(page.reload_calls, 0)
        self.assertEqual(page.evaluate_calls[0]["rangeFilters"], snapshot.range_filters)
        self.assertEqual(
            page.evaluate_calls[0]["selectableFilters"],
            snapshot.selectable_filters,
        )
        self.assertEqual(
            result,
            {
                "applied_sliders": {"Mood": (1, 3)},
                "missing_sliders": {},
                "exact_count": 7,
                "has_related": False,
            },
        )

    async def test_unfinished_downloads_are_reported_before_the_browser_closes(self):
        adapter = BlueDotAdapter()
        adapter.download_manager.errors.append("Timed out waiting for 1 download(s)")
        closed = []

        class Context:
            async def close(self):
                closed.append(True)

        with (
            patch.object(adapter.download_manager, "drain", new=AsyncMock()),
            patch("bluedot_agent.bluedot.report_failure") as report,
        ):
            await adapter._close_context(Context())

        report.assert_called_once()
        self.assertIn(
            "Timed out waiting for 1 download(s)",
            report.call_args.args[0],
        )
        self.assertEqual(adapter.download_manager.errors, [])
        self.assertEqual(closed, [True])

    async def test_clean_shutdown_reports_nothing(self):
        adapter = BlueDotAdapter()
        closed = []

        class Context:
            async def close(self):
                closed.append(True)

        with (
            patch.object(adapter.download_manager, "drain", new=AsyncMock()),
            patch("bluedot_agent.bluedot.report_failure") as report,
        ):
            await adapter._close_context(Context())

        report.assert_not_called()
        self.assertEqual(closed, [True])


if __name__ == "__main__":
    unittest.main()
