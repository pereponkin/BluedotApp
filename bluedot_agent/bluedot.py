from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Error as PlaywrightError, Page, async_playwright

from .browser import BrowserKind, launch_context, profile_dir_for
from .config import STATE_DIR, load_yaml
from .diagnostics import NetworkEvent, PendingTasks, diagnostic_path, redact, write_json_log
from .downloads import DownloadManager, default_download_directory
from .graphql import PlaylistGraphQLGate
from .intent import BlueDotIntent, broaden_intent, selectable_filters
from .models import BlueDotResult, SearchReport, needs_broader_search
from .notify import report_failure
from .panel import PanelFilterSnapshot, PanelHandler, install_panel
from .reporting import (
    print_live_results,
    print_mapper_warning,
    print_network_events,
    print_playlist_report,
    print_session_report,
)
from .react_bridge import (
    CHARACTERISTIC_SCALE,
    add_selectable_filter,
    apply_search_filters,
    read_slider_values,
    set_characteristic_range,
    wait_for_filters,
    wait_for_provider,
    wait_for_stable_results,
)


SLIDER_LABELS = (
    "Mood",
    "Density",
    "Energy",
    "Gravity",
    "Ensemble",
    "Melody",
    "Tension",
    "Rhythm",
)

BASIC_SLIDER_LABELS = ("Mood", "Density", "Energy", "Gravity", "Ensemble")
ADVANCED_SLIDER_LABELS = ("Melody", "Tension", "Rhythm")
SLIDER_FULL_RANGE = (1, 5)
BPM_FULL_RANGE = (50, 200)
LENGTH_FULL_RANGE = (0, 360)
BLUEDOT_GRAPHQL_URL = "https://api.sessions.blue/graphql"
BLUEDOT_SUGGEST_SEED = 916367
BLUEDOT_SUGGEST_QUERY = """
query ($filters: [suggestQuery], $randomSortMode: String, $from: JSON, $size: Int, $seed: Int) {
  suggest(q: $filters, randomSortMode: $randomSortMode, from: $from, size: $size, seed: $seed)
}
""".strip()


def allowed_slider_labels(include_advanced: bool = False) -> set[str]:
    """Return the slider names Blue Dot exposes in the given search mode.

    Args:
        include_advanced (bool, optional): Add Melody, Tension and Rhythm.

    Returns:
        (set)
    """
    labels = set(BASIC_SLIDER_LABELS)
    if include_advanced:
        labels.update(ADVANCED_SLIDER_LABELS)
    return labels


def slider_domain(name: str) -> tuple[int, int]:
    """Return the full range of a slider, used as its drag domain.

    Args:
        name (str): Slider label, for example "Mood", "BPM" or "Length".

    Returns:
        (tuple)
    """
    if name == "BPM":
        return BPM_FULL_RANGE
    if name == "Length":
        return LENGTH_FULL_RANGE
    return SLIDER_FULL_RANGE


