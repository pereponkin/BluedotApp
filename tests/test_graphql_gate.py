import json
import unittest

from bluedot_agent.graphql import PlaylistGraphQLGate


URL = "https://api.sessions.blue/graphql"


class FakeResponse:
    status = 200

    def __init__(self, body):
        self._body = body

    async def text(self):
        return self._body


class FakeRoute:
    def __init__(self, response_body='{"data":{"suggest":{"buckets":[1]}}}'):
        self.actions = []
        self.response_body = response_body

    async def continue_(self):
        self.actions.append(("continue", None))

    async def fulfill(self, **kwargs):
        self.actions.append(("fulfill", kwargs))

    async def fetch(self):
        self.actions.append(("fetch", None))
        return FakeResponse(self.response_body)


class FakeRequest:
    method = "POST"

    def __init__(self, filters, *, size=20, after=None, operation="suggest"):
        self.url = URL
        query = (
            "query Search($filters: [filterQuery]) { search(q: $q, filters: $filters) }"
            if operation == "search"
            else "query { suggest(q: $filters) }"
        )
        self.post_data = json.dumps(
            {
                "operationName": "Search" if operation == "search" else None,
                "variables": {"filters": filters, "size": size, "from": after},
                "query": query,
            }
        )


class PlaylistGraphQLGateTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events = []
        self.gate = PlaylistGraphQLGate(URL, ["Mood", "Energy"], self.events)

    async def test_blocks_until_enabled_and_until_all_expected_names_arrive(self):
        route = FakeRoute()
        await self.gate._handle(route, FakeRequest([]))
        self.assertEqual(route.actions[0][0], "fulfill")
        self.gate.allow_final()
        route = FakeRoute()
        await self.gate._handle(route, FakeRequest([{"filterName": "Mood", "min": 1, "max": 5}]))
        self.assertEqual(self.events[-1]["reason"], "incomplete_filters")

    async def test_exact_request_fetches_once_then_replays(self):
        self.gate.allow_final()
        filters = [
            {"filterName": "Mood", "min": 3, "max": 5},
            {"filterName": "Energy", "min": 1, "max": 2},
        ]
        first = FakeRoute()
        await self.gate._handle(first, FakeRequest(filters))
        second = FakeRoute()
        await self.gate._handle(second, FakeRequest(filters))
        self.assertEqual([action for action, _ in first.actions], ["fetch", "fulfill"])
        self.assertEqual([action for action, _ in second.actions], ["fulfill"])
        self.assertEqual(self.events[-1]["action"], "replay")

    async def test_same_count_with_changed_value_is_not_stale_replay(self):
        self.gate.allow_final()
        initial = [
            {"filterName": "Mood", "min": 3, "max": 5},
            {"filterName": "Energy", "min": 1, "max": 2},
        ]
        await self.gate._handle(FakeRoute(), FakeRequest(initial))
        changed = [dict(initial[0]), {"filterName": "Energy", "min": 4, "max": 5}]
        route = FakeRoute()
        await self.gate._handle(route, FakeRequest(changed))
        self.assertEqual(route.actions, [("continue", None)])

    async def test_pagination_has_a_distinct_cache_key(self):
        self.gate.allow_final()
        filters = [
            {"filterName": "Mood", "min": 3, "max": 5},
            {"filterName": "Energy", "min": 1, "max": 2},
        ]
        await self.gate._handle(FakeRoute(), FakeRequest(filters, after=None))
        second_page = FakeRoute()
        await self.gate._handle(second_page, FakeRequest(filters, after={"key": 2}))
        self.assertEqual(second_page.actions[0][0], "fetch")

    async def test_current_search_operation_is_gated_and_cached(self):
        self.gate.allow_final()
        filters = [
            {"filterName": "Mood", "min": 7, "max": 9},
            {"filterName": "Energy", "min": 2, "max": 7},
        ]
        first = FakeRoute()
        await self.gate._handle(first, FakeRequest(filters, operation="search"))
        second = FakeRoute()
        await self.gate._handle(second, FakeRequest(filters, operation="search"))
        self.assertEqual(first.actions[0][0], "fetch")
        self.assertEqual(second.actions[0][0], "fulfill")


if __name__ == "__main__":
    unittest.main()
