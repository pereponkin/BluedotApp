from __future__ import annotations

import argparse
import asyncio
import json
import os
from time import perf_counter, time_ns


CLI_STARTED_AT = perf_counter()
CLI_STARTED_UNIX_MS = time_ns() / 1_000_000
from dataclasses import asdict

from playwright.async_api import Error as PlaywrightError

from .bluedot import BlueDotAdapter, allowed_slider_labels
from .intent import (
    GeminiUnavailableError,
    IntentMapper,
    broaden_intent,
    selectable_filters,
)
from .launcher import (
    InstanceAlreadyRunning,
    InstanceLock,
    choose_browser,
    chrome_is_available,
    resolve_browser,
)
from .browser_install import ensure_firefox_installed
from .models import SearchReport, needs_broader_search
from .notify import report_failure
from .reporting import print_mapper_warning, print_network_events, print_search_report
from .startup_timing import StartupTimer
from .config import STATE_DIR
from .settings import ProviderSettingsStore


def _launcher_elapsed_offset_ms() -> float:
    raw_value = os.environ.get("BLUEDOT_LAUNCH_STARTED_UNIX_MS")
    if not raw_value:
        return 0.0
    try:
        return max(0.0, CLI_STARTED_UNIX_MS - float(raw_value))
    except ValueError:
        return 0.0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bluedot-agent")
    parser.add_argument(
        "--browser",
        choices=("firefox", "chrome"),
        help="Browser for this launch; overrides environment and saved settings",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Check the packaged runtime without opening Blue Dot",
    )
    parser.add_argument(
        "--require-frozen",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    subparsers = parser.add_subparsers(dest="command")

    login_parser = subparsers.add_parser("login", help="Open the selected browser for manual Blue Dot login")
    login_parser.set_defaults(func=_command_login)

    panel_parser = subparsers.add_parser("panel", help="Open Blue Dot with the embedded agent panel")
    panel_parser.set_defaults(func=_command_panel)

    probe_parser = subparsers.add_parser("probe-network", help="Record Blue Dot XHR/fetch traffic while filters change")
    probe_parser.set_defaults(func=_command_probe_network)
    probe_parser.add_argument("--seconds", type=int, default=120)
    probe_parser.add_argument("--json", action="store_true", help="Print raw JSON events")

    state_probe_parser = subparsers.add_parser("state-probe", help="Inspect Blue Dot browser-side filter state")
    state_probe_parser.set_defaults(func=_command_state_probe)
    state_probe_parser.add_argument("prompt", nargs="?", help="Optional natural-language request for automatic filter changes")
    state_probe_parser.add_argument("--preset", default="cozy_narration_broad")
    state_probe_parser.add_argument("--seconds", type=int, default=60)
    state_probe_parser.add_argument("--manual", action="store_true", help="Wait for manual filter changes instead of applying a prompt")
    state_probe_parser.add_argument("--via-react", action="store_true", help="Apply range filters by calling the React search context instead of dragging UI sliders")
    state_probe_parser.add_argument(
        "--include-advanced",
        action="store_true",
        help="Also inspect Melody/Tension/Rhythm during automatic probing",
    )

    api_search_parser = subparsers.add_parser("api-search", help="Search Blue Dot through its GraphQL API")
    api_search_parser.set_defaults(func=_command_api_search)
    api_search_parser.add_argument("prompt", help="Natural-language music request")
    api_search_parser.add_argument("--preset", default="auto")
    api_search_parser.add_argument("--limit", type=int, default=10)
    api_search_parser.add_argument("--json", action="store_true", help="Print raw JSON")
    api_search_parser.add_argument(
        "--basic-only",
        action="store_true",
        help="Use only Mood/Density/Energy/Gravity/Ensemble; API mode includes advanced sliders by default",
    )
    api_search_parser.add_argument(
        "--close",
        action="store_true",
        help="Close the browser after printing candidates; default keeps it open",
    )
    api_search_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without a visible browser window; useful only with --close",
    )

    playlist_parser = subparsers.add_parser("playlist", help="Open Blue Dot with agent-selected filters applied")
    playlist_parser.set_defaults(func=_command_playlist)
    playlist_parser.add_argument("prompt", nargs="?", help="Natural-language music request")
    playlist_parser.add_argument(
        "--prompt-env",
        help="Read the prompt from this environment variable (used by the detached launcher)",
    )
    playlist_parser.add_argument("--preset", default="auto")
    playlist_parser.add_argument(
        "--basic-only",
        action="store_true",
        help="Use only Mood/Density/Energy/Gravity/Ensemble",
    )

    playlist_probe_parser = subparsers.add_parser("playlist-probe", help="Debug one-shot filtered Blue Dot playlist loading")
    playlist_probe_parser.set_defaults(func=_command_playlist_probe)
    playlist_probe_parser.add_argument("prompt", help="Natural-language music request")
    playlist_probe_parser.add_argument("--preset", default="auto")
    playlist_probe_parser.add_argument("--seconds", type=int, default=20)
    playlist_probe_parser.add_argument(
        "--basic-only",
        action="store_true",
        help="Use only Mood/Density/Energy/Gravity/Ensemble",
    )

    session_parser = subparsers.add_parser("session", help="Keep one browser window and run repeated searches")
    session_parser.set_defaults(func=_command_session)
    session_parser.add_argument("prompt", nargs="?", help="Optional first music request")
    session_parser.add_argument("--preset", default="auto")
    session_parser.add_argument("--limit", type=int, default=10)
    session_parser.add_argument(
        "--include-advanced",
        action="store_true",
        help="Also automate Melody/Tension/Rhythm; off by default",
    )
    session_parser.add_argument(
        "--no-auto",
        action="store_true",
        help="Disable automatic broad fallback",
    )

    search_parser = subparsers.add_parser("search", help="Search Blue Dot Sessions")
    search_parser.set_defaults(func=_command_search)
    search_parser.add_argument("prompt", help="Natural-language music request")
    search_parser.add_argument("--preset", default="auto")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--json", action="store_true", help="Print raw JSON")
    search_parser.add_argument(
        "--auto",
        action="store_true",
        help="Try the selected preset, then broad fallback if there are no usable results",
    )
    search_parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Leave the browser open after searching",
    )
    search_parser.add_argument(
        "--include-advanced",
        action="store_true",
        help="Also automate Melody/Tension/Rhythm; off by default because Blue Dot sliders are fragile",
    )
    search_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print mapped filters without opening Blue Dot",
    )
    search_parser.add_argument(
        "--debug-dom",
        action="store_true",
        help="Print compact DOM candidates after applying filters",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.self_test:
        from .self_test import print_self_test, run_self_test

        result = run_self_test(
            browser=args.browser,
            require_frozen=args.require_frozen,
        )
        print_self_test(result)
        if not result["ok"]:
            raise SystemExit(1)
        return
    if args.command is None:
        args.command = "panel"
        args.func = _command_panel
    try:
        if _command_uses_browser(args):
            with InstanceLock(STATE_DIR / "agent.lock"):
                args.func(args, parser)
        else:
            args.func(args, parser)
    except InstanceAlreadyRunning as error:
        report_failure([str(error)])


def _command_uses_browser(args) -> bool:
    return not (
        args.command == "search"
        and getattr(args, "dry_run", False)
    )


def _runtime_settings() -> ProviderSettingsStore:
    return ProviderSettingsStore()


def _runtime_browser(args, settings: ProviderSettingsStore | None = None):
    store = settings or _runtime_settings()
    browser = resolve_browser(
        cli_browser=getattr(args, "browser", None),
        environ=os.environ,
        settings=store,
        chooser=choose_browser,
    )
    if browser == "chrome" and not chrome_is_available():
        explicit = getattr(args, "browser", None) or os.environ.get("BLUEDOT_BROWSER")
        if not explicit:
            browser = choose_browser()
            store.save_browser(browser)
        else:
            raise RuntimeError(
                "Google Chrome не найден. Установите его с google.com/chrome "
                "или выберите Firefox через --browser firefox."
            )
    if browser == "firefox":
        ensure_firefox_installed()
    return browser


def _adapter(args, *, headed: bool = True) -> BlueDotAdapter:
    settings = _runtime_settings()
    browser = _runtime_browser(args, settings) if hasattr(args, "browser") else "firefox"
    return BlueDotAdapter(
        headed=headed,
        browser=browser,
        download_directory=settings.download_directory(),
    )


def _report_playwright_failure(error: PlaywrightError, *hints: str) -> None:
    report_failure(
        [
            "Не удалось открыть выбранный браузер.",
            *hints,
            f"Деталь: {str(error).splitlines()[0]}",
        ]
    )


def _command_login(args, parser) -> None:
    asyncio.run(_adapter(args).login())


def _command_panel(args, parser) -> None:
    startup_timer = StartupTimer(
        started_at=CLI_STARTED_AT,
        elapsed_offset_ms=_launcher_elapsed_offset_ms(),
    )
    startup_timer.mark("cli_ready")
    try:
        settings = _runtime_settings()
        browser = _runtime_browser(args, settings)
        adapter = BlueDotAdapter(
            headed=True,
            browser=browser,
            download_directory=settings.download_directory(),
        )
        startup_timer.mark("adapter_ready", detail=f"browser={browser}")
        asyncio.run(adapter.panel(startup_timer=startup_timer, settings=settings))
    except GeminiUnavailableError as error:
        startup_timer.mark("startup_failed")
        report_failure([str(error)])
    except PlaywrightError as error:
        startup_timer.mark("startup_failed")
        _report_playwright_failure(
            error,
            "Если окно агента уже открыто, закрой его и повтори запуск панели.",
        )
    except Exception as error:
        detail = str(error).splitlines()[0] or type(error).__name__
        startup_timer.mark(
            "runtime_failed",
            detail=f"{type(error).__name__}: {detail}"[:500],
        )
        report_failure(
            [
                "Панель Blue Dot Agent остановилась из-за ошибки.",
                f"Деталь: {type(error).__name__}: {detail}",
                f"Журнал запуска: {startup_timer.path}",
            ]
        )
    finally:
        startup_timer.mark("process_exit")


def _command_probe_network(args, parser) -> None:
    try:
        events = asyncio.run(_adapter(args).probe_network(seconds=args.seconds))
    except PlaywrightError as error:
        _report_playwright_failure(
            error,
            "Если окно агента уже открыто, закрой его или запускай probe из той же сессии позже.",
        )
        return
    if args.json:
        print(json.dumps([asdict(event) for event in events], ensure_ascii=False, indent=2))
    else:
        print_network_events(events)


def _command_state_probe(args, parser) -> None:
    intent = None
    if not args.manual:
        prompt = args.prompt or "спокойный ненапряжный саундтрек под уютный нарратив"
        intent = IntentMapper().map_prompt(prompt, preset_name=args.preset)
    try:
        log_path = asyncio.run(
            _adapter(args).state_probe(
                intent=intent,
                include_advanced=args.include_advanced,
                seconds=args.seconds,
                via_react=args.via_react,
            )
        )
        print(f"State probe log: {log_path}")
    except PlaywrightError as error:
        _report_playwright_failure(
            error,
            "Если окно агента уже открыто, закрой его и повтори state-probe.",
        )


def _command_api_search(args, parser) -> None:
    intent = _map_intent(IntentMapper(), args.prompt, args.preset)
    try:
        report = asyncio.run(
            _adapter(args, headed=not args.headless).api_search(
                intent,
                limit=args.limit,
                include_advanced=not args.basic_only,
                keep_open=not args.close,
            )
        )
    except PlaywrightError as error:
        _report_playwright_failure(
            error,
            "Если окно агента уже открыто, закрой его или запускай API-поиск из будущей session-команды.",
        )
        return
    if args.close and args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    elif args.close:
        print_search_report(report)


def _command_playlist(args, parser) -> None:
    prompt = os.environ.get(args.prompt_env) if args.prompt_env else args.prompt
    if not prompt:
        parser.error("playlist requires a prompt")
    intent = _map_intent(IntentMapper(), prompt, args.preset)
    try:
        asyncio.run(
            _adapter(args).playlist(
                intent,
                include_advanced=not args.basic_only,
            )
        )
    except PlaywrightError as error:
        _report_playwright_failure(
            error,
            "Если окно агента уже открыто, работай в его terminal session или закрой окно.",
        )


def _command_playlist_probe(args, parser) -> None:
    intent = _map_intent(IntentMapper(), args.prompt, args.preset)
    try:
        log_path = asyncio.run(
            _adapter(args).playlist_probe(
                intent,
                include_advanced=not args.basic_only,
                seconds=args.seconds,
            )
        )
        print(f"Playlist probe log: {log_path}")
    except PlaywrightError as error:
        _report_playwright_failure(
            error,
            "Если окно агента уже открыто, закрой его и повтори probe.",
        )


def _command_session(args, parser) -> None:
    first_intent = None
    if args.prompt:
        first_intent = _map_intent(IntentMapper(), args.prompt, args.preset)
    try:
        asyncio.run(
            _adapter(args).session(
                first_intent=first_intent,
                limit=args.limit,
                include_advanced=args.include_advanced,
                auto_fallback=not args.no_auto,
                preset_name=args.preset,
            )
        )
    except PlaywrightError as error:
        _report_playwright_failure(
            error,
            "Если окно агента уже открыто, работай в его terminal session или закрой окно.",
        )


def _command_search(args, parser) -> None:
    mapper = IntentMapper()
    intent = _map_intent(mapper, args.prompt, args.preset)
    try:
        _run_search_command(args, mapper, intent)
    except PlaywrightError as error:
        _report_playwright_failure(
            error,
            "Чаще всего это значит, что окно агента уже открыто с тем же профилем.",
            "Закрой текущее окно браузера агента и повтори команду.",
        )


def _run_search_command(args, mapper: IntentMapper, intent) -> None:
    if args.dry_run:
        applied_sliders = _visible_sliders(intent.sliders, include_advanced=args.include_advanced)
        report = SearchReport(
            prompt=intent.prompt,
            preset_name=intent.preset_name,
            applied_sliders=applied_sliders,
            results=[],
            selectable_filters=selectable_filters(intent),
        )
    elif args.debug_dom:
        candidates = asyncio.run(
            _adapter(args).debug_dom(intent, limit=args.limit)
        )
        print(json.dumps(candidates, ensure_ascii=False, indent=2))
        return
    elif args.auto:
        report = _search(args, intent)
        if args.keep_open:
            if args.json:
                print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
            else:
                print_search_report(report)
            return
        if needs_broader_search(report):
            fallback_report = _search(args, broaden_intent(intent))
            report = SearchReport(
                prompt=fallback_report.prompt,
                preset_name=fallback_report.preset_name,
                applied_sliders=fallback_report.applied_sliders,
                results=fallback_report.results,
                selectable_filters=fallback_report.selectable_filters,
                fallback_used="broadened_filters",
                missing_sliders=fallback_report.missing_sliders,
            )
    else:
        report = _search(args, intent)
    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        print_search_report(report)


def _search(args, intent) -> SearchReport:
    return asyncio.run(
        _adapter(args).search(
            intent,
            limit=args.limit,
            keep_open=args.keep_open,
            include_advanced=args.include_advanced,
        )
    )


def _map_intent(mapper: IntentMapper, prompt: str, preset: str):
    intent = mapper.map_prompt(prompt, preset_name=preset)
    print_mapper_warning(mapper)
    return intent


def _visible_sliders(
    sliders: dict[str, tuple[int, int]],
    include_advanced: bool = False,
) -> dict[str, tuple[int, int]]:
    allowed = allowed_slider_labels(include_advanced)
    return {name: value for name, value in sliders.items() if name in allowed}


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
