from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from .config import load_yaml
from .gemini import GeminiClient, GeminiError
from .llm import (
    FilterInterpreterClient,
    ProviderRequestError,
    create_client,
)
from .schema import FilterSchema, FilterValidationError
from .settings import (
    PROVIDER_SPECS,
    ProviderConfigurationError,
    ProviderSettingsStore,
)


@dataclass(frozen=True)
class BlueDotIntent:
    prompt: str
    preset_name: str
    sliders: dict[str, tuple[int, int]]
    tags: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    instruments: list[str] = field(default_factory=list)
    keys: list[str] = field(default_factory=list)
    bpm: tuple[int, int] | None = None
    length: tuple[int, int] | None = None


def selectable_filters(intent: BlueDotIntent) -> dict[str, list[str]]:
    groups = {
        "Tags": intent.tags,
        "Genres": intent.genres,
        "Instruments": intent.instruments,
        "Keys": intent.keys,
    }
    return {name: list(values) for name, values in groups.items() if values}


class IntentParser(Protocol):
    name: str

    def parse(self, prompt: str) -> BlueDotIntent: ...


class ProviderUnavailableError(RuntimeError):
    pass


class GeminiUnavailableError(ProviderUnavailableError):
    pass


class PresetIntentParser:
    name = "preset"

    def __init__(self, preset_name: str, schema: FilterSchema) -> None:
        self._preset_name = preset_name
        self._schema = schema
        self._rules = load_yaml("mapping_rules.yaml")

    def parse(self, prompt: str) -> BlueDotIntent:
        preset = self._rules.get("presets", {}).get(self._preset_name)
        if not isinstance(preset, dict):
            raise ValueError(f"Unknown preset: {self._preset_name}")
        bluedot = preset.get("bluedot", {})
        if not isinstance(bluedot, dict):
            raise ValueError(f"Preset {self._preset_name} is missing bluedot mapping")
        return _intent_from_configuration(
            prompt,
            self._preset_name,
            bluedot,
            self._schema,
        )