class BlueDotAdapter:
    def __init__(
        self,
        headed: bool = True,
        profile_dir: Path | None = None,
        *,
        browser: BrowserKind = "firefox",
        state_dir: Path = STATE_DIR,
        download_directory: Path | None = None,
    ) -> None:
        self.headed = headed
        self.browser = browser
        if profile_dir is None and os.environ.get("BLUEDOT_PROFILE_DIR"):
            profile_dir = Path(os.environ["BLUEDOT_PROFILE_DIR"])
        self.profile_dir = profile_dir_for(
            browser,
            state_dir=state_dir,
            profile_override=profile_dir,
        )
        self.download_dir = download_directory or default_download_directory()
        self.download_manager = DownloadManager(
            self.download_dir,
            log_path=state_dir / "downloads.log",
        )
        inventory = load_yaml("provider_inventory.yaml")
        bluedot = inventory["providers"]["bluedot"]
        self.url = bluedot["url"]
        self.known_tags = set(bluedot["categorical_filters"]["Tags"])
        self.known_genres = set(bluedot["categorical_filters"]["Genres"])
        self.known_instruments = set(bluedot["categorical_filters"]["Instruments"])

    async def login(self) -> None:
        """Open Blue Dot in the agent profile so the user can sign in by hand.

        Blocks until the browser window is closed. Session cookies stay in the
        selected browser profile and serve every later command.
        """
        async with self._browser_page(open_bluedot=False) as page:
            await page.goto(self.url, wait_until="domcontentloaded")
            print("Браузер открыт. Войди в Blue Dot Sessions вручную.")
            print("Когда закончишь, закрой окно браузера или нажми Ctrl+C.")
            while True:
                try:
                    await page.wait_for_timeout(1000)
                    if page.is_closed():
                        break
                except PlaywrightError:
                    break

    async def panel(
        self,
        startup_timer: Any | None = None,
        settings: Any | None = None,
    ) -> None:
        """Open Blue Dot with the agent panel injected and keep it open.

        The panel maps a free-form prompt to Blue Dot filters and applies them
        on the page that is already open, without reloading the tab.

        Args:
            startup_timer (Any, optional): Collector for startup stage timings.
        """
        from .intent import ConfiguredIntentMapper
        from .settings import ProviderSettingsStore

        def mark(stage: str) -> None:
            if startup_timer is not None:
                startup_timer.mark(stage)

        settings = settings or ProviderSettingsStore()
        self.download_manager.set_directory(settings.download_directory())
        mapper = ConfiguredIntentMapper(settings)
        mark("settings_ready")
        async with self._browser_page(open_bluedot=False, mark=mark) as page:
            mark("browser_ready")
            handler = PanelHandler(
                mapper,
                lambda intent: self._run_panel_search(page, intent),
                settings,
                download_directory_changed=self.download_manager.set_directory,
                open_download=self.download_manager.open_last_download,
                restore=lambda snapshot: self._apply_panel_snapshot(page, snapshot),
            )
            await install_panel(page, handler)
            mark("panel_hooks_ready")
            await page.goto(self.url, wait_until="domcontentloaded")
            mark("dom_loaded")
            await self._ensure_ready(page)
            mark("bluedot_ready")
            await self._close_add_track_panel(page)
            await self._pause_all_media(page)
            mark("startup_complete")
            print("Blue Dot открыт с панелью агента. Введите запрос в панели слева.")
            await self._wait_until_closed(page, startup_timer=startup_timer)
        mark("browser_context_closed")

    async def search(
        self,
        intent: BlueDotIntent,
        limit: int = 10,
        keep_open: bool = False,
        include_advanced: bool = False,
    ) -> SearchReport:
        """Apply the intent by driving the Blue Dot UI and read the results.

        Args:
            intent (BlueDotIntent): Filters mapped from the user prompt.
            limit (int, optional): Maximum number of tracks to read.
            keep_open (bool, optional): Leave the selected browser open for listening.
            include_advanced (bool, optional): Also drive Melody, Tension and Rhythm.

        Returns:
            (SearchReport)
        """
        async with self._browser_page() as page:
            report = await self._search_page(
                page,
                intent,
                limit=limit,
                include_advanced=include_advanced,
            )
            if keep_open:
                print_live_results(report.results)
                await self._wait_until_closed(page)

        return report

    async def api_search(
        self,
        intent: BlueDotIntent,
        limit: int = 10,
        include_advanced: bool = True,
        keep_open: bool = True,
    ) -> SearchReport:
        """Search through the Blue Dot GraphQL API instead of the UI.

        Faster and steadier than dragging sliders, and the browser stays
        available for listening to what the API returned.

        Args:
            intent (BlueDotIntent): Filters mapped from the user prompt.
            limit (int, optional): Maximum number of tracks to read.
            include_advanced (bool, optional): Also send Melody, Tension and Rhythm.
            keep_open (bool, optional): Leave the selected browser open for listening.

        Returns:
            (SearchReport)
        """
        async with self._browser_page() as page:
            report = await self._api_search_page(
                page,
                intent,
                limit=limit,
                include_advanced=include_advanced,
            )
            if keep_open:
                print_session_report(report)
                await self._wait_until_closed(page)

        return report

    async def session(
        self,
        first_intent: BlueDotIntent | None = None,
        limit: int = 10,
        include_advanced: bool = False,
        auto_fallback: bool = True,
        preset_name: str = "auto",
    ) -> None:
        """Run repeated searches in one browser window until the user quits.

        Reads prompts from stdin. Besides plain requests the prompt accepts
        :playlist, :api, :probe, :quit.

        Args:
            first_intent (BlueDotIntent, optional): Request to run before the first prompt.
            limit (int, optional): Maximum number of tracks to read per search.
            include_advanced (bool, optional): Also drive Melody, Tension and Rhythm.
            auto_fallback (bool, optional): Retry with broader filters when nothing is found.
            preset_name (str, optional): Preset used for prompts typed in the session.
        """
        from .intent import IntentMapper

        mapper = IntentMapper()

        async with self._browser_page() as page:
            print("Blue Dot session открыт в одном окне браузера.")
            print("Вводи новый запрос и нажимай Enter. Команды: :playlist запрос, :api запрос, :probe 120, :quit, :q")

            if first_intent is not None:
                await self._run_session_search(
                    page,
                    mapper,
                    first_intent.prompt,
                    preset_name=preset_name,
                    limit=limit,
                    include_advanced=include_advanced,
                    auto_fallback=auto_fallback,
                )

            while True:
                try:
                    prompt = await asyncio.to_thread(input, "bluedot> ")
                except EOFError:
                    break
                prompt = self._normalize_session_prompt(prompt)
                if prompt in {":q", ":quit", "quit", "exit"}:
                    break
                if prompt.startswith(":probe"):
                    seconds = self._parse_probe_seconds(prompt)
                    events = await self._probe_network_on_page(page, seconds=seconds)
                    log_path = self._write_network_events(events)
                    print(f"Probe log: {log_path}")
                    print_network_events(events)
                    continue
                if prompt.startswith(":api"):
                    api_prompt = prompt.removeprefix(":api").strip() or "спокойный ненапряжный саундтрек под уютный нарратив"
                    intent = mapper.map_prompt(api_prompt, preset_name=preset_name)
                    print_mapper_warning(mapper)
                    report = await self._api_search_page(
                        page,
                        intent,
                        limit=limit,
                        include_advanced=True,
                    )
                    print_session_report(report)
                    continue
                if prompt.startswith(":playlist"):
                    playlist_prompt = prompt.removeprefix(":playlist").strip() or "спокойный ненапряжный саундтрек под уютный нарратив"
                    intent = mapper.map_prompt(playlist_prompt, preset_name=preset_name)
                    print_mapper_warning(mapper)
                    report = await self._materialize_playlist_page(
                        page,
                        intent,
                        include_advanced=True,
                    )
                    print_playlist_report(report)
                    continue
                if not prompt:
                    continue
                await self._run_session_search(
                    page,
                    mapper,
                    prompt,
                    preset_name=preset_name,
                    limit=limit,
                    include_advanced=include_advanced,
                    auto_fallback=auto_fallback,
                )

    async def playlist(
        self,
        intent: BlueDotIntent,
        include_advanced: bool = True,
    ) -> SearchReport:
        """Leave Blue Dot open on a playlist built by one filter request.

        Tracks are not read back: the point is a ready page for listening and
        downloading by hand.

        Args:
            intent (BlueDotIntent): Filters mapped from the user prompt.
            include_advanced (bool, optional): Also send Melody, Tension and Rhythm.

        Returns:
            (SearchReport)
        """
        async with self._browser_page(open_bluedot=False) as page:
            requested_sliders = self._requested_sliders(intent, include_advanced=include_advanced)
            gate_state = await self._install_playlist_graphql_gate(
                page,
                expected_filter_names=self._playlist_filter_names(intent, requested_sliders),
            )
            await page.goto(self.url, wait_until="domcontentloaded")
            await self._ensure_ready(page)
            await self._close_add_track_panel(page)
            await self._pause_all_media(page)
            applied_sliders, missing_sliders = await self._sync_visible_playlist_filters(
                page,
                intent,
                include_advanced=include_advanced,
                gate_state=gate_state,
                requested_sliders=requested_sliders,
            )
            await wait_for_stable_results(page)
            applied_sliders, missing_sliders = await self._read_react_slider_state(
                page, requested_sliders
            )
            await self._close_add_track_panel(page)
            await self._pause_all_media(page)
            report = SearchReport(
                prompt=intent.prompt,
                preset_name=intent.preset_name,
                applied_sliders=applied_sliders,
                missing_sliders=missing_sliders,
                results=[],
                selectable_filters=selectable_filters(intent),
            )
            print_playlist_report(report)
            await self._wait_until_closed(page)

        return report

    async def playlist_probe(
        self,
        intent: BlueDotIntent,
        include_advanced: bool = True,
        seconds: int = 20,
    ) -> Path:
        """Record how Blue Dot loads a filtered playlist, for diagnostics.

        Args:
            intent (BlueDotIntent): Filters mapped from the user prompt.
            include_advanced (bool, optional): Also send Melody, Tension and Rhythm.
            seconds (int, optional): How long to watch the page after applying filters.

        Returns:
            (Path)
        """
        async with self._browser_page(open_bluedot=False) as page:
            events: list[dict[str, Any]] = []
            requested_sliders = self._requested_sliders(intent, include_advanced=include_advanced)
            gate_state = await self._install_playlist_graphql_gate(
                page,
                expected_filter_names=self._playlist_filter_names(intent, requested_sliders),
                events=events,
            )
            page.on(
                "console",
                lambda message: events.append(
                    {
                        "kind": "console",
                        "type": message.type,
                        "text": message.text,
                    }
                ),
            )
            page.on(
                "pageerror",
                lambda error: events.append({"kind": "pageerror", "text": str(error)}),
            )
            pending_responses = PendingTasks()
            on_response = lambda response: pending_responses.create(
                self._record_playlist_probe_response(response, events)
            )
            page.on("response", on_response)
            await page.goto(self.url, wait_until="domcontentloaded")
            with suppress(PlaywrightError):
                await self._ensure_ready(page)
            await self._close_add_track_panel(page)
            await self._pause_all_media(page)
            try:
                applied_sliders, missing_sliders = await self._sync_visible_playlist_filters(
                    page,
                    intent,
                    include_advanced=include_advanced,
                    gate_state=gate_state,
                    requested_sliders=requested_sliders,
                )
                events.append(
                    {
                        "kind": "visible_filter_state",
                        "applied": applied_sliders,
                        "missing": missing_sliders,
                    }
                )
                await wait_for_stable_results(page)
                applied_sliders, missing_sliders = await self._read_react_slider_state(
                    page, requested_sliders
                )
                events.append(
                    {
                        "kind": "stable_visible_filter_state",
                        "applied": applied_sliders,
                        "missing": missing_sliders,
                    }
                )
            except Exception as error:
                events.append({"kind": "visible_filter_state_error", "text": str(error)})
            for elapsed in range(max(1, seconds)):
                await page.wait_for_timeout(1000)
                if elapsed == 0 or (elapsed + 1) % 5 == 0 or elapsed + 1 == max(1, seconds):
                    with suppress(Exception):
                        events.append(
                            {
                                "kind": "playlist_probe_tick",
                                "elapsedSeconds": elapsed + 1,
                                **await self._read_playlist_dom_state(page),
                            }
                        )
            await self._close_add_track_panel(page)
            await self._pause_all_media(page)

            dom_state = await self._read_playlist_dom_state(page)
            events.append({"kind": "dom_state", **dom_state})
            screenshot_path = self._playlist_probe_path("png")
            with suppress(PlaywrightError):
                await page.screenshot(path=str(screenshot_path), full_page=True)
            events.append({"kind": "screenshot", "path": str(screenshot_path)})
            page.remove_listener("response", on_response)
            await pending_responses.drain()
            return self._write_playlist_probe_events(events)

    async def _record_playlist_probe_response(self, response, events: list[dict[str, Any]]) -> None:
        if response.url != BLUEDOT_GRAPHQL_URL:
            return
        request = response.request
        post_data = request.post_data or ""
        if "filter(q:" not in post_data and "suggest(q:" not in post_data:
            return
        operation = "suggest" if "suggest(q:" in post_data else "filter"
        with suppress(Exception):
            text = await response.text()
            events.append(
                {
                    "kind": "graphql_response",
                    "operation": operation,
                    "status": response.status,
                    "hasErrors": '"errors"' in text[:1000],
                    "hasBuckets": '"buckets"' in text[:2000],
                    "length": len(text),
                    "bodyPreview": text[:1000],
                }
            )

    async def probe_network(self, seconds: int = 120) -> list[NetworkEvent]:
        """Record Blue Dot XHR and fetch traffic while filters change by hand.

        Args:
            seconds (int, optional): How long to watch the page.

        Returns:
            (list)
        """
        async with self._browser_page() as page:
            events = await self._probe_network_on_page(page, seconds=seconds)
            self._write_network_events(events)

        return events

    async def state_probe(
        self,
        intent: BlueDotIntent | None = None,
        include_advanced: bool = False,
        seconds: int = 0,
        via_react: bool = False,
    ) -> Path:
        """Capture the browser-side filter state of Blue Dot, for diagnostics.

        Args:
            intent (BlueDotIntent, optional): Filters to apply before capturing.
            include_advanced (bool, optional): Also inspect Melody, Tension and Rhythm.
            seconds (int, optional): How long to watch manual filter changes.
            via_react (bool, optional): Set ranges through the React context instead
                of dragging the sliders.

        Returns:
            (Path)
        """
        async with self._browser_page(open_bluedot=False) as page:
            events: list[dict[str, Any]] = []

            def record_request(request) -> None:
                if request.url != BLUEDOT_GRAPHQL_URL:
                    return
                payload = None
                with suppress(Exception):
                    payload = json.loads(request.post_data or "{}")
                events.append(
                    {
                        "kind": "graphql_request",
                        "phase": events[-1]["phase"] if events and "phase" in events[-1] else None,
                        "queryKind": self._graphql_query_kind(payload or {}),
                        "variables": (payload or {}).get("variables"),
                    }
                )

            page.on("request", record_request)

            await page.goto(self.url, wait_until="domcontentloaded")
            await self._ensure_ready(page)
            events.append(await self._capture_browser_state(page, "initial"))

            if intent is not None:
                requested_sliders = self._requested_sliders(intent, include_advanced=include_advanced)
                await self._clear_filters(page)
                await page.wait_for_timeout(1000)
                events.append(await self._capture_browser_state(page, "after_clear"))

                for name, value_range in requested_sliders.items():
                    domain = slider_domain(name)
                    if via_react and domain == SLIDER_FULL_RANGE:
                        events.append(
                            {
                                "kind": "react_apply_result",
                                "phase": f"before_{name}",
                                **await self._set_filter_via_react_context(page, name, value_range),
                            }
                        )
                    else:
                        await self._set_slider_range(page, name, value_range, domain)
                    await page.wait_for_timeout(1200)
                    events.append(await self._capture_browser_state(page, f"after_{name}"))
            else:
                print("State probe активен.")
                print("Вручную меняй фильтры Blue Dot в открытом браузере.")
                print(f"Подожди {seconds} секунд или закрой окно, чтобы записать лог состояния.")
                for _ in range(max(1, seconds)):
                    try:
                        await page.wait_for_timeout(1000)
                        if page.is_closed():
                            break
                    except PlaywrightError:
                        break
                if not page.is_closed():
                    events.append(await self._capture_browser_state(page, "manual_final"))

            return self._write_state_probe_events(events)

    async def _set_filter_via_react_context(
        self,
        page: Page,
        name: str,
        value_range: tuple[int, int],
    ) -> dict[str, Any]:
        return await set_characteristic_range(page, name, value_range)

    async def _probe_network_on_page(self, page: Page, seconds: int = 120) -> list[NetworkEvent]:
        events: list[NetworkEvent] = []
        pending_responses = PendingTasks()

        def record_request(request) -> None:
            if request.resource_type not in {"fetch", "xhr", "websocket"}:
                return
            post_data = request.post_data
            if post_data and len(post_data) > 1200:
                post_data = post_data[:1200] + "...<truncated>"
            events.append(
                NetworkEvent(
                    direction="request",
                    method=request.method,
                    url=request.url,
                    resource_type=request.resource_type,
                    post_data=post_data,
                )
            )

        async def record_response(response) -> None:
            request = response.request
            if request.resource_type not in {"fetch", "xhr"}:
                return
            body_preview = None
            content_type = response.headers.get("content-type", "")
            if "json" in content_type:
                with suppress(Exception):
                    text = await response.text()
                    body_preview = text[:1200]
                    if len(text) > 1200:
                        body_preview += "...<truncated>"
            events.append(
                NetworkEvent(
                    direction="response",
                    method=request.method,
                    url=response.url,
                    resource_type=request.resource_type,
                    status=response.status,
                    body_preview=body_preview,
                )
            )

        page.on("request", record_request)
        on_response = lambda response: pending_responses.create(record_response(response))
        page.on("response", on_response)

        print("Network probe активен.")
        print("Вручную меняй фильтры Blue Dot в открытом браузере.")
        print(f"Подожди {seconds} секунд или закрой окно, чтобы увидеть лог запросов.")

        for _ in range(seconds):
            try:
                await page.wait_for_timeout(1000)
                if page.is_closed():
                    break
            except PlaywrightError:
                break

        page.remove_listener("response", on_response)
        await pending_responses.drain()
        return events

    async def _run_session_search(
        self,
        page: Page,
        mapper,
        prompt: str,
        preset_name: str,
        limit: int,
        include_advanced: bool,
        auto_fallback: bool,
    ) -> SearchReport:
        intent = mapper.map_prompt(prompt, preset_name=preset_name)
        print_mapper_warning(mapper)
        report = await self._search_page(
            page,
            intent,
            limit=limit,
            include_advanced=include_advanced,
        )
        if auto_fallback and needs_broader_search(report):
            fallback_intent = broaden_intent(intent)
            report = await self._search_page(
                page,
                fallback_intent,
                limit=limit,
                include_advanced=include_advanced,
            )
            report = SearchReport(
                prompt=report.prompt,
                preset_name=report.preset_name,
                applied_sliders=report.applied_sliders,
                results=report.results,
                selectable_filters=report.selectable_filters,
                fallback_used="broadened_filters",
                missing_sliders=report.missing_sliders,
            )
        print_session_report(report)
        return report

    async def _run_panel_search(
        self,
        page: Page,
        intent: BlueDotIntent,
    ) -> dict[str, Any]:
        requested_sliders = self._requested_sliders(intent, include_advanced=True)
        snapshot = PanelFilterSnapshot(
            range_filters=self._playlist_range_filters(requested_sliders),
            selectable_filters=self._playlist_selectable_filters(intent),
            requested_sliders=requested_sliders,
        )
        state = await self._apply_panel_snapshot(page, snapshot)
        state["snapshot"] = snapshot
        return state

    async def _apply_panel_snapshot(
        self,
        page: Page,
        snapshot: PanelFilterSnapshot,
    ) -> dict[str, Any]:
        with suppress(PlaywrightError):
            await page.unroute_all(behavior="ignoreErrors")
        gate_state = await self._install_playlist_graphql_gate(
            page,
            expected_filter_names=snapshot.filter_names(),
        )
        gate_state.allow_final()
        await self._set_playlist_filters_via_react_context(
            page,
            snapshot.range_filters,
            snapshot.selectable_filters,
        )
        await self._close_filter_popovers(page)
        state = await wait_for_stable_results(page)
        applied_sliders, missing_sliders = await self._read_react_slider_state(
            page,
            snapshot.requested_sliders,
        )
        await self._close_add_track_panel(page)
        await self._pause_all_media(page)
        exact_count = state.get("exactTracksLength")
        related_count = state.get("suggestedTracksLength")
        return {
            "applied_sliders": applied_sliders,
            "missing_sliders": missing_sliders,
            "exact_count": exact_count if isinstance(exact_count, int) else 0,
            "has_related": isinstance(related_count, int) and related_count > 0,
        }

    async def _materialize_playlist_page(
        self,
        page: Page,
        intent: BlueDotIntent,
        include_advanced: bool,
    ) -> SearchReport:
        requested_sliders = self._requested_sliders(intent, include_advanced=include_advanced)
        with suppress(PlaywrightError):
            await page.unroute_all(behavior="ignoreErrors")
        gate_state = await self._install_playlist_graphql_gate(
            page,
            expected_filter_names=self._playlist_filter_names(intent, requested_sliders),
        )
        await page.reload(wait_until="domcontentloaded")
        await self._ensure_ready(page)
        applied_sliders, missing_sliders = await self._sync_visible_playlist_filters(
            page,
            intent,
            include_advanced=include_advanced,
            gate_state=gate_state,
            requested_sliders=requested_sliders,
        )
        await wait_for_stable_results(page)
        applied_sliders, missing_sliders = await self._read_react_slider_state(
            page, requested_sliders
        )

        return SearchReport(
            prompt=intent.prompt,
            preset_name=intent.preset_name,
            applied_sliders=applied_sliders,
            missing_sliders=missing_sliders,
            results=[],
            selectable_filters=selectable_filters(intent),
        )

    async def _api_search_page(
        self,
        page: Page,
        intent: BlueDotIntent,
        limit: int,
        include_advanced: bool,
    ) -> SearchReport:
        requested_sliders = self._requested_sliders(intent, include_advanced=include_advanced)
        filters = self._api_filters(intent, requested_sliders)
        payload = {
            "operationName": None,
            "variables": {
                "filters": filters,
                "randomSortMode": "avg",
                "seed": BLUEDOT_SUGGEST_SEED,
                "size": max(limit, 10),
            },
            "query": BLUEDOT_SUGGEST_QUERY,
        }
        response = await page.context.request.post(
            BLUEDOT_GRAPHQL_URL,
            data=payload,
            headers={"content-type": "application/json"},
        )
        if not response.ok:
            body = await response.text()
            raise RuntimeError(f"Blue Dot GraphQL failed: HTTP {response.status}: {body[:500]}")

        data = await response.json()
        results = self._parse_api_suggest_results(data, limit=limit)
        return SearchReport(
            prompt=intent.prompt,
            preset_name=intent.preset_name,
            applied_sliders=requested_sliders,
            results=results,
            selectable_filters=selectable_filters(intent),
        )

    async def _search_page(
        self,
        page: Page,
        intent: BlueDotIntent,
        limit: int,
        include_advanced: bool,
    ) -> SearchReport:
        await self._apply_intent(page, intent, include_advanced=include_advanced)
        requested_sliders = self._requested_sliders(intent, include_advanced=include_advanced)
        applied_sliders, missing_sliders = await self._repair_and_read_slider_state(
            page,
            requested_sliders,
        )
        await wait_for_stable_results(page)
        await self._close_filter_popovers(page)
        results = await self._extract_results(page, limit=limit)

        return SearchReport(
            prompt=intent.prompt,
            preset_name=intent.preset_name,
            applied_sliders=applied_sliders,
            missing_sliders=missing_sliders,
            results=results,
            selectable_filters=selectable_filters(intent),
        )

    async def debug_dom(self, intent: BlueDotIntent, limit: int = 20) -> list[dict[str, Any]]:
        """Return compact DOM candidates after applying the intent.

        Args:
            intent (BlueDotIntent): Filters mapped from the user prompt.
            limit (int, optional): Maximum number of DOM nodes to return.

        Returns:
            (list)
        """
        async with self._browser_page() as page:
            await self._apply_intent(page, intent, include_advanced=True)
            await wait_for_stable_results(page)
            await self._close_filter_popovers(page)
            candidates = await page.evaluate(
                """
                ({ labels, limit }) => {
                  const nodes = Array.from(document.querySelectorAll("body *"));
                  return nodes
                    .map((node) => {
                      const rect = node.getBoundingClientRect();
                      const text = (node.innerText || "").trim();
                      return {
                        tag: node.tagName,
                        className: String(node.className || ""),
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                        lineCount: text ? text.split("\\n").length : 0,
                        hasAlbum: text.includes("Album"),
                        hasPublisher: text.includes("Publisher"),
                        hasAddTrack: text.includes("Add Track"),
                        sliderHits: labels.filter((label) => text.split("\\n").map((line) => line.trim()).includes(label)),
                        sample: text.split("\\n").map((line) => line.trim()).filter(Boolean).slice(0, 16).join(" | ")
                      };
                    })
                    .filter((item) => item.width > 120 && item.height > 60 && item.lineCount > 2)
                    .filter((item) => item.hasAlbum || item.hasPublisher || item.hasAddTrack || item.sliderHits.length >= 3)
                    .sort((a, b) => a.y - b.y || a.x - b.x)
                    .slice(0, limit);
                }
                """,
                {"labels": list(SLIDER_LABELS), "limit": limit},
            )
            return candidates

    def _api_filters(
        self,
        intent: BlueDotIntent,
        requested_sliders: dict[str, tuple[int, int]],
    ) -> list[dict[str, Any]]:
        filters: list[dict[str, Any]] = []
        for name, value_range in requested_sliders.items():
            if name == "BPM":
                filter_name = "BPM"
                minimum, maximum = value_range
            elif name == "Length":
                filter_name = "Duration"
                minimum, maximum = value_range
            else:
                filter_name = name
                minimum, maximum = self._api_slider_range(value_range)
            filters.append(
                {
                    "min": minimum,
                    "max": maximum,
                    "filterType": "range",
                    "filterName": filter_name,
                }
            )

        if not intent.length and not any(item["filterName"] == "Duration" for item in filters):
            filters.append(
                {
                    "min": 0,
                    "max": 330,
                    "filterType": "range",
                    "filterName": "Duration",
                }
            )

        for tag in intent.tags:
            filters.append({"filterType": "selectable", "filterName": "tags", "filterValue": tag})
        for genre in intent.genres:
            filters.append(
                {"filterType": "selectable", "filterName": "genres", "filterValue": genre}
            )
        for instrument in intent.instruments:
            filters.append(
                {
                    "filterType": "selectable",
                    "filterName": "instruments",
                    "filterValue": instrument,
                }
            )
        for key in intent.keys:
            filters.append({"filterType": "selectable", "filterName": "keys", "filterValue": key})

        return filters

    @staticmethod
    def _playlist_probe_path(extension: str) -> Path:
        return diagnostic_path("playlist_probe", extension)

    @staticmethod
    def _write_playlist_probe_events(events: list[dict[str, Any]]) -> Path:
        return write_json_log("playlist_probe", events)

    @staticmethod
    def _write_state_probe_events(events: list[dict[str, Any]]) -> Path:
        return write_json_log("state_probe", events)

    @staticmethod
    def _graphql_query_kind(payload: dict[str, Any]) -> str:
        query = payload.get("query") or ""
        if "suggest(q:" in query:
            return "suggest"
        if "filter(q:" in query:
            return "filter"
        return "other"

    async def _capture_browser_state(self, page: Page, phase: str) -> dict[str, Any]:
        state = await page.evaluate(
            """
            async (phase) => {
              const preview = (value, limit = 700) => {
                if (value == null) return value;
                const text = typeof value === "string" ? value : (() => {
                  try { return JSON.stringify(value); } catch (_) { return String(value); }
                })();
                return text.length > limit ? text.slice(0, limit) + "...<truncated>" : text;
              };
              const tryJson = (value) => {
                try { return JSON.parse(value); } catch (_) { return null; }
              };
              const dumpStorage = (storage) => {
                const rows = [];
                for (let index = 0; index < storage.length; index += 1) {
                  const key = storage.key(index);
                  const value = storage.getItem(key);
                  const parsed = tryJson(value);
                  rows.push({
                    key,
                    length: value ? value.length : 0,
                    jsonType: parsed === null ? null : Array.isArray(parsed) ? "array" : typeof parsed,
                    jsonKeys: parsed && typeof parsed === "object" && !Array.isArray(parsed)
                      ? Object.keys(parsed).slice(0, 40)
                      : [],
                    filterHint: /filter|mood|density|energy|gravity|ensemble|melody|tension|rhythm|bpm|length|search|apollo|redux|store/i.test(
                      `${key} ${parsed && typeof parsed === "object" ? Object.keys(parsed).join(" ") : ""}`
                    )
                  });
                }
                return rows.sort((a, b) => a.key.localeCompare(b.key));
              };
              const indexedDbDatabases = await (async () => {
                try {
                  if (!indexedDB.databases) return { available: false, databases: [] };
                  return { available: true, databases: await indexedDB.databases() };
                } catch (error) {
                  return { available: true, error: String(error), databases: [] };
                }
              })();
              const globalKeys = Object.keys(window).filter((key) =>
                /apollo|redux|store|router|history|filter|search|blue|session|vue|react|ng|webpack|pinia|zustand|mobx|graphql/i.test(key)
              ).sort();
              const globalHints = globalKeys.slice(0, 120).map((key) => {
                let type = "unreadable";
                let keys = [];
                try {
                  const value = window[key];
                  type = value === null ? "null" : Array.isArray(value) ? "array" : typeof value;
                  if (value && typeof value === "object") keys = Object.keys(value).slice(0, 30);
                } catch (_) {}
                return { key, type, keys };
              });
              const framework = {
                hasReactDevtoolsHook: Boolean(window.__REACT_DEVTOOLS_GLOBAL_HOOK__),
                hasVueDevtoolsHook: Boolean(window.__VUE_DEVTOOLS_GLOBAL_HOOK__),
                hasAngular: Boolean(window.ng),
                webpackLikeKeys: Object.keys(window).filter((key) => /webpack|chunk/i.test(key)).slice(0, 40),
              };
              const nodes = Array.from(document.querySelectorAll("body *"));
              const visible = nodes.map((node) => {
                const rect = node.getBoundingClientRect();
                return {
                  node,
                  rect,
                  text: (node.innerText || node.textContent || "").trim(),
                  role: node.getAttribute("role"),
                  aria: {
                    label: node.getAttribute("aria-label"),
                    valueNow: node.getAttribute("aria-valuenow"),
                    valueMin: node.getAttribute("aria-valuemin"),
                    valueMax: node.getAttribute("aria-valuemax"),
                  }
                };
              }).filter((item) => item.rect.width > 0 && item.rect.height > 0);
              const topChips = visible
                .filter((item) => item.rect.y < 230 && item.rect.x > 240)
                .filter((item) => /Mood|Density|Energy|Gravity|Ensemble|Melody|Tension|Rhythm|BPM|Length|Tags|Keys|Instruments/.test(item.text))
                .map((item) => ({
                  text: item.text,
                  x: Math.round(item.rect.x),
                  y: Math.round(item.rect.y),
                  width: Math.round(item.rect.width),
                  height: Math.round(item.rect.height),
                }))
                .slice(0, 80);
              const leftFilterRows = visible
                .filter((item) => item.rect.x < 240 && item.rect.y > 100 && item.rect.y < window.innerHeight - 60)
                .filter((item) => /^(Mood|Density|Energy|Gravity|Ensemble|Melody|Tension|Rhythm|Instruments|Tags|Keys|BPM|Length|Adv\\. search)$/.test(item.text))
                .map((item) => ({
                  text: item.text,
                  x: Math.round(item.rect.x),
                  y: Math.round(item.rect.y),
                  width: Math.round(item.rect.width),
                  height: Math.round(item.rect.height),
                  role: item.role,
                  aria: item.aria,
                }));
              const roleSliders = visible
                .filter((item) => item.role === "slider" || item.aria.valueNow !== null)
                .map((item) => ({
                  text: item.text,
                  x: Math.round(item.rect.x),
                  y: Math.round(item.rect.y),
                  width: Math.round(item.rect.width),
                  height: Math.round(item.rect.height),
                  role: item.role,
                  aria: item.aria,
                }))
                .slice(0, 120);
              const frameworkMarkers = nodes
                .map((node) => {
                  const markers = Object.keys(node).filter((key) =>
                    /^(__react|__vue|__ng|__zone|_react|react)/i.test(key)
                  );
                  if (!markers.length) return null;
                  const rect = node.getBoundingClientRect();
                  return {
                    tag: node.tagName,
                    id: node.id || null,
                    className: typeof node.className === "string" ? node.className.slice(0, 120) : null,
                    text: (node.textContent || "").trim().slice(0, 120),
                    markers: markers.slice(0, 12),
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                  };
                })
                .filter(Boolean)
                .slice(0, 80);
              const reactProviders = (() => {
                const rootNode = document.getElementById("root");
                const roots = [];
                if (rootNode && rootNode._reactRootContainer && rootNode._reactRootContainer._internalRoot) {
                  roots.push(rootNode._reactRootContainer._internalRoot.current);
                }
                for (const node of nodes) {
                  for (const key of Object.keys(node)) {
                    if (/^__reactInternalInstance/.test(key) && node[key]) roots.push(node[key]);
                  }
                }
                const seen = new Set();
                const providers = [];
                const stack = roots.filter(Boolean);
                const looksRelevant = (value) =>
                  value && typeof value === "object" &&
                  (
                    "searchFilters" in value ||
                    "setFilters" in value ||
                    "onCharChange" in value ||
                    "fetchTracks" in value ||
                    "exactTracks" in value ||
                    "suggestedTracks" in value
                  );
                const summarizeValue = (value) => {
                  const keys = Object.keys(value).slice(0, 80);
                  const functionKeys = keys.filter((key) => typeof value[key] === "function");
                  return {
                    keys,
                    functionKeys,
                    searchFilters: Array.isArray(value.searchFilters) ? value.searchFilters : null,
                    allCharacteristics: Array.isArray(value.allCharacteristics)
                      ? value.allCharacteristics.map((item) => ({
                        filterName: item && item.filterName,
                        min: item && item.min,
                        max: item && item.max,
                        filterType: item && item.filterType
                      })).slice(0, 20)
                      : null,
                    exactTracksLength: Array.isArray(value.exactTracks) ? value.exactTracks.length : null,
                    suggestedTracksLength: Array.isArray(value.suggestedTracks) ? value.suggestedTracks.length : null,
                    allTracksLength: Array.isArray(value.allTracks) ? value.allTracks.length : null,
                  };
                };
                while (stack.length && seen.size < 30000 && providers.length < 40) {
                  const fiber = stack.pop();
                  if (!fiber || seen.has(fiber)) continue;
                  seen.add(fiber);
                  const propsList = [fiber.memoizedProps, fiber.pendingProps].filter(Boolean);
                  for (const props of propsList) {
                    if (looksRelevant(props.value)) {
                      providers.push({
                        tag: fiber.tag,
                        key: fiber.key || null,
                        typeName: fiber.type && (fiber.type.displayName || fiber.type.name) || null,
                        elementTypeName: fiber.elementType && (fiber.elementType.displayName || fiber.elementType.name) || null,
                        value: summarizeValue(props.value),
                      });
                    }
                  }
                  if (fiber.child) stack.push(fiber.child);
                  if (fiber.sibling) stack.push(fiber.sibling);
                }
                return providers;
              })();
              const scripts = Array.from(document.scripts)
                .map((script) => script.src)
                .filter(Boolean)
                .slice(0, 80);
              const resources = performance.getEntriesByType("resource")
                .map((entry) => entry.name)
                .filter((name) => /\\.js($|\\?)|graphql|api\\.sessions\\.blue|sessions\\.blue/i.test(name))
                .slice(0, 160);
              return {
                kind: "browser_state",
                phase,
                url: location.href,
                title: document.title,
                historyState: history.state,
                bodyPreview: preview(document.body.innerText || "", 1200),
                storage: {
                  localStorage: dumpStorage(localStorage),
                  sessionStorage: dumpStorage(sessionStorage),
                },
                indexedDB: indexedDbDatabases,
                globalHints,
                framework,
                dom: {
                  topChips,
                  leftFilterRows,
                  roleSliders,
                  frameworkMarkers,
                  reactProviders,
                },
                scripts,
                resources,
              };
            }
            """,
            phase,
        )
        return state

    @staticmethod
    def _api_slider_range(value_range: tuple[int, int]) -> tuple[int, int]:
        return (
            BlueDotAdapter._api_slider_value(value_range[0]),
            BlueDotAdapter._api_slider_value(value_range[1]),
        )

    @staticmethod
    def _api_slider_value(value: int) -> int:
        value = max(1, min(5, value))
        return CHARACTERISTIC_SCALE[value]

    def _parse_api_suggest_results(self, data: dict[str, Any], limit: int) -> list[BlueDotResult]:
        suggest = data.get("data", {}).get("suggest")
        if isinstance(suggest, dict):
            rows = suggest.get("buckets", []) or []
        elif isinstance(suggest, list):
            rows = suggest
        else:
            rows = []
        results: list[BlueDotResult] = []
        seen: set[str] = set()

        for row in rows:
            if not isinstance(row, dict):
                continue
            hits = row.get("top_tracks", {}).get("hits", {}).get("hits", [])
            hit = hits[0] if hits else row
            source = hit.get("_source") if isinstance(hit, dict) else None
            if not isinstance(source, dict):
                source = row if "title" in row or "name" in row else {}
            if not source:
                continue
            key = row.get("key") if isinstance(row.get("key"), dict) else {}
            unique_key = (
                key.get("parentTrackId")
                or source.get("parentTrackId")
                or source.get("id")
                or hit.get("_id")
            )
            if unique_key and unique_key in seen:
                continue
            if unique_key:
                seen.add(unique_key)
            results.append(self._parse_api_result(source))
            if len(results) >= limit:
                return results

        return results

    def _parse_api_result(self, source: dict[str, Any]) -> BlueDotResult:
        album = source.get("album")
        if isinstance(album, dict):
            album_name = album.get("name")
        elif isinstance(album, str):
            album_name = album
        else:
            album_name = None
        if album_name and self._looks_like_uuid(album_name):
            album_name = None

        stem = source.get("stem") or []
        instruments = list(source.get("instruments") or [])
        if not instruments and isinstance(stem, list):
            instruments = [
                item["instrument"]
                for item in stem
                if isinstance(item, dict) and item.get("instrument")
            ]
        instruments = list(dict.fromkeys(instruments))

        sliders = {
            name: source.get(name)
            for name in ("mood", "density", "energy", "gravity", "ensemble", "melody", "tension", "rhythm")
            if source.get(name) is not None
        }

        return BlueDotResult(
            title=source.get("title") or source.get("name") or "Untitled",
            subtitle=album_name,
            album=album_name,
            published=source.get("publishDate"),
            key=source.get("key"),
            bpm=str(source["bpm"]) if source.get("bpm") is not None else None,
            stem_files=str(len(stem)) if isinstance(stem, list) and stem else None,
            publisher=source.get("publisher"),
            sliders=sliders,
            tags=list(source.get("tags") or []),
            instruments=instruments,
            url=None,
        )

    @staticmethod
    def _looks_like_uuid(value: str) -> bool:
        return bool(
            re.fullmatch(
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                value,
            )
        )

    @asynccontextmanager
    async def _browser_page(
        self,
        *,
        open_bluedot: bool = True,
        mark: Callable[[str], None] | None = None,
    ) -> AsyncIterator[Page]:
        """Give a block one browser page and close the browser afterwards.

        Args:
            open_bluedot (bool, optional): Navigate to Blue Dot and wait for its
                React search provider before yielding. Turn off when the caller
                has to install routes or hooks before the first navigation.
            mark (Callable, optional): Startup-timing callback for the stages
                this manager owns.

        Returns:
            (AsyncIterator)
        """
        async with async_playwright() as playwright:
            if mark is not None:
                mark("playwright_ready")
            context = await self._new_context(playwright)
            try:
                page = await self._first_page(context)
                if open_bluedot:
                    await page.goto(self.url, wait_until="domcontentloaded")
                    await self._ensure_ready(page)
                yield page
            finally:
                await self._close_context(context)

    async def _new_context(self, playwright: Any) -> BrowserContext:
        context = await launch_context(
            playwright,
            self.profile_dir,
            headed=self.headed,
            browser=self.browser,
        )
        self.download_manager.attach(context)
        return context

    async def _close_context(self, context: BrowserContext) -> None:
        with suppress(asyncio.CancelledError):
            await self.download_manager.drain()
        self._report_download_errors()
        with suppress(PlaywrightError, asyncio.CancelledError):
            await context.close()

    def _report_download_errors(self) -> None:
        errors = self.download_manager.errors
        if not errors:
            return
        report_failure(["Скачивание не завершено:", *errors])
        errors.clear()

    async def _first_page(self, context: BrowserContext) -> Page:
        if context.pages:
            return context.pages[0]
        return await context.new_page()

    async def _ensure_ready(self, page: Page) -> None:
        await page.wait_for_load_state("domcontentloaded")
        await wait_for_provider(page)

    async def _read_playlist_dom_state(self, page: Page) -> dict[str, Any]:
        result = await page.evaluate(
            """
            () => {
              const nodes = Array.from(document.querySelectorAll("body *"));
              const visible = nodes
                .map((node) => {
                  const rect = node.getBoundingClientRect();
                  const text = (node.innerText || node.textContent || "").trim();
                  const style = window.getComputedStyle(node);
                  return { node, rect, text, style };
                })
                .filter((item) => item.rect.width > 0 && item.rect.height > 0 && item.style.visibility !== "hidden");
              const skeletonLike = visible.filter((item) => {
                const bg = item.style.backgroundColor || "";
                return item.text === "" && item.rect.x > 250 && item.rect.y > 220 && item.rect.width > 40 && bg !== "rgba(0, 0, 0, 0)";
              });
              const textItems = visible
                .filter((item) => item.text && !item.text.includes("\\n") && item.rect.x > 250 && item.rect.y > 220)
                .map((item) => ({ text: item.text, x: Math.round(item.rect.x), y: Math.round(item.rect.y) }))
                .slice(0, 80);
              const trackLike = textItems.filter((item) =>
                !["Filter By", "Mood", "Density", "Energy", "Gravity", "Ensemble", "Instruments", "Tags", "Keys", "Adv. search"].includes(item.text) &&
                !/^\\d+:\\d{2}$/.test(item.text)
              );
              const reactSearchState = (() => {
                const rootNode = document.getElementById("root");
                const roots = [];
                if (rootNode && rootNode._reactRootContainer && rootNode._reactRootContainer._internalRoot) {
                  roots.push(rootNode._reactRootContainer._internalRoot.current);
                }
                const seen = new Set();
                const stack = roots.filter(Boolean);
                while (stack.length && seen.size < 30000) {
                  const fiber = stack.pop();
                  if (!fiber || seen.has(fiber)) continue;
                  seen.add(fiber);
                  for (const props of [fiber.memoizedProps, fiber.pendingProps]) {
                    const value = props && props.value;
                    if (
                      value &&
                      typeof value === "object" &&
                      Array.isArray(value.searchFilters) &&
                      Array.isArray(value.allTracks)
                    ) {
                      return {
                        allTracksLength: value.allTracks.length,
                        exactTracksLength: Array.isArray(value.exactTracks) ? value.exactTracks.length : null,
                        suggestedTracksLength: Array.isArray(value.suggestedTracks) ? value.suggestedTracks.length : null,
                        loadingTracks: Boolean(value.loadingTracks),
                        loadingMore: Boolean(value.loadingMore),
                        searchFilters: value.searchFilters.map((item) => ({
                          filterName: item.filterName,
                          min: item.min,
                          max: item.max,
                          filterType: item.filterType,
                          filterValue: item.filterValue
                        })),
                        firstTracks: value.allTracks.slice(0, 8).map((item) => ({
                          title: item.title || item.name,
                          albumName: item.albumName || (item.album && item.album.name) || item.album
                        }))
                      };
                    }
                  }
                  if (fiber.child) stack.push(fiber.child);
                  if (fiber.sibling) stack.push(fiber.sibling);
                }
                return null;
              })();
              return {
                url: location.href,
                title: document.title,
                bodyTextStart: (document.body.innerText || "").slice(0, 1200),
                skeletonLikeCount: skeletonLike.length,
                textItemCount: textItems.length,
                trackLikeTextCount: trackLike.length,
                trackLikeSample: trackLike.slice(0, 30),
                reactSearchState,
              };
            }
            """
        )
        return result

    async def _close_filter_popovers(self, page: Page) -> None:
        with suppress(PlaywrightError):
            await page.keyboard.press("Escape")
        await page.wait_for_timeout(200)
        with suppress(PlaywrightError):
            await page.evaluate("() => window.getSelection()?.removeAllRanges()")
        await page.wait_for_timeout(500)

    async def _pause_all_media(self, page: Page) -> None:
        with suppress(PlaywrightError):
            await page.evaluate(
                """
                () => {
                  for (const media of document.querySelectorAll("audio, video")) {
                    try {
                      media.pause();
                      if (Number.isFinite(media.currentTime) && media.currentTime > 0) {
                        media.currentTime = 0;
                      }
                    } catch (_) {}
                  }
                }
                """
            )

    async def _close_add_track_panel(self, page: Page) -> None:
        for _ in range(2):
            closed = await page.evaluate(
                """
                () => {
                  const bodyText = document.body.innerText || "";
                  const addTrackPanelOpen =
                    bodyText.includes("Drop audio files to add reference tracks to your mix") ||
                    bodyText.includes("Supported formats:") ||
                    (bodyText.includes("Add Track") && bodyText.includes("0:00:00") && bodyText.includes("1:1"));
                  if (!addTrackPanelOpen) return null;

                  const explicitClose = Array.from(document.querySelectorAll(
                    '[aria-label*="close" i], [title*="close" i]'
                  )).find((node) => {
                    const rect = node.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                  });
                  if (!explicitClose) return false;
                  explicitClose.click();
                  return true;
                }
                """
            )
            if not closed:
                with suppress(PlaywrightError):
                    await page.keyboard.press("Escape")
                break
            await page.wait_for_timeout(500)

    async def _wait_until_closed(
        self,
        page: Page,
        *,
        startup_timer: Any | None = None,
    ) -> None:
        print("Браузер оставлен открытым. Закрой окно, когда закончишь слушать.")
        while True:
            try:
                await page.wait_for_timeout(1000)
                if page.is_closed():
                    if startup_timer is not None:
                        startup_timer.mark("browser_page_closed")
                    break
            except PlaywrightError as error:
                if startup_timer is not None:
                    detail = str(error).splitlines()[0] or type(error).__name__
                    stage = (
                        "browser_page_closed"
                        if page.is_closed()
                        else "browser_disconnected"
                    )
                    startup_timer.mark(stage, detail=detail[:500])
                break

    @staticmethod
    def _parse_probe_seconds(command: str) -> int:
        parts = command.split()
        if len(parts) < 2:
            return 120
        with suppress(ValueError):
            return max(5, min(600, int(parts[1])))
        return 120

    @staticmethod
    def _normalize_session_prompt(prompt: str) -> str:
        prompt = prompt.strip()
        while prompt.lower().startswith("bluedot>"):
            prompt = prompt.split(">", 1)[1].strip()
        return prompt

    @staticmethod
    def _write_network_events(events: list[NetworkEvent]) -> Path:
        return write_json_log("network_probe", [asdict(event) for event in events])

    async def _sync_visible_playlist_filters(
        self,
        page: Page,
        intent: BlueDotIntent,
        include_advanced: bool,
        gate_state: PlaylistGraphQLGate | None = None,
        requested_sliders: dict[str, tuple[int, int]] | None = None,
    ) -> tuple[dict[str, tuple[int, int]], dict[str, tuple[int, int]]]:
        if requested_sliders is None:
            requested_sliders = self._requested_sliders(intent, include_advanced=include_advanced)
        await self._apply_playlist_intent_via_react(page, intent, requested_sliders, gate_state=gate_state)
        return await self._read_react_slider_state(page, requested_sliders)

    async def _apply_playlist_intent_via_react(
        self,
        page: Page,
        intent: BlueDotIntent,
        requested_sliders: dict[str, tuple[int, int]],
        gate_state: PlaylistGraphQLGate | None = None,
    ) -> None:
        range_filters = self._playlist_range_filters(requested_sliders)
        selectable_filters = self._playlist_selectable_filters(intent)
        if gate_state is not None:
            gate_state.allow_final()
        await self._set_playlist_filters_via_react_context(page, range_filters, selectable_filters)
        await self._close_filter_popovers(page)

    @staticmethod
    def _playlist_range_filters(
        requested_sliders: dict[str, tuple[int, int]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "filterName": "Duration" if label == "Length" else label,
                "displayName": label,
                "min": slider_range[0],
                "max": slider_range[1],
                "characteristic": label not in {"BPM", "Length"},
            }
            for label, slider_range in requested_sliders.items()
        ]

    @staticmethod
    def _playlist_selectable_filters(intent: BlueDotIntent) -> list[dict[str, str]]:
        filters: list[dict[str, str]] = []
        filters.extend({"filterName": "tags", "filterValue": value} for value in intent.tags)
        filters.extend({"filterName": "genres", "filterValue": value} for value in intent.genres)
        filters.extend({"filterName": "instruments", "filterValue": value} for value in intent.instruments)
        filters.extend({"filterName": "keys", "filterValue": value} for value in intent.keys)
        return filters

    @staticmethod
    def _playlist_filter_names(
        intent: BlueDotIntent,
        requested_sliders: dict[str, tuple[int, int]],
    ) -> list[str]:
        names = ["Duration" if label == "Length" else label for label in requested_sliders]
        names.extend("tags" for _ in intent.tags)
        names.extend("genres" for _ in intent.genres)
        names.extend("instruments" for _ in intent.instruments)
        names.extend("keys" for _ in intent.keys)
        return names

    async def _install_playlist_graphql_gate(
        self,
        page: Page,
        expected_filter_names: list[str],
        events: list[dict[str, Any]] | None = None,
    ) -> PlaylistGraphQLGate:
        gate = PlaylistGraphQLGate(BLUEDOT_GRAPHQL_URL, expected_filter_names, events)
        return await gate.install(page)

    async def _set_playlist_filters_via_react_context(
        self,
        page: Page,
        range_filters: list[dict[str, int | str]],
        selectable_filters: list[dict[str, str]],
    ) -> dict[str, Any]:
        result = await apply_search_filters(page, range_filters, selectable_filters)
        expected_filters: list[dict[str, Any]] = [
            {
                "filterType": "range",
                "filterName": item["filterName"],
                "min": item["min"],
                "max": item["max"],
            }
            for item in range_filters
        ]
        expected_filters.extend(
            {
                "filterType": "selectable",
                "filterName": item["filterName"],
                "filterValue": item["filterValue"],
            }
            for item in selectable_filters
        )
        state = await wait_for_filters(page, expected_filters)
        result["filters"] = state["filters"]
        return result

    async def _set_selectable_via_react_context(
        self,
        page: Page,
        group: str,
        value: str,
    ) -> dict[str, Any]:
        filter_name = {
            "Tags": "tags",
            "Genres": "genres",
            "Instruments": "instruments",
            "Keys": "keys",
        }.get(group, group)
        return await add_selectable_filter(page, filter_name, value)

    async def _read_react_slider_state(
        self,
        page: Page,
        requested_sliders: dict[str, tuple[int, int]],
    ) -> tuple[dict[str, tuple[int, int]], dict[str, tuple[int, int]]]:
        react_values = await read_slider_values(page, list(requested_sliders.keys()))

        visible_values = {
            str(name): (int(value[0]), int(value[1]))
            for name, value in react_values.items()
            if isinstance(value, list) and len(value) >= 2
        }
        applied = {
            name: value_range
            for name, value_range in requested_sliders.items()
            if visible_values.get(name) == value_range
        }
        missing = {
            name: value_range
            for name, value_range in requested_sliders.items()
            if visible_values.get(name) != value_range
        }
        return applied, missing

    async def _apply_intent(
        self,
        page: Page,
        intent: BlueDotIntent,
        include_advanced: bool = False,
        retry_sliders: bool = True,
    ) -> None:
        await self._clear_filters(page)
        if include_advanced:
            await self._set_advanced_search(page, enabled=True)

        allowed_sliders = allowed_slider_labels(include_advanced)

        for label, slider_range in intent.sliders.items():
            if label not in allowed_sliders:
                continue
            if retry_sliders:
                await self._set_slider_range_with_retry(
                    page, label, slider_range, domain=SLIDER_FULL_RANGE
                )
            else:
                await self._set_slider_range(page, label, slider_range, domain=SLIDER_FULL_RANGE)

        if intent.bpm:
            if retry_sliders:
                await self._set_slider_range_with_retry(
                    page, "BPM", intent.bpm, domain=BPM_FULL_RANGE
                )
            else:
                await self._set_slider_range(page, "BPM", intent.bpm, domain=BPM_FULL_RANGE)

        if intent.length:
            if retry_sliders:
                await self._set_slider_range_with_retry(
                    page, "Length", intent.length, domain=LENGTH_FULL_RANGE
                )
            else:
                await self._set_slider_range(page, "Length", intent.length, domain=LENGTH_FULL_RANGE)

        for group, values in (
            ("Tags", intent.tags),
            ("Genres", intent.genres),
            ("Instruments", intent.instruments),
            ("Keys", intent.keys),
        ):
            if not values:
                continue
            for value in values:
                await self._set_selectable_via_react_context(page, group, value)

    async def _clear_filters(self, page: Page) -> None:
        clear = page.get_by_text("Clear all", exact=True)
        with suppress(PlaywrightError):
            if await clear.count() > 0:
                await clear.first.click(timeout=2000)
                await page.wait_for_timeout(700)

    async def _set_slider_range_with_retry(
        self,
        page: Page,
        label: str,
        value_range: tuple[int, int],
        domain: tuple[int, int],
    ) -> None:
        for attempt in range(2):
            await self._set_slider_range(page, label, value_range, domain)
            await page.wait_for_timeout(500)
            if await self._is_filter_chip_active(page, label):
                return
            if attempt == 0:
                await self._close_filter_popovers(page)

    async def _repair_and_read_slider_state(
        self,
        page: Page,
        requested_sliders: dict[str, tuple[int, int]],
        max_repair_passes: int = 2,
    ) -> tuple[dict[str, tuple[int, int]], dict[str, tuple[int, int]]]:
        for _ in range(max_repair_passes):
            visible_values = await self._visible_slider_values(page, requested_sliders.keys())
            missing = {
                name: value_range
                for name, value_range in requested_sliders.items()
                if visible_values.get(name) != value_range
            }
            if not missing:
                break
            for name, value_range in missing.items():
                await self._close_filter_popovers(page)
                await self._set_slider_range(page, name, value_range, slider_domain(name))
                await page.wait_for_timeout(450)

        visible_values = await self._visible_slider_values(page, requested_sliders.keys())
        applied = {
            name: value_range
            for name, value_range in requested_sliders.items()
            if visible_values.get(name) == value_range
        }
        missing = {
            name: value_range
            for name, value_range in requested_sliders.items()
            if visible_values.get(name) != value_range
        }
        return applied, missing

    async def _visible_slider_values(
        self,
        page: Page,
        labels,
    ) -> dict[str, tuple[int, int]]:
        values: dict[str, tuple[int, int]] = {}
        for label in labels:
            await self._open_filter_group(page, label)
            await page.wait_for_timeout(150)
            slider = await self._find_open_slider(page, str(label))
            if slider is None:
                continue
            handle_values = sorted(
                int(item["value"])
                for item in slider.get("handles", [])
                if isinstance(item.get("value"), (int, float))
            )
            if len(handle_values) >= 2:
                values[str(label)] = (handle_values[0], handle_values[-1])
        return values

    async def _active_filter_chips(self, page: Page, labels) -> set[str]:
        label_list = list(labels)
        active = await page.evaluate(
            """
            (labels) => {
              const labelSet = new Set(labels);
              return Array.from(document.querySelectorAll("body *"))
                .map((node) => ({ rect: node.getBoundingClientRect(), text: (node.textContent || "").trim() }))
                .filter((item) => labelSet.has(item.text))
                .filter((item) =>
                  item.rect.x > 240 &&
                  item.rect.y < 240 &&
                  item.rect.width > 20 &&
                  item.rect.width < 220 &&
                  item.rect.height > 10 &&
                  item.rect.height < 80
                )
                .map((item) => item.text);
            }
            """,
            label_list,
        )
        return set(active)

    async def _is_filter_chip_active(self, page: Page, label: str) -> bool:
        return label in await self._active_filter_chips(page, [label])

    @staticmethod
    def _requested_sliders(
        intent: BlueDotIntent,
        include_advanced: bool = False,
    ) -> dict[str, tuple[int, int]]:
        allowed_sliders = allowed_slider_labels(include_advanced)
        requested = {
            name: value
            for name, value in intent.sliders.items()
            if name in allowed_sliders and value != SLIDER_FULL_RANGE
        }
        if intent.bpm and intent.bpm != BPM_FULL_RANGE:
            requested["BPM"] = intent.bpm
        if intent.length and intent.length != LENGTH_FULL_RANGE:
            requested["Length"] = intent.length
        return requested

    async def _set_advanced_search(self, page: Page, enabled: bool) -> None:
        if enabled and await page.get_by_text("Rhythm", exact=True).count() > 0:
            return

        state = await page.evaluate(
            """
            () => {
              const labels = Array.from(document.querySelectorAll("body *"));
              const adv = labels.find((node) => (node.textContent || "").trim() === "Adv. search");
              if (!adv) return null;
              const rect = adv.getBoundingClientRect();
              const candidates = Array.from(document.querySelectorAll("button, [role=switch], [role=checkbox], input, div"));
              const near = candidates
                .map((node) => ({ node, rect: node.getBoundingClientRect() }))
                .filter((item) => item.rect.width > 0 && item.rect.height > 0)
                .filter((item) => Math.abs(item.rect.y - rect.y) < 30 && item.rect.x < rect.x)
                .sort((a, b) => Math.abs(a.rect.x - rect.x) - Math.abs(b.rect.x - rect.x))[0];
              if (!near) return null;
              const knob = near.rect;
              return { x: knob.x + knob.width / 2, y: knob.y + knob.height / 2 };
            }
            """
        )
        if state is None:
            return

        if enabled:
            await page.mouse.click(state["x"], state["y"])
            await page.wait_for_timeout(300)

    async def _set_slider_range(
        self,
        page: Page,
        label: str,
        value_range: tuple[int, int],
        domain: tuple[int, int],
    ) -> None:
        await self._open_filter_group(page, label)
        slider = await self._find_open_slider(page, label)
        if slider is None:
            return

        min_value, max_value = value_range
        handle_values = sorted(
            int(item["value"])
            for item in slider.get("handles", [])
            if isinstance(item.get("value"), (int, float))
        )
        if len(handle_values) >= 2 and (handle_values[0], handle_values[-1]) == (min_value, max_value):
            return

        min_domain, max_domain = domain
        width = max(slider["width"], 1)

        def x_for(value: int) -> float:
            ratio = (value - min_domain) / (max_domain - min_domain)
            ratio = max(0.0, min(1.0, ratio))
            return slider["x"] + ratio * width

        y = slider["y"] + slider["height"] / 2
        await self._drag_slider_handle(page, slider, handle="min", target_x=x_for(min_value), y=y)
        await page.wait_for_timeout(100)
        slider = await self._find_open_slider(page, label) or slider
        y = slider["y"] + slider["height"] / 2
        await self._drag_slider_handle(page, slider, handle="max", target_x=x_for(max_value), y=y)
        await page.wait_for_timeout(250)

    async def _open_filter_group(self, page: Page, label: str) -> None:
        target = await page.evaluate(
            """
            (label) => {
              const nodes = Array.from(document.querySelectorAll("button, [role=button], div, span"))
                .map((node) => ({ node, rect: node.getBoundingClientRect(), text: (node.textContent || "").trim() }))
                .filter((item) => item.text === label)
                .filter((item) => item.rect.width > 20 && item.rect.height > 10)
                .filter((item) => item.rect.x < 240)
                .sort((a, b) => a.rect.y - b.rect.y)[0];
              if (!nodes) return null;
              return { x: nodes.rect.x + nodes.rect.width / 2, y: nodes.rect.y + nodes.rect.height / 2 };
            }
            """,
            label,
        )
        if target is None:
            return

        await page.mouse.click(target["x"], target["y"])
        await page.wait_for_timeout(250)

    async def _find_open_slider(self, page: Page, label: str) -> dict[str, float] | None:
        return await page.evaluate(
            """
            (label) => {
              const nodes = Array.from(document.querySelectorAll("body *"));
              const labelNode = nodes.find((node) => (node.textContent || "").trim() === label);
              const labelRect = labelNode ? labelNode.getBoundingClientRect() : null;

              const row = Array.from(document.querySelectorAll(".selectable-container"))
                .map((node) => ({ node, rect: node.getBoundingClientRect(), text: (node.textContent || "").trim() }))
                .filter((item) => item.text === label)
                .filter((item) => item.rect.x < 260 && item.rect.width > 80 && item.rect.height > 20)
                .sort((a, b) => a.rect.y - b.rect.y)[0];
              const rowHandles = row ? Array.from(row.node.querySelectorAll('[role="slider"]'))
                .map((node) => ({ node, rect: node.getBoundingClientRect(), value: Number(node.getAttribute("aria-valuenow")) }))
                .filter((item) => item.rect.width > 8 && item.rect.height > 8 && Number.isFinite(item.value))
                .sort((a, b) => a.value - b.value || a.rect.x - b.rect.x) : [];
              const basicRangeLabels = new Set(["Mood", "Density", "Energy", "Gravity", "Ensemble", "Melody", "Tension", "Rhythm"]);
              const rowVisualHandles = row && rowHandles.length < 2 && basicRangeLabels.has(label)
                ? Array.from(row.node.querySelectorAll("*"))
                  .map((node) => ({ node, rect: node.getBoundingClientRect(), style: window.getComputedStyle(node) }))
                  .filter((item) => item.rect.width >= 8 && item.rect.width <= 32)
                  .filter((item) => item.rect.height >= 8 && item.rect.height <= 32)
                  .filter((item) => item.rect.x >= row.rect.x - 4 && item.rect.x <= row.rect.x + row.rect.width + 4)
                  .filter((item) => Math.abs((item.rect.y + item.rect.height / 2) - (row.rect.y + row.rect.height / 2)) < 16)
                  .filter((item) => {
                    const bg = item.style.backgroundColor || "";
                    const radius = item.style.borderRadius || "";
                    return bg !== "rgba(0, 0, 0, 0)" || radius !== "0px";
                  })
                  .map((item) => ({
                    rect: item.rect,
                    x: item.rect.x + item.rect.width / 2
                  }))
                  .sort((a, b) => a.x - b.x)
                : [];
              if (rowHandles.length >= 2) {
                const first = rowHandles[0];
                const last = rowHandles[rowHandles.length - 1];
                const padding = Math.min(row.rect.height / 2, 12);
                return {
                  x: row.rect.x + padding,
                  y: row.rect.y,
                  width: Math.max(row.rect.width - padding * 2, 1),
                  height: Math.max(first.rect.height, last.rect.height),
                  handles: rowHandles.map((item) => ({
                    x: item.rect.x + item.rect.width / 2,
                    y: item.rect.y + item.rect.height / 2,
                    value: item.value
                  }))
                };
              }
              if (rowVisualHandles.length >= 2) {
                const padding = Math.min(row.rect.height / 2, 12);
                const trackX = row.rect.x + padding;
                const trackWidth = Math.max(row.rect.width - padding * 2, 1);
                const valueFor = (x) => {
                  const ratio = Math.max(0, Math.min(1, (x - trackX) / trackWidth));
                  return Math.round(1 + ratio * 4);
                };
                return {
                  x: trackX,
                  y: row.rect.y,
                  width: trackWidth,
                  height: Math.max(row.rect.height, rowVisualHandles[0].rect.height),
                  handles: rowVisualHandles.slice(0, 2).map((item) => ({
                    x: item.x,
                    y: item.rect.y + item.rect.height / 2,
                    value: valueFor(item.x)
                  }))
                };
              }

              const roleHandles = Array.from(document.querySelectorAll('[role="slider"]'))
                .map((node) => ({ node, rect: node.getBoundingClientRect(), value: Number(node.getAttribute("aria-valuenow")) }))
                .filter((item) => item.rect.width > 8 && item.rect.height > 8 && Number.isFinite(item.value))
                .filter((item) => item.rect.x < 240 && item.rect.y > 100)
                .sort((a, b) => {
                  if (!labelRect) return a.rect.y - b.rect.y;
                  return Math.abs(a.rect.y - labelRect.y) - Math.abs(b.rect.y - labelRect.y);
                });
              if (roleHandles.length >= 2) {
                const closeY = roleHandles[0].rect.y;
                const handles = roleHandles
                  .filter((item) => Math.abs(item.rect.y - closeY) < 16)
                  .sort((a, b) => a.value - b.value || a.rect.x - b.rect.x);
                if (handles.length >= 2) {
                  const first = handles[0];
                  const last = handles[handles.length - 1];
                  const firstX = first.rect.x + first.rect.width / 2;
                  const lastX = last.rect.x + last.rect.width / 2;
                  return {
                    x: Math.min(firstX, lastX),
                    y: Math.min(first.rect.y, last.rect.y),
                    width: Math.abs(lastX - firstX),
                    height: Math.max(first.rect.height, last.rect.height),
                    handles: handles.map((item) => ({
                      x: item.rect.x + item.rect.width / 2,
                      y: item.rect.y + item.rect.height / 2,
                      value: item.value
                    }))
                  };
                }
              }

              if (row && basicRangeLabels.has(label)) {
                const padding = Math.min(row.rect.height / 2, 12);
                return {
                  x: row.rect.x + padding,
                  y: row.rect.y,
                  width: Math.max(row.rect.width - padding * 2, 1),
                  height: row.rect.height,
                  handles: []
                };
              }

              return null;
            }
            """,
            label,
        )

    async def _drag_slider_handle(
        self,
        page: Page,
        slider: dict[str, float],
        handle: str,
        target_x: float,
        y: float,
    ) -> None:
        handles = slider.get("handles") or []
        if handles:
            sorted_handles = sorted(handles, key=lambda item: (item.get("value", 0), item.get("x", 0)))
            selected = sorted_handles[0] if handle == "min" else sorted_handles[-1]
            handle_x = selected["x"]
            y = selected["y"]
        else:
            handle_x = await page.evaluate(
                """
                ({ slider, targetX }) => {
                  const candidates = Array.from(document.querySelectorAll('[role="slider"]'))
                    .map((node) => ({ node, rect: node.getBoundingClientRect() }))
                    .filter((item) => item.rect.width > 8 && item.rect.width < 35)
                    .filter((item) => item.rect.height > 8 && item.rect.height < 35)
                    .filter((item) => Math.abs((item.rect.y + item.rect.height / 2) - (slider.y + slider.height / 2)) < 20)
                    .filter((item) => item.rect.x >= slider.x - 20 && item.rect.x <= slider.x + slider.width + 20)
                    .map((item) => item.rect.x + item.rect.width / 2)
                    .sort((a, b) => Math.abs(a - targetX) - Math.abs(b - targetX));
                  return candidates[0] || targetX;
                }
                """,
                {"slider": slider, "targetX": target_x},
            )
        try:
            await page.mouse.move(handle_x, y)
            await page.mouse.down()
            await page.mouse.move(target_x, y, steps=8)
            await page.mouse.up()
            with suppress(PlaywrightError):
                await page.evaluate("() => window.getSelection()?.removeAllRanges()")
        except PlaywrightError:
            with suppress(PlaywrightError):
                await page.mouse.up()

    async def _extract_results(self, page: Page, limit: int) -> list[BlueDotResult]:
        raw_results = await page.evaluate(
            """
            ({ labels, limit }) => {
              const sliderLabels = new Set(labels);
              const all = Array.from(document.querySelectorAll("body *"));
              const detailCards = all
                .map((node) => ({ node, rect: node.getBoundingClientRect(), text: (node.innerText || "").trim() }))
                .filter((item) => item.rect.width > 250 && item.rect.height > 120)
                .filter((item) => item.rect.height <= 520)
                .filter((item) => item.rect.x > 220)
                .filter((item) => !item.text.includes("Filter By"))
                .filter((item) => !item.text.includes("Add Track"))
                .filter((item) => labels.some((label) => item.text.includes(label)))
                .filter((item) => item.text.split("\\n").length >= 6 && item.text.split("\\n").length <= 28)
                .filter((item) => item.text.includes("Album") || item.text.includes("Publisher") || item.text.includes("Stem Files"))
                .sort((a, b) => a.rect.y - b.rect.y)
                .slice(0, limit);

              const fromDetailCards = detailCards.map((item) => {
                const lines = item.text.split("\\n").map((line) => line.trim()).filter(Boolean);
                const sliders = {};
                labels.forEach((label) => {
                  if (lines.includes(label)) sliders[label] = null;
                });

                const chips = Array.from(item.node.querySelectorAll("button, [role=button], span, div"))
                  .map((node) => (node.innerText || node.textContent || "").trim())
                  .filter((text) => text && text.length <= 32)
                  .filter((text, index, arr) => arr.indexOf(text) === index)
                  .filter((text) => !sliderLabels.has(text));

                return {
                  lines,
                  sliders,
                  chips,
                  url: item.node.querySelector("a")?.href || null
                };
              });

              if (fromDetailCards.length > 0) return fromDetailCards;

              const stop = new Set([
                "Filter By", "Clear all", "Mood", "Density", "Energy", "Gravity", "Ensemble",
                "Melody", "Tension", "Rhythm", "Instruments", "Tags", "Keys", "BPM", "Length",
                "Adv. search", "Add Track", "Drop audio files to add reference tracks to your mix",
                "Supported formats: .mp3, .wav"
              ]);
              const textNodes = all
                .map((node) => {
                  const rect = node.getBoundingClientRect();
                  const text = (node.innerText || node.textContent || "").trim();
                  return { node, rect, text };
                })
                .filter((item) => item.text && item.text.length <= 80)
                .filter((item) => !item.text.includes("\\n"))
                .filter((item) => item.rect.x >= 220 && item.rect.y >= 110 && item.rect.y <= window.innerHeight - 120)
                .filter((item) => item.rect.width >= 40 && item.rect.height >= 10 && item.rect.height <= 80)
                .filter((item) => !stop.has(item.text))
                .filter((item) => !/^[0-9: /+.-]+$/.test(item.text))
                .filter((item) => !/^\\d+:\\d{2}$/.test(item.text))
                .sort((a, b) => a.rect.y - b.rect.y || a.rect.x - b.rect.x);

              const rows = [];
              const seen = new Set();
              for (let index = 0; index < textNodes.length - 1 && rows.length < limit; index += 1) {
                const current = textNodes[index];
                const next = textNodes[index + 1];
                if (Math.abs(next.rect.y - current.rect.y) > 34 && Math.abs(next.rect.y - (current.rect.y + current.rect.height)) > 34) {
                  continue;
                }
                if (next.text === current.text) continue;
                const key = current.text + "\\n" + next.text;
                if (seen.has(key)) continue;
                seen.add(key);
                rows.push({ lines: [current.text, next.text], sliders: {}, chips: [], url: current.node.closest("a")?.href || null });
                index += 1;
              }
              if (rows.length > 0) return rows;

              const bodyLines = (document.body.innerText || "")
                .split("\\n")
                .map((line) => line.trim())
                .filter(Boolean);
              const advIndex = bodyLines.lastIndexOf("Adv. search");
              const candidateLines = bodyLines
                .slice(advIndex >= 0 ? advIndex + 1 : 0)
                .filter((line) => !stop.has(line))
                .filter((line) => !/^[0-9: /+.-]+$/.test(line))
                .filter((line) => !/^\\d+:\\d{2}$/.test(line))
                .filter((line) => line.length <= 80);
              const bodyRows = [];
              const seenBody = new Set();
              for (let index = 0; index < candidateLines.length - 1 && bodyRows.length < limit; index += 1) {
                const title = candidateLines[index];
                const subtitle = candidateLines[index + 1];
                if (title === subtitle) continue;
                const key = title + "\\n" + subtitle;
                if (seenBody.has(key)) continue;
                seenBody.add(key);
                bodyRows.push({ lines: [title, subtitle], sliders: {}, chips: [], url: null });
                index += 1;
              }
              return bodyRows;
            }
            """,
            {"labels": list(SLIDER_LABELS), "limit": limit},
        )

        return [self._parse_result(raw) for raw in raw_results]

    def _parse_result(self, raw: dict[str, Any]) -> BlueDotResult:
        lines = [line for line in raw.get("lines", []) if line]
        title = lines[0] if lines else "Untitled"
        subtitle = lines[1] if len(lines) > 1 else None

        field_map = self._parse_field_lines(lines)
        chips = raw.get("chips", [])
        tags, instruments = self._split_chips(chips)

        return BlueDotResult(
            title=title,
            subtitle=subtitle,
            album=field_map.get("Album"),
            published=field_map.get("Published"),
            key=field_map.get("Key"),
            bpm=field_map.get("BPM"),
            stem_files=field_map.get("Stem Files"),
            publisher=field_map.get("Publisher"),
            sliders={label.lower(): None for label in raw.get("sliders", {})},
            tags=tags,
            instruments=instruments,
            url=raw.get("url"),
        )

    @staticmethod
    def _parse_field_lines(lines: list[str]) -> dict[str, str]:
        fields = {"Album", "Published", "Key", "BPM", "Stem Files", "Publisher", "ISRC"}
        parsed: dict[str, str] = {}

        for index, line in enumerate(lines[:-1]):
            if line in fields:
                parsed[line] = lines[index + 1]

        return parsed

    def _split_chips(self, chips: list[str]) -> tuple[list[str], list[str]]:
        ignored = {
            "Album",
            "Published",
            "Key",
            "BPM",
            "Stem Files",
            "Publisher",
            "ISRC",
            "Load all variations",
        }
        cleaned = [chip for chip in chips if chip not in ignored and not re.match(r"^[0-9/:+ -]+$", chip)]
        tags: list[str] = []
        instruments: list[str] = []
        unknown: list[str] = []

        for chip in cleaned:
            if chip in self.known_tags:
                tags.append(chip)
            elif chip in self.known_genres:
                tags.append(chip)
            elif chip in self.known_instruments:
                instruments.append(chip)
            else:
                unknown.append(chip)

        return tags + unknown, instruments
