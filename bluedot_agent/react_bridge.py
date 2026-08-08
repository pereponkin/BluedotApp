from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any


CHARACTERISTIC_SCALE = {1: 0, 2: 2, 3: 5, 4: 7, 5: 9}

FIND_SEARCH_PROVIDER_JS = """
function findSearchProvider({ arrays = [], functions = [] } = {}) {
  // Blue Dot mounts with the legacy ReactDOM.render, which parks the root on
  // _reactRootContainer. React 18+ with createRoot hides it on the container as
  // __reactContainer$<build id>, and host nodes carry __reactFiber$<build id>.
  // All three are tried so an upgrade on their side does not silence the agent.
  const collectRoots = (node) => {
    const found = new Set();
    if (!node) return found;
    const legacy = node._reactRootContainer;
    const internal = legacy && (legacy._internalRoot || legacy);
    if (internal && internal.current) found.add(internal.current);
    for (const key of Object.keys(node)) {
      if (!key.startsWith("__reactContainer$") && !key.startsWith("__reactFiber$")) continue;
      let fiber = node[key];
      if (!fiber) continue;
      if (key.startsWith("__reactFiber$")) {
        while (fiber.return && fiber.return !== fiber) fiber = fiber.return;
      }
      found.add(fiber);
    }
    return found;
  };
  const containers = new Set([document.getElementById("root"), document.body]);
  if (document.body) document.body.querySelectorAll(":scope > *").forEach((node) => containers.add(node));
  const roots = new Set();
  for (const container of containers) {
    for (const root of collectRoots(container)) roots.add(root);
  }
  const seen = new Set();
  const stack = [...roots].filter(Boolean);
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
        arrays.every((name) => Array.isArray(value[name])) &&
        functions.every((name) => typeof value[name] === "function")
      ) {
        return value;
      }
    }
    if (fiber.child) stack.push(fiber.child);
    if (fiber.sibling) stack.push(fiber.sibling);
  }
  return null;
}
"""

READ_SEARCH_STATE_JS = """
() => {
  __FIND_SEARCH_PROVIDER__
  const value = findSearchProvider({ arrays: ["allTracks"] });
  if (!value) return null;
  const tracks = Array.isArray(value.allTracks) ? value.allTracks : [];
  return {
    filters: value.searchFilters.map((item) => ({
      filterName: item.filterName,
      filterValue: item.filterValue,
      filterType: item.filterType,
      min: item.min,
      max: item.max
    })),
    loadingTracks: Boolean(value.loadingTracks),
    loadingMore: Boolean(value.loadingMore),
    allTracksLength: tracks.length,
    exactTracksLength: Array.isArray(value.exactTracks) ? value.exactTracks.length : null,
    suggestedTracksLength: Array.isArray(value.suggestedTracks) ? value.suggestedTracks.length : null,
    firstTracks: tracks.slice(0, 12).map((item) => ({
      title: item.title || item.name || null,
      albumName: item.albumName || (item.album && item.album.name) || item.album || null
    }))
  };
}
""".replace("__FIND_SEARCH_PROVIDER__", FIND_SEARCH_PROVIDER_JS)

APPLY_SEARCH_FILTERS_JS = """
({ rangeFilters, selectableFilters }) => {
  __FIND_SEARCH_PROVIDER__
  const provider = findSearchProvider({
    arrays: ["allCharacteristics"],
    functions: ["setFilters"]
  });
  if (!provider) {
    return { ok: false, reason: "search_provider_not_found" };
  }
  const filters = [];
  const characteristicScale = {1: 0, 2: 2, 3: 5, 4: 7, 5: 9};
  for (const item of rangeFilters) {
    // The characteristic objects are written in place on purpose. Blue Dot draws
    // its sliders from allCharacteristics and read_slider_values checks the same
    // objects, so this is what makes the page and the applied/missing summary
    // agree. Going through provider.onCharChange instead would fire one search
    // per slider, which is exactly what the GraphQL gate exists to prevent.
    if (item.characteristic) {
      const characteristic = (provider.allCharacteristics || []).find((candidate) =>
        candidate &&
        String(candidate.filterName).toLowerCase() === String(item.filterName).toLowerCase()
      );
      if (characteristic) {
        characteristic.min = item.min;
        characteristic.max = item.max;
      }
    }
    filters.push({
      filterType: "range",
      filterName: item.filterName,
      min: item.characteristic ? characteristicScale[item.min] : item.min,
      max: item.characteristic ? characteristicScale[item.max] : item.max
    });
  }
  for (const item of selectableFilters) {
    filters.push({
      filterType: "selectable",
      filterName: item.filterName,
      filterValue: item.filterValue
    });
  }
  provider.setFilters(filters);
  return { ok: true, filters };
}
""".replace("__FIND_SEARCH_PROVIDER__", FIND_SEARCH_PROVIDER_JS)