class RuleBasedIntentParser:
    name = "rule_based"

    _COZY = ("уют", "ненапряж", "cozy", "gentle narration", "calm narration")
    _CHASE = ("погон", "chase", "преследован", "динамич", "action")
    _MYSTERY = ("загад", "таинств", "вкрадчив", "осторож", "myster", "sneak", "cautious")
    _FRIENDLY = ("дружелюб", "заигрыв", "игрив", "friendly", "flirt", "playful")
    _CONFIDENT = ("уверенн", "превосход", "confident", "superior")
    _DIGITAL = ("цифров", "технолог", "digital", "technology")
    _MEDIEVAL = ("средневек", "medieval", "middle ages", "рыцар")
    _ARISTOCRATIC = ("аристократ", "xviii", "18 век", "baroque", "барок")
    _STRINGS = ("струн", "скрип", "violin", "strings")

    def __init__(self, schema: FilterSchema) -> None:
        self._schema = schema

    def parse(self, prompt: str) -> BlueDotIntent:
        lowered = prompt.casefold()
        is_confident = _contains_any(lowered, self._CONFIDENT)
        is_digital = _contains_any(lowered, self._DIGITAL)
        config: dict[str, Any] = {
            "sliders": {name: [1, 5] for name in self._schema.numeric_ranges if name not in {"BPM", "Length"}},
            "tags": [],
            "genres": [],
            "instruments": [],
            "keys": [],
            "bpm": None,
            "length": None,
        }
        sliders = config["sliders"]

        if _contains_any(lowered, self._COZY):
            sliders.update(
                Mood=[3, 5], Density=[1, 2], Energy=[1, 2], Gravity=[1, 3],
                Ensemble=[1, 3], Melody=[2, 4], Tension=[1, 2], Rhythm=[1, 2],
            )
        if _contains_any(lowered, self._CHASE):
            sliders.update(
                Mood=[2, 5], Density=[3, 5], Energy=[4, 5], Gravity=[3, 5],
                Ensemble=[3, 5], Melody=[1, 4], Tension=[4, 5], Rhythm=[4, 5],
            )
            config["tags"] = ["Chase"]
            config["bpm"] = [110, 200]
        if _contains_any(lowered, self._MYSTERY):
            sliders.update(
                Mood=[1, 3], Density=[1, 3], Energy=[1, 3], Gravity=[2, 4],
                Ensemble=[1, 3], Melody=[1, 4], Tension=[3, 5], Rhythm=[1, 3],
            )
            config["tags"] = ["Mysterious"]
        if _contains_any(lowered, self._FRIENDLY):
            sliders.update(
                Mood=[4, 5], Density=[1, 3], Energy=[2, 4], Gravity=[1, 2],
                Ensemble=[1, 3], Melody=[2, 5], Tension=[1, 2], Rhythm=[2, 4],
            )
            config["tags"] = ["Lighthearted"]
        if is_confident:
            sliders.update(
                Mood=[3, 5], Energy=[3, 5], Gravity=[2, 5], Rhythm=[3, 5],
            )
            config["tags"] = ["Confident"]
        if is_digital:
            sliders.update(Density=[2, 5], Energy=[3, 5], Rhythm=[3, 5])
            config["genres"] = ["Electro"]
            if is_confident:
                config["tags"] = []
        if _contains_any(lowered, self._MEDIEVAL):
            sliders.update(
                Mood=[2, 5], Density=[1, 4], Energy=[1, 4], Gravity=[2, 5],
                Ensemble=[2, 5], Melody=[3, 5], Tension=[1, 4], Rhythm=[1, 4],
            )
            config["genres"] = ["Folk"]
        if _contains_any(lowered, self._ARISTOCRATIC):
            sliders.update(
                Mood=[3, 5], Density=[1, 4], Energy=[1, 4], Gravity=[3, 5],
                Ensemble=[2, 5], Melody=[3, 5], Tension=[1, 3], Rhythm=[1, 4],
            )
            config["genres"] = ["Classical"]
        if _contains_any(lowered, self._STRINGS):
            config["instruments"] = ["Strings"]

        return _intent_from_configuration(
            prompt, self.name, config, self._schema
        )


class GeminiIntentParser:
    name = "gemini"

    def __init__(self, client: GeminiClient, schema: FilterSchema) -> None:
        self._client = client
        self._schema = schema

    def parse(self, prompt: str) -> BlueDotIntent:
        config = self._client.parse_filters(prompt, self._schema)
        return _intent_from_configuration(prompt, self.name, config, self._schema)


class GeminiRequiredIntentParser:
    name = "gemini"

    def __init__(self, parser: IntentParser | None) -> None:
        self._parser = parser

    def parse(self, prompt: str) -> BlueDotIntent:
        if self._parser is None:
            raise GeminiUnavailableError(
                "Gemini не настроен. Задайте GEMINI_API_KEY и перезапустите панель."
            )
        try:
            return self._parser.parse(prompt)
        except (GeminiError, FilterValidationError, ValueError) as error:
            raise GeminiUnavailableError(
                "Gemini не смог интерпретировать запрос. "
                "Проверьте подключение и GEMINI_MODEL, затем повторите поиск."
            ) from error


class FallbackIntentParser:
    name = "auto"

    def __init__(self, primary: IntentParser | None, fallback: IntentParser) -> None:
        self._primary = primary
        self._fallback = fallback
        self.last_warning: str | None = None

    def parse(self, prompt: str) -> BlueDotIntent:
        self.last_warning = None
        if self._primary is not None:
            try:
                return self._primary.parse(prompt)
            except (GeminiError, FilterValidationError, ValueError) as error:
                self.last_warning = f"Gemini parser failed; using local rules: {error}"
        return self._fallback.parse(prompt)


