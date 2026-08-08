from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .schema import FilterSchema


class ProviderRequestError(RuntimeError):
    pass


class FilterInterpreterClient(Protocol):
    def parse_filters(
        self,
        prompt: str,
        schema: FilterSchema,
    ) -> dict[str, Any]: ...


Transport = Callable[[Request, float], bytes]


def _urlopen_transport(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def filter_interpretation_prompt(prompt: str, schema: FilterSchema) -> str:
    return (
        "Convert this music-search request into Blue Dot filter settings. "
        "Interpret meaning holistically rather than matching keywords. "
        "Infer musical characteristics from the described scene, era, "
        "emotion, pacing, attitude, and intended use. Slider axes are: "
        "Mood: dark/negative -> bright/positive; "
        "Density: sparse -> dense/layered; "
        "Energy: restrained/calm -> energetic/intense; "
        "Gravity: light/weightless -> heavy/serious; "
        "Ensemble: solo/small -> large/full; "
        "Melody: atmospheric/non-melodic -> strongly melodic; "
        "Tension: calm/relaxed -> tense/suspenseful; "
        "Rhythm: free/subtle pulse -> strong/driving pulse. "
        "Every slider uses 1 for the left endpoint and 5 for the right. "
        "The first number in every pair must not exceed the second. "
        "Interpret compositionally: emotion and attitude map to Tags, "
        "musical style maps to Genres, and explicitly requested timbres "
        "map to Instruments. "
        f"{schema.inventory_prompt()} Request: {prompt}"
    )


def compact_filter_interpretation_prompt(
    prompt: str,
    schema: FilterSchema,
) -> str:
    selectables = {
        group: sorted(values)
        for group, values in schema.selectable_values.items()
    }
    return (
        "Map music-search request to Blue Dot filters. "
        "Infer whole meaning, not keywords: scene, era, emotion, pace, attitude, "
        "intended use. Axes, 1 = left, 5 = right; min <= max: "
        "Mood: dark/negative - bright/positive; "
        "Density: sparse - dense/layered; "
        "Energy: restrained/calm - energetic/intense; "
        "Gravity: light/weightless - heavy/serious; "
        "Ensemble: solo/small - large/full; "
        "Melody: atmospheric/non-melodic - strongly melodic; "
        "Tension: calm/relaxed - tense/suspenseful; "
        "Rhythm: free/subtle pulse - strong/driving pulse. "
        "Meaning: Tags = emotion and attitude; Genres = musical style; "
        "Instruments = explicitly requested timbres. "
        f"Domains: {schema.numeric_ranges}. Allowed values: {selectables}. "
        "Use listed values only. Default to broad numeric ranges and empty selectable "
        "lists. Narrow or add values only when wording clearly requires them. "
        "Selectable values combine with AND. Use minimum needed. Never encode same "
        "idea across groups. Normally choose no more than one selectable value total. "
        "Use two groups only for independent explicit facts, e.g. Classical + Strings. "
        "Collections are navigation contexts, not track filters. Never return them. "
        f"Request: {prompt}."
    )


def _groq_filter_interpretation_prompt(
    prompt: str,
    schema: FilterSchema,
) -> str:
    return (
        compact_filter_interpretation_prompt(prompt, schema)
        + " Groq only: Return numeric ranges as integer objects, "
        'e.g. "Energy":{"min":4,"max":5}. Narrow only 2-4 decisive slider axes. '
        'Set every other slider to {"min":1,"max":5}. Target small useful result '
        "set, not zero matches."
    )


def _mistral_filter_interpretation_prompt(
    prompt: str,
    schema: FilterSchema,
) -> str:
    return (
        compact_filter_interpretation_prompt(prompt, schema)
        + " Mistral: 2-4 decisive axes only. Other axes: [1,5]. "
        "One selectable value total. Other lists empty. "
        "BPM/Length null unless explicitly requested. Broad useful results."
    )


_OPENAI_ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "mistral": "https://api.mistral.ai/v1/chat/completions",
}

