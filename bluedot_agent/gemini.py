from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .llm import ProviderRequestError, compact_filter_interpretation_prompt
from .schema import FilterSchema


class GeminiError(ProviderRequestError):
    pass


Transport = Callable[[Request, float], bytes]


def _urlopen_transport(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:
        return response.read()


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-3.5-flash",
        timeout: float = 20.0,
        transport: Transport = _urlopen_transport,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Gemini API key cannot be empty")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._transport = transport

    def parse_filters(self, prompt: str, schema: FilterSchema) -> dict[str, Any]:
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": compact_filter_interpretation_prompt(prompt, schema)
                        }
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _gemini_response_schema(schema),
            },
        }
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self._api_key,
            },
            method="POST",
        )
        try:
            raw_response = self._transport(request, self._timeout)
        except HTTPError as error:
            raise GeminiError(f"Gemini HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise GeminiError(f"Gemini request failed: {error}") from error

        try:
            response = json.loads(raw_response.decode("utf-8"))
            parts = response["candidates"][0]["content"]["parts"]
            text = "".join(str(part.get("text", "")) for part in parts)
            parsed = json.loads(text)
        except (KeyError, IndexError, TypeError, ValueError, UnicodeDecodeError) as error:
            raise GeminiError("Gemini returned an invalid structured response") from error
        if not isinstance(parsed, dict):
            raise GeminiError("Gemini filter response is not an object")
        return parsed


def _gemini_response_schema(schema: FilterSchema) -> dict[str, Any]:
    """Avoid Gemini's hidden complexity limit for large enum inventories.

    The full allowed inventory remains in the prompt, and FilterSchema validates
    every returned value locally before any filter reaches Blue Dot.
    """

    compact = deepcopy(schema.json_schema())

    def strip_large_hints(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("description", None)
            value.pop("enum", None)
            for child in value.values():
                strip_large_hints(child)
        elif isinstance(value, list):
            for child in value:
                strip_large_hints(child)

    strip_large_hints(compact)
    return compact