class IntentMapper:
    def __init__(
        self,
        *,
        schema: FilterSchema | None = None,
        auto_parser: IntentParser | None = None,
        gemini_required: bool = False,
    ) -> None:
        self._schema = schema or FilterSchema.from_inventory()
        if auto_parser is None:
            rule_parser = RuleBasedIntentParser(self._schema)
            api_key = os.environ.get("GEMINI_API_KEY", "").strip()
            if gemini_required and not api_key:
                raise GeminiUnavailableError(
                    "Gemini не настроен. Задайте GEMINI_API_KEY и перезапустите панель."
                )
            primary = None
            if api_key:
                client = GeminiClient(
                    api_key,
                    model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
                )
                primary = GeminiIntentParser(client, self._schema)
            auto_parser = (
                GeminiRequiredIntentParser(primary)
                if gemini_required
                else FallbackIntentParser(primary, rule_parser)
            )
        elif gemini_required:
            auto_parser = GeminiRequiredIntentParser(auto_parser)
        self._auto_parser = auto_parser
        self.last_warning: str | None = None

    def map_prompt(self, prompt: str, preset_name: str = "auto") -> BlueDotIntent:
        if preset_name != "auto":
            self.last_warning = None
            return PresetIntentParser(preset_name, self._schema).parse(prompt)
        intent = self._auto_parser.parse(prompt)
        self.last_warning = getattr(self._auto_parser, "last_warning", None)
        return intent


class ConfiguredIntentMapper:
    """Interpret each request with the provider currently selected in settings."""

    def __init__(
        self,
        store: ProviderSettingsStore,
        *,
        schema: FilterSchema | None = None,
        client_factory: Callable[
            [str, str, str],
            FilterInterpreterClient,
        ] = create_client,
    ) -> None:
        self._store = store
        self._schema = schema or FilterSchema.from_inventory()
        self._client_factory = client_factory
        self.last_warning: str | None = None

    def map_prompt(
        self,
        prompt: str,
        preset_name: str = "auto",
    ) -> BlueDotIntent:
        if preset_name != "auto":
            return PresetIntentParser(preset_name, self._schema).parse(prompt)
        credentials = None
        try:
            credentials = self._store.credentials()
            client = self._client_factory(
                credentials.provider,
                credentials.api_key,
                credentials.model,
            )
            for attempt in range(2):
                try:
                    config = client.parse_filters(prompt, self._schema)
                    config = _enforce_filter_budget(
                        prompt,
                        config,
                        self._schema,
                    )
                    intent = _intent_from_configuration(
                        prompt,
                        credentials.provider,
                        config,
                        self._schema,
                    )
                    return intent
                except FilterValidationError:
                    if attempt == 1:
                        cleaned = _discard_unknown_selectable_values(
                            config,
                            self._schema,
                        )
                        return _intent_from_configuration(
                            prompt,
                            credentials.provider,
                            cleaned,
                            self._schema,
                        )
                except (ProviderRequestError, ValueError):
                    if attempt == 1:
                        raise
        except ProviderConfigurationError as error:
            raise ProviderUnavailableError(str(error)) from error
        except (
            ProviderRequestError,
            FilterValidationError,
            ValueError,
        ) as error:
            provider = "ИИ-провайдер"
            if credentials is not None:
                provider = PROVIDER_SPECS[credentials.provider].label
            raise ProviderUnavailableError(
                f"{provider} не смог интерпретировать запрос. "
                "Проверьте API-ключ, модель и подключение, затем повторите поиск."
            ) from error


def broaden_intent(
    intent: BlueDotIntent,
    schema: FilterSchema | None = None,
) -> BlueDotIntent:
    schema = schema or FilterSchema.from_inventory()
    sliders = {
        name: _broaden_range(name, value_range, schema)
        for name, value_range in intent.sliders.items()
    }
    bpm = _broaden_range("BPM", intent.bpm, schema) if intent.bpm else None
    length = _broaden_range("Length", intent.length, schema) if intent.length else None
    return replace(intent, sliders=sliders, bpm=bpm, length=length)