ADD_SELECTABLE_FILTER_JS = """
async ({ filterName, filterValue }) => {
  __FIND_SEARCH_PROVIDER__
  const provider = findSearchProvider({ functions: ["addSelectable"] });
  if (!provider) {
    return { ok: false, reason: "search_provider_not_found" };
  }
  const alreadySelected = provider.searchFilters.some((item) =>
    item &&
    item.filterType === "selectable" &&
    String(item.filterName).toLowerCase() === String(filterName).toLowerCase() &&
    String(item.filterValue).toLowerCase() === String(filterValue).toLowerCase()
  );
  if (!alreadySelected) {
    provider.addSelectable(filterValue, filterName);
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return { ok: true, requested: { filterName, filterValue } };
}
""".replace("__FIND_SEARCH_PROVIDER__", FIND_SEARCH_PROVIDER_JS)

SET_CHARACTERISTIC_RANGE_JS = """
async ({ name, valueRange }) => {
  __FIND_SEARCH_PROVIDER__
  const provider = findSearchProvider({
    arrays: ["allCharacteristics"],
    functions: ["onCharChange"]
  });
  if (!provider) {
    return { ok: false, reason: "search_provider_not_found" };
  }
  const characteristic = (provider.allCharacteristics || []).find((item) =>
    item && item.filterName && item.filterName.toLowerCase() === name.toLowerCase()
  );
  if (!characteristic) {
    return {
      ok: false,
      reason: "characteristic_not_found",
      available: (provider.allCharacteristics || []).map((item) => item && item.filterName).filter(Boolean)
    };
  }
  provider.onCharChange(characteristic, valueRange);
  await new Promise((resolve) => setTimeout(resolve, 50));
  return { ok: true, requested: { name, valueRange } };
}
""".replace("__FIND_SEARCH_PROVIDER__", FIND_SEARCH_PROVIDER_JS)

READ_SLIDER_VALUES_JS = """
(labels) => {
  __FIND_SEARCH_PROVIDER__
  const provider = findSearchProvider({ arrays: ["allCharacteristics"] });
  if (!provider) return {};
  const labelSet = new Set(labels.map((label) => String(label).toLowerCase()));
  const values = {};
  for (const item of provider.allCharacteristics || []) {
    if (!item || !item.filterName) continue;
    const name = String(item.filterName);
    if (!labelSet.has(name.toLowerCase())) continue;
    values[name] = [Number(item.min), Number(item.max)];
  }
  for (const item of provider.searchFilters || []) {
    if (!item || item.filterType !== "range" || !item.filterName) continue;
    const name = String(item.filterName).toLowerCase();
    if (name === "bpm" && labelSet.has("bpm")) {
      values.BPM = [Number(item.min), Number(item.max)];
    }
    if ((name === "duration" || name === "length") && labelSet.has("length")) {
      values.Length = [Number(item.min), Number(item.max)];
    }
  }
  return values;
}
""".replace("__FIND_SEARCH_PROVIDER__", FIND_SEARCH_PROVIDER_JS)


async def read_search_state(page: Any) -> dict[str, Any] | None:
    return await page.evaluate(READ_SEARCH_STATE_JS)


