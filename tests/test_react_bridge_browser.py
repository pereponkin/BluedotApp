import unittest

from playwright.async_api import async_playwright

from bluedot_agent.react_bridge import FIND_SEARCH_PROVIDER_JS


PAGE_HTML = """
<html><body><div id="root"><main>Blue Dot</main></div></body></html>
"""

# Мини-дерево fiber: HostRoot -> провайдер контекста с нужным value.
BUILD_TREE_JS = """
() => {
  const value = {
    searchFilters: [],
    allCharacteristics: [{ filterName: "Mood", min: 1, max: 5 }],
    setFilters: () => {}
  };
  const host = { memoizedProps: {}, child: null, sibling: null, return: null };
  const provider = { memoizedProps: { value }, child: host, sibling: null, return: null };
  const spacer = { memoizedProps: {}, child: provider, sibling: null };
  const root = { memoizedProps: {}, child: spacer, sibling: null };
  host.return = provider;
  provider.return = spacer;
  spacer.return = root;
  return { current: root, host };
}
"""

FIND_JS = (
    "() => {\n"
    + FIND_SEARCH_PROVIDER_JS
    + "\n  const value = findSearchProvider({"
    ' arrays: ["allCharacteristics"], functions: ["setFilters"] });\n'
    "  return value ? value.allCharacteristics[0].filterName : null;\n"
    "}"
)


class ReactRootLookupTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.firefox.launch(headless=True)
        self.page = await self.browser.new_page()
        await self.page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=PAGE_HTML,
            ),
        )
        await self.page.goto("https://app.sessions.blue/browse")

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()

    async def test_legacy_render_root_is_found(self):
        await self.page.evaluate(
            "() => { document.getElementById('root')._reactRootContainer ="
            f" {{ _internalRoot: ({BUILD_TREE_JS})() }}; }}"
        )

        self.assertEqual(await self.page.evaluate(FIND_JS), "Mood")

    async def test_create_root_container_is_found(self):
        await self.page.evaluate(
            "() => { document.getElementById('root')['__reactContainer$abc123'] ="
            f" ({BUILD_TREE_JS})().current; }}"
        )

        self.assertEqual(await self.page.evaluate(FIND_JS), "Mood")

    async def test_host_fiber_on_a_body_child_is_found(self):
        await self.page.evaluate(
            "() => { document.body.children[0]['__reactFiber$abc123'] ="
            f" ({BUILD_TREE_JS})().host; }}"
        )

        self.assertEqual(await self.page.evaluate(FIND_JS), "Mood")

    async def test_missing_react_reports_nothing_instead_of_throwing(self):
        self.assertIsNone(await self.page.evaluate(FIND_JS))


if __name__ == "__main__":
    unittest.main()