_USER_AGENT = "BlueDotAgent/0.2"


class OpenAICompatibleClient:
    def __init__(
        self,
        provider: str,
        api_key: str,
        *,
        model: str,
        timeout: float = 20.0,
        transport: Transport = _urlopen_transport,
    ) -> None:
        if provider not in _OPENAI_ENDPOINTS:
            raise ValueError(f"Unsupported OpenAI-compatible provider: {provider}")
        if not api_key.strip():
            raise ValueError("API key cannot be empty")
        if not model.strip():
            raise ValueError("Model cannot be empty")
        self._provider = provider
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._transport = transport

    def parse_filters(
        self,
        prompt: str,
        schema: FilterSchema,
    ) -> dict[str, Any]:
        response_schema = schema.json_schema()
        prompt_text = filter_interpretation_prompt(prompt, schema)
        if self._provider == "groq":
            response_schema = _groq_response_schema(response_schema)
            prompt_text = _groq_filter_interpretation_prompt(prompt, schema)
        elif self._provider == "mistral":
            prompt_text = _mistral_filter_interpretation_prompt(prompt, schema)
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt_text,
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "bluedot_filters",
                    "strict": True,
                    "schema": response_schema,
                },
            },
        }
        request = Request(
            _OPENAI_ENDPOINTS[self._provider],
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": _USER_AGENT,
            },
            method="POST",
        )
        try:
            raw_response = self._transport(request, self._timeout)
        except HTTPError as error:
            raise ProviderRequestError(
                f"{self._provider} HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise ProviderRequestError(
                f"{self._provider} request failed"
            ) from error

        try:
            response = json.loads(raw_response.decode("utf-8"))
            content = response["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
        ) as error:
            raise ProviderRequestError(
                f"{self._provider} returned an invalid structured response"
            ) from error
        if not isinstance(parsed, dict):
            raise ProviderRequestError(
                f"{self._provider} filter response is not an object"
            )
        if self._provider == "groq":
            return _decode_groq_ranges(parsed)
        return parsed


def create_client(
    provider: str,
    api_key: str,
    model: str,
) -> FilterInterpreterClient:
    if provider == "gemini":
        from .gemini import GeminiClient

        return GeminiClient(api_key, model=model)
    return OpenAICompatibleClient(provider, api_key, model=model)


def _groq_response_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Keep range bounds separate for Groq's GPT-OSS structured output."""

    compatible = deepcopy(schema)

    def replace_range_arrays(value: Any) -> None:
        if isinstance(value, dict):
            item_schema = value.get("items")
            if (
                value.get("type") == "array"
                and isinstance(item_schema, dict)
                and item_schema.get("type") == "string"
            ):
                value["maxItems"] = 1
            prefix_items = value.get("prefixItems")
            if (
                isinstance(prefix_items, list)
                and len(prefix_items) == 2
                and prefix_items[0] == prefix_items[1]
            ):
                item_schema = prefix_items[0]
                value.clear()
                value.update(
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "min": deepcopy(item_schema),
                            "max": deepcopy(item_schema),
                        },
                        "required": ["min", "max"],
                    }
                )
                return
            for child in value.values():
                replace_range_arrays(child)
        elif isinstance(value, list):
            for child in value:
                replace_range_arrays(child)

    replace_range_arrays(compatible)
    return compatible


def _decode_groq_ranges(config: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(config)
    sliders = decoded.get("sliders")
    if isinstance(sliders, dict):
        decoded["sliders"] = {
            name: _decode_named_range(value)
            for name, value in sliders.items()
        }
    for name in ("bpm", "length"):
        decoded[name] = _decode_named_range(decoded.get(name))
    return decoded


def _decode_named_range(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"min", "max"}:
        return [value["min"], value["max"]]
    return value