async def apply_search_filters(
    page: Any,
    range_filters: list[dict[str, Any]],
    selectable_filters: list[dict[str, str]],
) -> dict[str, Any]:
    result = await page.evaluate(
        APPLY_SEARCH_FILTERS_JS,
        {"rangeFilters": range_filters, "selectableFilters": selectable_filters},
    )
    if not result.get("ok"):
        raise RuntimeError(
            f"Blue Dot React search provider rejected filters: {result.get('reason', 'unknown')}"
        )
    return result


async def add_selectable_filter(page: Any, filter_name: str, filter_value: str) -> dict[str, Any]:
    return await page.evaluate(
        ADD_SELECTABLE_FILTER_JS,
        {"filterName": filter_name, "filterValue": filter_value},
    )


async def set_characteristic_range(
    page: Any,
    name: str,
    value_range: tuple[int, int],
) -> dict[str, Any]:
    return await page.evaluate(
        SET_CHARACTERISTIC_RANGE_JS,
        {"name": name, "valueRange": list(value_range)},
    )


async def read_slider_values(page: Any, labels: list[str]) -> dict[str, list[int]]:
    return await page.evaluate(READ_SLIDER_VALUES_JS, labels)


async def wait_for_provider(
    page: Any,
    *,
    timeout: float = 30.0,
    reader: Callable[[Any], Awaitable[dict[str, Any] | None]] = read_search_state,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        state = await reader(page)
        if state is not None:
            return state
        await asyncio.sleep(0.1)
    raise RuntimeError("Blue Dot React search provider did not become ready")


async def wait_for_filters(
    page: Any,
    expected_filters: list[dict[str, Any]],
    *,
    timeout: float = 10.0,
    reader: Callable[[Any], Awaitable[dict[str, Any] | None]] = read_search_state,
) -> dict[str, Any]:
    expected = _filter_signature(expected_filters)
    deadline = asyncio.get_running_loop().time() + timeout
    last: dict[str, Any] | None = None
    while asyncio.get_running_loop().time() < deadline:
        state = await reader(page)
        if state is not None:
            last = state
            if _filter_signature(state.get("filters") or []) == expected:
                return state
        await asyncio.sleep(0.1)
    raise RuntimeError(
        "Blue Dot did not apply the requested filters. "
        f"Expected {expected}; observed {_filter_signature((last or {}).get('filters') or [])}"
    )


async def wait_for_stable_results(
    page: Any,
    *,
    timeout: float = 30.0,
    stable_samples: int = 3,
    interval: float = 0.5,
    reader: Callable[[Any], Awaitable[dict[str, Any] | None]] = read_search_state,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout
    previous: str | None = None
    stable_count = 0
    last: dict[str, Any] | None = None
    while asyncio.get_running_loop().time() < deadline:
        state = await reader(page)
        if state is not None:
            last = state
            if not state.get("loadingTracks") and not state.get("loadingMore"):
                fingerprint = result_fingerprint(state)
                stable_count = stable_count + 1 if fingerprint == previous else 1
                previous = fingerprint
                if stable_count >= stable_samples:
                    return state
            else:
                previous = None
                stable_count = 0
        await asyncio.sleep(interval)
    raise RuntimeError(f"Blue Dot results did not stabilize; last state: {last}")


def result_fingerprint(state: dict[str, Any]) -> str:
    relevant = {
        "filters": state.get("filters") or [],
        "allTracksLength": state.get("allTracksLength"),
        "exactTracksLength": state.get("exactTracksLength"),
        "suggestedTracksLength": state.get("suggestedTracksLength"),
        "firstTracks": state.get("firstTracks") or [],
    }
    return json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _filter_signature(filters: list[dict[str, Any]]) -> str:
    normalized = [
        {
            "filterName": str(item.get("filterName", "")).casefold(),
            "filterValue": item.get("filterValue"),
            "filterType": item.get("filterType"),
            "min": item.get("min"),
            "max": item.get("max"),
        }
        for item in filters
    ]
    return json.dumps(
        sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
