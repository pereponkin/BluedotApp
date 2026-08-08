from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BlueDotResult:
    title: str
    subtitle: str | None = None
    album: str | None = None
    published: str | None = None
    key: str | None = None
    bpm: str | None = None
    stem_files: str | None = None
    publisher: str | None = None
    sliders: dict[str, float | None] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    instruments: list[str] = field(default_factory=list)
    url: str | None = None


@dataclass(frozen=True)
class SearchReport:
    prompt: str
    preset_name: str
    applied_sliders: dict[str, tuple[int, int]]
    results: list[BlueDotResult]
    fallback_used: str | None = None
    missing_sliders: dict[str, tuple[int, int]] = field(default_factory=dict)
    selectable_filters: dict[str, list[str]] = field(default_factory=dict)


def needs_broader_search(report: SearchReport) -> bool:
    """Tell whether a report is empty enough to justify a broader retry.

    Blue Dot answers a hopeless filter set with a single placeholder card
    instead of an empty list, so that case counts as no results too.

    Args:
        report (SearchReport): Report of a finished search.

    Returns:
        (bool)
    """
    if not report.results:
        return True
    if len(report.results) == 1:
        return report.results[0].title.lower().startswith("no results")
    return False
