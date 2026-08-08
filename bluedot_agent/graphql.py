from __future__ import annotations

import asyncio
import json
from collections import Counter
from typing import Any


class PlaylistGraphQLGate:
    def __init__(
        self,
        graphql_url: str,
        expected_filter_names: list[str],
        events: list[dict[str, Any]] | None = None,
    ) -> None:
        self._graphql_url = graphql_url
        self._expected_names = Counter(name.casefold() for name in expected_filter_names)
        self._events = events
        self._enabled = False
        self._filter_signature: str | None = None
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def install(self, page: Any) -> "PlaylistGraphQLGate":
        await page.route(self._graphql_url, self._handle)
        return self

    def allow_final(self) -> None:
        self._enabled = True

    async def _handle(self, route: Any, request: Any) -> None:
        post_data = request.post_data or ""
        operation = _playlist_operation(request.url, post_data, self._graphql_url)
        if operation is None:
            if request.url == self._graphql_url and request.method.upper() == "POST":
                try:
                    observed = json.loads(post_data)
                except (TypeError, ValueError):
                    observed = {}
                variables = observed.get("variables", {}) if isinstance(observed, dict) else {}
                filters = variables.get("filters") or [] if isinstance(variables, dict) else []
                self._record(
                    "continue",
                    "other",
                    filters,
                    operationName=observed.get("operationName") if isinstance(observed, dict) else None,
                    queryPreview=str(observed.get("query", ""))[:300] if isinstance(observed, dict) else "",
                )
            await route.continue_()
            return
        try:
            payload = json.loads(post_data)
            variables = payload.get("variables", {})
            filters = variables.get("filters") or []
        except (TypeError, ValueError, AttributeError):
            await route.continue_()
            return

        names = Counter(str(item.get("filterName", "")).casefold() for item in filters)
        if not self._enabled:
            await self._block(route, operation, filters, "not_ready")
            return

        signature = _canonical_json(filters)
        if self._filter_signature is None:
            if names != self._expected_names:
                await self._block(route, operation, filters, "incomplete_filters")
                return
            self._filter_signature = signature
        elif signature != self._filter_signature:
            self._record("continue", operation, filters, reason="manual_filter_change")
            await route.continue_()
            return

        cache_key = f"{operation}:{_canonical_json(payload)}"
        async with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._record("replay", operation, filters, cacheKey=cache_key)
                await route.fulfill(
                    status=cached["status"],
                    content_type="application/json",
                    body=cached["body"],
                )
                return

            self._record("fetch", operation, filters, cacheKey=cache_key)
            response = await route.fetch()
            body = await response.text()
            self._cache[cache_key] = {"status": response.status, "body": body}
            await route.fulfill(
                status=response.status,
                content_type="application/json",
                body=body,
            )

    async def _block(
        self,
        route: Any,
        operation: str,
        filters: list[dict[str, Any]],
        reason: str,
    ) -> None:
        self._record("block", operation, filters, reason=reason)
        field = "suggest" if operation == "suggest" else "filter"
        if operation == "search":
            body = {
                "data": {
                    "search": {
                        "exact": [],
                        "suggested": [],
                        "isFallback": False,
                        "exactHasMore": False,
                        "suggestedHasMore": False,
                    }
                }
            }
        else:
            body = {"data": {field: {"buckets": [], "after_key": None}}}
        await route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body),
        )

    def _record(
        self,
        action: str,
        operation: str,
        filters: list[dict[str, Any]],
        **details: Any,
    ) -> None:
        if self._events is not None:
            self._events.append(
                {
                    "kind": "playlist_graphql_gate",
                    "action": action,
                    "operation": operation,
                    "filterCount": len(filters),
                    **details,
                }
            )


def _playlist_operation(url: str, post_data: str, graphql_url: str) -> str | None:
    if url != graphql_url:
        return None
    if "suggest(q:" in post_data:
        return "suggest"
    if "filter(q:" in post_data:
        return "filter"
    try:
        payload = json.loads(post_data)
    except (TypeError, ValueError):
        payload = {}
    if payload.get("operationName") == "Search" or "search(q:" in str(payload.get("query", "")):
        return "search"
    return None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
