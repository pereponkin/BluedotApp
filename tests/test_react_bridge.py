import unittest

from bluedot_agent.react_bridge import (
    ADD_SELECTABLE_FILTER_JS,
    APPLY_SEARCH_FILTERS_JS,
    FIND_SEARCH_PROVIDER_JS,
    READ_SEARCH_STATE_JS,
    READ_SLIDER_VALUES_JS,
    SET_CHARACTERISTIC_RANGE_JS,
    apply_search_filters,
    wait_for_filters,
    wait_for_stable_results,
)


class SequenceReader:
    def __init__(self, states):
        self.states = list(states)
        self.index = 0

    async def __call__(self, page):
        state = self.states[min(self.index, len(self.states) - 1)]
        self.index += 1
        return state


async def _result(value):
    return value


class ReactBridgeTest(unittest.IsolatedAsyncioTestCase):
    def test_all_bridge_operations_share_one_provider_finder(self):
        for script in (
            READ_SEARCH_STATE_JS,
            APPLY_SEARCH_FILTERS_JS,
            ADD_SELECTABLE_FILTER_JS,
            SET_CHARACTERISTIC_RANGE_JS,
            READ_SLIDER_VALUES_JS,
        ):
            with self.subTest(script=script[:30]):
                self.assertIn(FIND_SEARCH_PROVIDER_JS.strip(), script)

    async def test_apply_filters_reports_missing_provider(self):
        page = type(
            "Page",
            (),
            {"evaluate": lambda self, script, payload: _result({"ok": False, "reason": "missing"})},
        )()

        with self.assertRaisesRegex(RuntimeError, "missing"):
            await apply_search_filters(page, [], [])

    async def test_wait_for_filters_requires_exact_values(self):
        wrong = {"filters": [{"filterName": "Mood", "filterType": "range", "min": 1, "max": 5}]}
        right = {"filters": [{"filterName": "Mood", "filterType": "range", "min": 3, "max": 5}]}
        result = await wait_for_filters(
            None,
            right["filters"],
            timeout=1,
            reader=SequenceReader([wrong, right]),
        )
        self.assertEqual(result, right)

    async def test_wait_for_stable_results_resets_while_loading_or_changing(self):
        loading = {"loadingTracks": True, "loadingMore": False, "firstTracks": []}
        a = {"loadingTracks": False, "loadingMore": False, "firstTracks": [{"title": "A"}]}
        b = {"loadingTracks": False, "loadingMore": False, "firstTracks": [{"title": "B"}]}
        reader = SequenceReader([loading, a, b, b, b])
        result = await wait_for_stable_results(
            None, timeout=1, stable_samples=3, interval=0, reader=reader
        )
        self.assertEqual(result["firstTracks"][0]["title"], "B")


if __name__ == "__main__":
    unittest.main()