def _broaden_range(
    name: str,
    value_range: tuple[int, int],
    schema: FilterSchema,
) -> tuple[int, int]:
    domain_min, domain_max = schema.numeric_ranges[name]
    step = 10 if name == "BPM" else 30 if name == "Length" else 1
    return max(domain_min, value_range[0] - step), min(domain_max, value_range[1] + step)


def _intent_from_configuration(
    prompt: str,
    source_name: str,
    config: dict[str, Any],
    schema: FilterSchema,
) -> BlueDotIntent:
    validated = schema.validate_configuration(config)
    return BlueDotIntent(
        prompt=prompt,
        preset_name=source_name,
        sliders=validated["sliders"],
        tags=validated["tags"],
        genres=validated["genres"],
        instruments=validated["instruments"],
        keys=validated["keys"],
        bpm=validated["bpm"],
        length=validated["length"],
    )


def _discard_unknown_selectable_values(
    config: dict[str, Any],
    schema: FilterSchema,
) -> dict[str, Any]:
    cleaned = dict(config)
    for field, group in (
        ("tags", "Tags"),
        ("genres", "Genres"),
        ("instruments", "Instruments"),
        ("keys", "Keys"),
    ):
        values = cleaned.get(field)
        if isinstance(values, list):
            allowed = schema.selectable_values[group]
            cleaned[field] = [
                value
                for value in values
                if isinstance(value, str) and value in allowed
            ]
    return cleaned


def _enforce_filter_budget(
    prompt: str,
    config: dict[str, Any],
    schema: FilterSchema,
) -> dict[str, Any]:
    limited = dict(config)
    sliders = config.get("sliders")
    if isinstance(sliders, dict):
        limited_sliders = dict(sliders)
        ranked: list[tuple[float, float, int, str]] = []
        slider_priority = {
            name: priority
            for priority, name in enumerate(
                (
                    "Ensemble",
                    "Density",
                    "Gravity",
                    "Melody",
                    "Rhythm",
                    "Tension",
                    "Energy",
                    "Mood",
                )
            )
        }
        for name, value in sliders.items():
            if name not in schema.numeric_ranges:
                continue
            try:
                minimum, maximum = schema.validate_range(name, value)
            except FilterValidationError:
                continue
            domain_min, domain_max = schema.numeric_ranges[name]
            if (minimum, maximum) == (domain_min, domain_max):
                continue
            domain_span = domain_max - domain_min
            tightness = domain_span - (maximum - minimum)
            extremity = abs(
                (minimum + maximum) - (domain_min + domain_max)
            )
            ranked.append(
                (
                    float(tightness),
                    float(extremity),
                    slider_priority.get(name, -1),
                    name,
                )
            )
        keep = {
            item[3]
            for item in sorted(ranked, reverse=True)[:4]
        }
        for _, _, _, name in ranked:
            if name not in keep:
                limited_sliders[name] = list(schema.numeric_ranges[name])
        limited["sliders"] = limited_sliders

    selectable_kept = False
    for field in ("tags", "genres", "instruments", "keys"):
        values = config.get(field)
        if not isinstance(values, list):
            continue
        if not selectable_kept and values:
            limited[field] = values[:1]
            selectable_kept = True
        else:
            limited[field] = []

    lowered = prompt.casefold()
    if not re.search(r"\b(?:bpm|tempo|темп\w*)\b", lowered):
        limited["bpm"] = None
    if not re.search(
        r"\b(?:length|duration|длитель\w*|сек(?:унд\w*)?|минут\w*)\b|\d+:\d{2}",
        lowered,
    ):
        limited["length"] = None
    return limited


def _contains_any(text: str, fragments: tuple[str, ...]) -> bool:
    return any(fragment in text for fragment in fragments)
