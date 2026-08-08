from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .diagnostics import NetworkEvent, redact
from .models import BlueDotResult, SearchReport


def print_mapper_warning(mapper: Any) -> None:
    """Print the warning left by the last prompt mapping, if there was one.

    Args:
        mapper (Any): Intent mapper that just handled a prompt.
    """
    if mapper.last_warning:
        print(f"Предупреждение: {mapper.last_warning}")


def print_search_report(report: SearchReport) -> None:
    """Print a finished search with every candidate spelled out.

    Args:
        report (SearchReport): Report of a finished search.
    """
    print(f"Запрос: {report.prompt}")
    print(f"Профиль: {report.preset_name}")
    if report.fallback_used:
        print(f"Fallback: {report.fallback_used}")
    print("Фильтры Blue Dot:")
    _print_filters(report)
    if report.missing_sliders:
        print("Не установились:")
        _print_ranges(report.missing_sliders)

    if not report.results:
        print("\nРезультаты не найдены или карточки не удалось прочитать.")
        return

    print("\nКандидаты:")
    for index, result in enumerate(report.results, start=1):
        _print_candidate(index, result)


def print_session_report(report: SearchReport) -> None:
    """Print a compact search summary for the interactive session.

    Args:
        report (SearchReport): Report of a finished search.
    """
    print(f"Профиль: {report.preset_name}")
    if report.fallback_used:
        print(f"Fallback: {report.fallback_used}")
    print("Applied:")
    _print_filters(report)
    if report.missing_sliders:
        print("Missing:")
        _print_ranges(report.missing_sliders)
    print("Кандидаты:")
    if not report.results:
        print("  результатов нет")
    for index, result in enumerate(report.results[:10], start=1):
        subtitle = f" / {result.subtitle}" if result.subtitle else ""
        print(f"  {index}. {result.title}{subtitle}")


def print_playlist_report(report: SearchReport) -> None:
    """Print the filters behind a playlist left open in Blue Dot.

    Args:
        report (SearchReport): Report of a finished playlist run.
    """
    print(f"Профиль: {report.preset_name}")
    print("Подборка открыта в Blue Dot через один GraphQL-запрос фильтров.")
    print("Фильтры агента:")
    _print_filters(report)
    if report.missing_sliders:
        print("Missing:")
        _print_ranges(report.missing_sliders)
        print("Плейлист оставлен открытым, но выдача может быть шире нужной.")


def print_live_results(results: list[BlueDotResult]) -> None:
    """Print the first track of a search left open for listening.

    Args:
        results (list): Tracks read from the Blue Dot page.
    """
    print("Найдено для прослушивания:")
    if not results:
        print("  результатов нет")
        return
    first = results[0]
    subtitle = f" / {first.subtitle}" if first.subtitle else ""
    print(f"  {first.title}{subtitle}")


def print_network_events(events: list[NetworkEvent]) -> None:
    """Print recorded Blue Dot traffic with secrets masked.

    Notification polling is left out: it fires on a timer and says nothing
    about the filters under study.

    Args:
        events (list): Events captured during a probe.
    """
    visible_events = [
        event
        for event in events
        if event.post_data is None or "getNotifications" not in event.post_data
    ]
    if not visible_events:
        print("XHR/fetch запросы не зафиксированы.")
        return

    print("Network events:")
    for index, event in enumerate(visible_events, start=1):
        safe_event = redact(asdict(event))
        status = f" status={event.status}" if event.status is not None else ""
        print(f"{index}. {event.direction} {event.method} {event.resource_type}{status}")
        print(f"   {safe_event['url']}")
        if safe_event.get("post_data"):
            print(f"   post: {safe_event['post_data']}")
        if safe_event.get("body_preview"):
            print(f"   body: {safe_event['body_preview']}")


def _print_filters(report: SearchReport) -> None:
    _print_ranges(report.applied_sliders)
    for name, values in report.selectable_filters.items():
        print(f"  - {name}: {', '.join(values)}")


def _print_ranges(ranges: dict[str, tuple[int, int]]) -> None:
    for name, value_range in ranges.items():
        print(f"  - {name}: {value_range[0]}-{value_range[1]}")


def _print_candidate(index: int, result: BlueDotResult) -> None:
    print(f"\n{index}. {result.title}")
    if result.subtitle:
        print(f"   {result.subtitle}")
    facts = []
    if result.key:
        facts.append(f"Key {result.key}")
    if result.bpm:
        facts.append(f"BPM {result.bpm}")
    if result.album:
        facts.append(f"Album {result.album}")
    if facts:
        print(f"   {' | '.join(facts)}")
    if result.sliders:
        print(f"   Шкалы: {', '.join(sorted(result.sliders.keys()))}")
    if result.tags:
        print(f"   Теги/инструменты: {', '.join(result.tags + result.instruments)}")
    if result.url:
        print(f"   {result.url}")
