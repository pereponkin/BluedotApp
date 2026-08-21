import asyncio
import os
import unittest

from playwright.async_api import async_playwright

from bluedot_agent.panel import install_panel


TEST_APP_HTML = """
<html>
  <head>
    <style>
      html, body { margin: 0; height: 100%; }
      #root { min-height: 100vh; }
      main { padding: 24px; }
      .filters { height: 48px; }
      .card { height: 180px; }
      .player { position: fixed; inset: auto 0 0; height: 72px; }
    </style>
  </head>
  <body>
    <div id="root">
      <main>
        <section class="filters">Filters</section>
        <article class="card">Track</article>
      </main>
      <footer class="player">Player</footer>
    </div>
  </body>
</html>
"""

PUBLIC_SETTINGS = {
    "browser": "firefox",
    "selected_provider": "gemini",
    "download_directory": r"D:\Downloads",
    "providers": {
        "gemini": {
            "id": "gemini",
            "label": "Google AI Studio (Gemini)",
            "model": "gemini-3.5-flash-lite",
            "recommended_models": [
                "gemini-3.5-flash-lite",
                "gemini-3.5-flash",
            ],
            "has_api_key": True,
        },
        "groq": {
            "id": "groq",
            "label": "Groq",
            "model": "openai/gpt-oss-120b",
            "recommended_models": [
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
            ],
            "has_api_key": False,
        },
        "openrouter": {
            "id": "openrouter",
            "label": "OpenRouter",
            "model": "openai/gpt-oss-20b:free",
            "recommended_models": ["openai/gpt-oss-20b:free"],
            "has_api_key": False,
        },
        "mistral": {
            "id": "mistral",
            "label": "Mistral",
            "model": "mistral-small-latest",
            "recommended_models": ["mistral-small-latest"],
            "has_api_key": False,
        },
    },
}


class PanelBrowserTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        browser_name = os.environ.get("BLUEDOT_TEST_BROWSER", "firefox")
        browser_type = getattr(self.playwright, browser_name)
        self.browser = await browser_type.launch(headless=True)

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()

    async def test_panel_mounts_only_on_bluedot_and_collapses_page(self):
        async def handler(source, command):
            return {"ok": False, "error": "unused"}

        page = await self.browser.new_page(viewport={"width": 1280, "height": 900})
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=TEST_APP_HTML,
            ),
        )
        await page.goto("https://app.sessions.blue/browse")

        host = page.locator("#bluedot-agent-panel")
        self.assertEqual(await host.count(), 1)
        self.assertTrue(await host.evaluate("(node) => Boolean(node.shadowRoot)"))
        expanded = await page.locator("#root").bounding_box()
        self.assertEqual(round(expanded["x"]), 340)
        self.assertEqual(round(expanded["width"]), 940)
        for selector in (".filters", ".card", ".player"):
            box = await page.locator(selector).bounding_box()
            self.assertGreaterEqual(round(box["x"]), 340)
            self.assertLessEqual(round(box["x"] + box["width"]), 1280)
        player = await page.locator(".player").bounding_box()
        self.assertEqual(round(player["y"] + player["height"]), 900)

        toggle = host.locator("button[data-role=toggle]")
        await toggle.click()

        self.assertEqual(await toggle.get_attribute("aria-expanded"), "false")
        collapsed = await page.locator("#root").bounding_box()
        self.assertEqual(round(collapsed["x"]), 44)
        self.assertEqual(round(collapsed["width"]), 1236)
        player = await page.locator(".player").bounding_box()
        self.assertGreaterEqual(round(player["x"]), 44)
        self.assertEqual(round(player["y"] + player["height"]), 900)

        await toggle.click()
        await page.set_viewport_size({"width": 1720, "height": 1000})
        wide = await page.locator("#root").bounding_box()
        self.assertEqual(round(wide["x"]), 340)
        self.assertEqual(round(wide["width"]), 1380)
        player = await page.locator(".player").bounding_box()
        self.assertLessEqual(round(player["x"] + player["width"]), 1720)
        self.assertEqual(round(player["y"] + player["height"]), 1000)

        other = await self.browser.new_page()
        await install_panel(other, handler)
        await other.route(
            "https://example.com/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="<html><body>Other</body></html>",
            ),
        )
        await other.goto("https://example.com/")

        self.assertEqual(await other.locator("#bluedot-agent-panel").count(), 0)

    async def test_empty_result_sections_stay_hidden(self):
        async def handler(source, command):
            if command["type"] == "get_settings":
                return {"ok": True, "settings": PUBLIC_SETTINGS}
            return {
                "ok": True,
                "prompt": command["prompt"],
                "parser": "gemini",
                "warning": None,
                "applied_sliders": {"Mood": [3, 5]} if command["prompt"] == "полный" else {},
                "categories": {"Tags": ["Peaceful"]} if command["prompt"] == "полный" else {},
                "missing_sliders": {},
                "exact_count": 0,
                "has_related": False,
            }

        page = await self.browser.new_page()
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=TEST_APP_HTML,
            ),
        )
        await page.goto("https://app.sessions.blue/browse")

        host = page.locator("#bluedot-agent-panel")
        status = host.locator("[data-role=status]")
        sliders = host.locator("[data-role=sliders-section]")
        categories = host.locator("[data-role=categories-section]")
        missing = host.locator("[data-role=missing-section]")

        await host.locator("[data-role=query]").fill("пусто")
        await host.locator("[data-role=search]").click()
        await status.get_by_text("Готово.").wait_for()

        self.assertTrue(await host.locator("[data-role=result]").is_visible())
        self.assertFalse(await sliders.is_visible())
        self.assertFalse(await categories.is_visible())
        self.assertFalse(await missing.is_visible())

        await host.locator("[data-role=query]").fill("полный")
        await host.locator("[data-role=search]").click()
        await sliders.wait_for(state="visible")

        self.assertTrue(await categories.is_visible())
        self.assertFalse(await missing.is_visible())
        self.assertIn("Mood", await sliders.text_content())

    async def test_panel_announces_through_one_region_and_starts_at_h1(self):
        async def handler(source, command):
            if command["type"] == "get_settings":
                return {"ok": True, "settings": PUBLIC_SETTINGS}
            return {"ok": False, "error": "unused"}

        page = await self.browser.new_page()
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=TEST_APP_HTML,
            ),
        )
        await page.goto("https://app.sessions.blue/browse")

        host = page.locator("#bluedot-agent-panel")

        self.assertEqual(
            await host.evaluate(
                """(node) => [...node.shadowRoot.querySelectorAll("aside :is(h1, h2, h3)")]
                    .map((item) => item.tagName)"""
            ),
            ["H1", "H2", "H2", "H2", "H2"],
        )
        self.assertEqual(
            await host.locator("aside h1").text_content(),
            "Blue Dot Agent",
        )

        live = await host.evaluate(
            """(node) => [...node.shadowRoot.querySelectorAll("aside [aria-live], aside [role=status]")]
                .map((item) => item.dataset.role)"""
        )
        self.assertEqual(live, ["status"])

        settings_toggle = host.locator("[data-role=settings-toggle]")
        self.assertEqual(
            await settings_toggle.get_attribute("aria-controls"),
            "bluedot-agent-settings",
        )
        self.assertEqual(
            await host.locator("[data-role=settings]").get_attribute("id"),
            "bluedot-agent-settings",
        )

    async def test_download_status_event_is_visible_in_panel(self):
        commands = []

        async def handler(source, command):
            commands.append(command)
            return {"ok": True}

        page = await self.browser.new_page()
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=TEST_APP_HTML,
            ),
        )
        await page.goto("https://app.sessions.blue/browse")
        status = page.locator("#bluedot-agent-panel").locator("[data-role=status]")
        commands.clear()

        await page.evaluate(
            """() => window.dispatchEvent(new CustomEvent(
                "bluedot-agent-download-status",
                { detail: {
                    kind: "success",
                    text: "Скачано: Morning Bells.wav",
                    can_open: true
                } }
            ))"""
        )

        self.assertEqual(await status.text_content(), "Скачано: Morning Bells.wav")
        self.assertEqual(await status.get_attribute("data-kind"), "success")
        self.assertIsNotNone(await status.get_attribute("data-can-open"))
        await status.click()
        self.assertEqual(commands, [{"type": "open_download"}])

    async def test_help_button_opens_in_page_overlay_without_leaving_the_browser(self):
        commands = []

        async def handler(source, command):
            if command["type"] == "get_settings":
                return {"ok": True, "settings": PUBLIC_SETTINGS}
            commands.append(command)
            return {"ok": True}

        page = await self.browser.new_page(viewport={"width": 1280, "height": 900})
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=TEST_APP_HTML,
            ),
        )
        await page.goto("https://app.sessions.blue/browse")

        host = page.locator("#bluedot-agent-panel")
        help_button = host.locator("[data-role=help-toggle]")
        overlay = host.locator("[data-role=help]")
        self.assertTrue(await help_button.is_visible())
        self.assertEqual(await help_button.text_content(), "?")
        self.assertEqual(
            await help_button.get_attribute("aria-label"),
            "Справка о Blue Dot Agent",
        )
        self.assertFalse(await overlay.is_visible())

        await help_button.click()

        self.assertTrue(await overlay.is_visible())
        self.assertEqual(await help_button.get_attribute("aria-expanded"), "true")
        self.assertEqual(await host.locator("[data-role=help-title]").text_content(), "Blue Dot Agent")
        tabs = host.locator("[data-role=help-tabs] button")
        self.assertEqual(
            await tabs.all_text_contents(),
            ["О проекте", "Установка", "Использование", "ИИ и данные"],
        )
        panels = host.locator("[data-role=help-body] [role=tabpanel]")
        self.assertEqual(await panels.count(), 4)
        self.assertTrue(await panels.nth(0).is_visible())
        self.assertFalse(await panels.nth(1).is_visible())
        self.assertIn(
            "локальный ИИ-помощник",
            await panels.nth(0).text_content(),
        )

        await tabs.nth(1).click()
        self.assertFalse(await panels.nth(0).is_visible())
        self.assertTrue(await panels.nth(1).is_visible())
        link = panels.nth(1).locator("a.help-link").first
        self.assertEqual(
            await link.get_attribute("href"),
            "https://aistudio.google.com/app/apikey",
        )
        self.assertEqual(await link.get_attribute("target"), "_blank")
        self.assertEqual(await link.get_attribute("rel"), "noopener noreferrer")

        overlay_box = await overlay.bounding_box()
        self.assertEqual(overlay_box["width"], 1280)

        await page.keyboard.press("Escape")
        self.assertFalse(await overlay.is_visible())
        self.assertEqual(await help_button.get_attribute("aria-expanded"), "false")
        self.assertEqual(commands, [])

        await host.locator("[data-role=toggle]").click()
        self.assertFalse(await help_button.is_visible())

    async def test_open_help_keeps_focus_inside_the_dialog(self):
        async def handler(source, command):
            if command["type"] == "get_settings":
                return {"ok": True, "settings": PUBLIC_SETTINGS}
            return {"ok": False, "error": "unused"}

        page = await self.browser.new_page(viewport={"width": 1280, "height": 900})
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=TEST_APP_HTML,
            ),
        )
        await page.goto("https://app.sessions.blue/browse")

        host = page.locator("#bluedot-agent-panel")
        overlay = host.locator("[data-role=help]")
        await host.locator("[data-role=help-toggle]").click()
        self.assertTrue(await overlay.is_visible())

        self.assertTrue(await page.evaluate("() => document.body.inert"))
        self.assertTrue(
            await host.evaluate("(node) => node.shadowRoot.querySelector('aside').inert")
        )

        inside_dialog = """() => {
          const shadow = document.getElementById("bluedot-agent-panel").shadowRoot;
          const active = shadow.activeElement;
          const dialog = shadow.querySelector("[data-role=help-dialog]");
          return Boolean(active) && dialog.contains(active) || active === dialog;
        }"""
        for step in range(12):
            await page.keyboard.press("Tab")
            with self.subTest(tab=step):
                self.assertTrue(await page.evaluate(inside_dialog))

        await page.keyboard.press("Escape")

        self.assertFalse(await overlay.is_visible())
        self.assertFalse(await page.evaluate("() => document.body.inert"))
        self.assertFalse(
            await host.evaluate("(node) => node.shadowRoot.querySelector('aside').inert")
        )
        self.assertEqual(
            await host.evaluate(
                "(node) => node.shadowRoot.activeElement.dataset.role"
            ),
            "help-toggle",
        )

    async def test_browser_back_replays_the_previous_panel_search(self):
        commands = []

        async def handler(source, command):
            if command["type"] == "get_settings":
                return {"ok": True, "settings": PUBLIC_SETTINGS}
            commands.append(command)
            if command["type"] == "restore":
                if command["index"] < 0:
                    return {"ok": True, "result": None}
                return {
                    "ok": True,
                    "result": {
                        "ok": True,
                        "prompt": "первый запрос",
                        "parser": "gemini",
                        "warning": None,
                        "applied_sliders": {"Mood": [3, 5]},
                        "categories": {},
                        "missing_sliders": {},
                        "exact_count": 4,
                        "has_related": False,
                    },
                }
            return {
                "ok": True,
                "prompt": command["prompt"],
                "parser": "gemini",
                "warning": None,
                "applied_sliders": {"Mood": [3, 5]},
                "categories": {},
                "missing_sliders": {},
                "exact_count": 4,
                "has_related": False,
                "history_index": len([item for item in commands if item["type"] == "search"]) - 1,
            }

        page = await self.browser.new_page(viewport={"width": 1280, "height": 900})
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=TEST_APP_HTML,
            ),
        )
        await page.goto("https://app.sessions.blue/browse")

        host = page.locator("#bluedot-agent-panel")
        query = host.locator("[data-role=query]")
        status = host.locator("[data-role=status]")
        result = host.locator("[data-role=result]")

        await query.fill("первый запрос")
        await host.locator("[data-role=search]").click()
        await status.get_by_text("Готово.").wait_for()

        await query.fill("второй запрос")
        await host.locator("[data-role=search]").click()
        await status.get_by_text("Готово.").wait_for()

        self.assertEqual(
            [command["type"] for command in commands],
            ["search", "search"],
        )

        await page.go_back()
        await status.get_by_text("Показан прошлый запрос.").wait_for()

        self.assertEqual(commands[-1], {"type": "restore", "index": 0})
        self.assertEqual(await query.input_value(), "первый запрос")
        self.assertTrue(await result.is_visible())

        await page.go_back()
        await status.get_by_text("Фильтры сброшены к исходным.").wait_for()

        self.assertEqual(commands[-1], {"type": "restore", "index": -1})
        self.assertFalse(await result.is_visible())

        await page.go_forward()
        await status.get_by_text("Показан прошлый запрос.").wait_for()

        self.assertEqual(commands[-1], {"type": "restore", "index": 0})
        self.assertEqual(page.url, "https://app.sessions.blue/browse")

    async def test_panel_is_responsive_and_uses_consistent_control_geometry(self):
        async def handler(source, command):
            if command["type"] == "get_settings":
                return {"ok": True, "settings": PUBLIC_SETTINGS}
            return {"ok": False, "error": "unused"}

        for width in (320, 375, 414, 768):
            with self.subTest(width=width):
                page = await self.browser.new_page(
                    viewport={"width": width, "height": 800}
                )
                await install_panel(page, handler)
                await page.route(
                    "https://app.sessions.blue/**",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="text/html",
                        body=TEST_APP_HTML,
                    ),
                )
                await page.goto("https://app.sessions.blue/browse")

                host = page.locator("#bluedot-agent-panel")
                await host.locator("[data-role=settings-toggle]").click()
                metrics = await host.evaluate(
                    """node => {
                      const shadow = node.shadowRoot;
                      const style = selector => getComputedStyle(shadow.querySelector(selector));
                      const height = selector => shadow.querySelector(selector)
                        .getBoundingClientRect().height;
                      return {
                        viewportWidth: window.innerWidth,
                        documentWidth: document.documentElement.scrollWidth,
                        hostWidth: node.getBoundingClientRect().width,
                        overlay: node.hasAttribute("data-overlay"),
                        queryHeight: height("[data-role=query]"),
                        searchHeight: height("[data-role=search]"),
                        settingsButtonHeights: [...shadow.querySelectorAll(
                          "[data-role=settings-actions] button"
                        )].map(button => button.getBoundingClientRect().height),
                        panelFont: style("aside").fontFamily,
                        buttonFont: style("button").fontFamily,
                        buttonWhiteSpace: style("button").whiteSpace
                      };
                    }"""
                )

                self.assertLessEqual(metrics["documentWidth"], width)
                self.assertLessEqual(metrics["hostWidth"], width)
                self.assertEqual(metrics["overlay"], width < 640)
                self.assertEqual(round(metrics["queryHeight"]), 44)
                self.assertEqual(round(metrics["searchHeight"]), 44)
                self.assertEqual(
                    [round(value) for value in metrics["settingsButtonHeights"]],
                    [44, 44, 44],
                )
                self.assertEqual(metrics["buttonFont"], metrics["panelFont"])
                self.assertEqual(metrics["buttonWhiteSpace"], "nowrap")

                search = host.locator("[data-role=search]")
                await host.locator("[data-role=query]").focus()
                await page.keyboard.press("Tab")
                self.assertTrue(await search.evaluate("button => button.matches(':focus')"))
                focus = await search.evaluate(
                    """button => {
                      const value = getComputedStyle(button);
                      return { style: value.outlineStyle, width: value.outlineWidth };
                    }"""
                )
                self.assertEqual(focus, {"style": "solid", "width": "2px"})
                await page.close()

    async def test_query_field_grows_wraps_and_keeps_search_visible(self):
        async def handler(source, command):
            if command["type"] == "get_settings":
                return {"ok": True, "settings": PUBLIC_SETTINGS}
            return {"ok": False, "error": "unused"}

        page = await self.browser.new_page(viewport={"width": 420, "height": 360})
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="<html><body><div id='root'>Blue Dot</div></body></html>",
            ),
        )
        await page.goto("https://app.sessions.blue/browse")

        host = page.locator("#bluedot-agent-panel")
        query = host.locator("[data-role=query]")
        initial_height = (await query.bounding_box())["height"]
        await query.fill("длинный музыкальный запрос " * 80)
        metrics = await query.evaluate(
            """field => {
              const style = getComputedStyle(field);
              const search = field.form.querySelector("[data-role=search]");
              return {
                tag: field.tagName,
                height: field.getBoundingClientRect().height,
                clientHeight: field.clientHeight,
                scrollHeight: field.scrollHeight,
                resize: style.resize,
                overflowY: style.overflowY,
                overflowWrap: style.overflowWrap,
                searchBottom: search.getBoundingClientRect().bottom,
                viewportHeight: window.innerHeight
              };
            }"""
        )

        self.assertEqual(metrics["tag"], "TEXTAREA")
        self.assertGreater(metrics["height"], initial_height)
        self.assertEqual(metrics["resize"], "vertical")
        self.assertEqual(metrics["overflowY"], "auto")
        self.assertEqual(metrics["overflowWrap"], "anywhere")
        self.assertGreater(metrics["scrollHeight"], metrics["clientHeight"])
        self.assertLessEqual(metrics["searchBottom"], metrics["viewportHeight"])

        await host.locator("[data-role=toggle]").click()
        await page.set_viewport_size({"width": 420, "height": 260})
        await host.locator("[data-role=toggle]").click()
        await page.wait_for_function(
            """() => {
              const host = document.getElementById("bluedot-agent-panel");
              const search = host?.shadowRoot?.querySelector("[data-role=search]");
              return search && search.getBoundingClientRect().bottom <= window.innerHeight;
            }"""
        )

        await query.fill("первая строка")
        await query.press("Shift+Enter")
        self.assertEqual(await query.input_value(), "первая строка\n")

    async def test_collapsed_panel_keeps_expand_button_inside_visible_strip(self):
        async def handler(source, command):
            return {"ok": False, "error": "unused"}

        page = await self.browser.new_page(viewport={"width": 800, "height": 600})
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=TEST_APP_HTML,
            ),
        )
        await page.goto("https://app.sessions.blue/browse")

        host = page.locator("#bluedot-agent-panel")
        toggle = host.locator("button[data-role=toggle]")
        await toggle.click()

        host_box = await host.bounding_box()
        toggle_box = await toggle.bounding_box()
        self.assertIsNotNone(toggle_box)
        self.assertGreaterEqual(round(toggle_box["x"]), round(host_box["x"]))
        self.assertLessEqual(
            round(toggle_box["x"] + toggle_box["width"]),
            round(host_box["x"] + host_box["width"]),
        )
        self.assertFalse(
            await host.locator("button[data-role=settings-toggle]").is_visible()
        )
        self.assertEqual(await toggle.text_content(), "›")

        await toggle.click()
        self.assertEqual(await toggle.get_attribute("aria-expanded"), "true")

    async def test_enter_renders_loading_result_and_error_states(self):
        started = asyncio.Event()
        release = asyncio.Event()
        commands = []

        async def handler(source, command):
            if command["type"] == "get_settings":
                return {"ok": True, "settings": PUBLIC_SETTINGS}
            commands.append(command)
            if len(commands) == 1:
                started.set()
                await release.wait()
                return {
                    "ok": True,
                    "parser": "gemini",
                    "warning": None,
                    "applied_sliders": {"Mood": [3, 5]},
                    "categories": {"Tags": ["Peaceful"], "Instruments": ["Strings"]},
                    "missing_sliders": {"Tension": [1, 2]},
                    "exact_count": 0,
                    "has_related": True,
                }
            return {"ok": False, "error": "Безопасная ошибка"}

        page = await self.browser.new_page()
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="<html><body><div id='root'><main>Blue Dot</main></div></body></html>",
            ),
        )
        await page.goto("https://app.sessions.blue/browse")
        host = page.locator("#bluedot-agent-panel")
        field = host.locator("textarea[data-role=query]")
        search = host.locator("button[data-role=search]")
        status = host.locator("[data-role=status]")

        await field.fill("calm strings")
        submission = asyncio.create_task(field.press("Enter"))
        await started.wait()

        self.assertTrue(await field.is_disabled())
        self.assertTrue(await search.is_disabled())
        self.assertEqual(await status.text_content(), "Ищу…")

        release.set()
        await submission
        await status.filter(has_text="Готово.").wait_for()

        text = await host.locator("aside").text_content()
        self.assertEqual(commands, [{"type": "search", "prompt": "calm strings"}])
        self.assertIn("Gemini", text)
        self.assertIn("Mood: 3–5", text)
        self.assertIn("Tags: Peaceful", text)
        self.assertIn("Instruments: Strings", text)
        self.assertIn("Tension: 1–2", text)
        self.assertIn("Точных совпадений: 0", text)
        self.assertIn("Точных совпадений нет; ниже похожие треки", text)

        await page.goto("https://app.sessions.blue/another-page")
        host = page.locator("#bluedot-agent-panel")
        field = host.locator("textarea[data-role=query]")
        status = host.locator("[data-role=status]")

        self.assertEqual(await field.input_value(), "calm strings")
        self.assertIn(
            "Последняя интерпретация: Google AI Studio (Gemini)",
            await host.locator("aside").text_content(),
        )

        await field.fill("next")
        await field.press("Enter")

        self.assertEqual(await status.text_content(), "Безопасная ошибка")
        self.assertEqual(await status.get_attribute("data-kind"), "error")

    async def test_new_panel_run_ignores_restored_session_state(self):
        async def handler(source, command):
            return {"ok": False, "error": "unused"}

        page = await self.browser.new_page()
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="<html><body><div id='root'>Blue Dot</div></body></html>",
            ),
        )
        await page.goto("https://app.sessions.blue/browse")
        await page.evaluate(
            """() => sessionStorage.setItem(
              "__bluedotAgentPanelState:old-run",
              JSON.stringify({
                query: "restored query",
                result: {
                  ok: true,
                  parser: "rule_based",
                  applied_sliders: {},
                  categories: {},
                  missing_sliders: {},
                  exact_count: 1,
                  has_related: false
                }
              })
            )"""
        )

        await install_panel(page, handler)
        await page.reload()

        host = page.locator("#bluedot-agent-panel")
        self.assertEqual(await host.locator("textarea[data-role=query]").input_value(), "")
        self.assertTrue(await host.locator("[data-role=result]").is_hidden())
        self.assertEqual(
            await page.evaluate(
                """() => Object.keys(sessionStorage)
                  .filter((key) => key.startsWith("__bluedotAgentPanelState:"))
                  .length"""
            ),
            0,
        )

    async def test_space_in_query_does_not_trigger_page_playback_shortcut(self):
        async def handler(source, command):
            return {"ok": False, "error": "unused"}

        page = await self.browser.new_page()
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="""
                  <html>
                    <body>
                      <div id="root">Blue Dot</div>
                      <script>
                        window.playbackShortcutCount = 0;
                        window.addEventListener("keydown", (event) => {
                          if (event.code === "Space") {
                            window.playbackShortcutCount += 1;
                            event.preventDefault();
                          }
                        });
                      </script>
                    </body>
                  </html>
                """,
            ),
        )
        await page.goto("https://app.sessions.blue/browse")

        field = page.locator("#bluedot-agent-panel").locator("textarea[data-role=query]")
        await field.click()
        await page.keyboard.type("calm strings")

        self.assertEqual(await field.input_value(), "calm strings")
        self.assertEqual(await page.evaluate("window.playbackShortcutCount"), 0)

    async def test_settings_offer_all_providers_without_sending_key_from_browser(self):
        commands = []

        async def handler(source, command):
            if command["type"] == "get_settings":
                return {"ok": True, "settings": PUBLIC_SETTINGS}
            commands.append(command)
            if command["type"] == "choose_download_directory":
                return {"ok": True, "download_directory": r"E:\Music\Blue Dot"}
            updated = {
                **PUBLIC_SETTINGS,
                "selected_provider": command["provider"],
                "providers": {
                    **PUBLIC_SETTINGS["providers"],
                    command["provider"]: {
                        **PUBLIC_SETTINGS["providers"][command["provider"]],
                        "model": command["model"],
                        "has_api_key": command["type"] == "set_api_key",
                    },
                },
            }
            return {"ok": True, "settings": updated}

        page = await self.browser.new_page()
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=TEST_APP_HTML,
            ),
        )
        await page.goto("https://app.sessions.blue/browse")
        host = page.locator("#bluedot-agent-panel")
        await host.locator("[data-role=settings-toggle]").click()
        self.assertEqual(
            await host.locator("[data-role=save-settings]").text_content(),
            "Применить",
        )
        self.assertEqual(
            await host.locator("[data-role=provider] option").all_text_contents(),
            [
                "Google AI Studio (Gemini)",
                "Groq",
                "OpenRouter",
                "Mistral",
            ],
        )
        await host.locator("[data-role=provider]").select_option("openrouter")
        browser = host.locator("[data-role=browser]")
        self.assertEqual(
            await browser.locator("option").all_text_contents(),
            ["Firefox", "Google Chrome"],
        )
        await browser.select_option("chrome")
        download_directory = host.locator("[data-role=download-directory]")
        self.assertEqual(await download_directory.input_value(), r"D:\Downloads")
        self.assertTrue(
            await host.evaluate(
                """node => {
                  const shadow = node.shadowRoot;
                  const folder = shadow.querySelector("[data-role=download-directory]");
                  const heading = [...shadow.querySelectorAll("h2")]
                    .find(item => item.textContent.trim() === "Настройки ИИ");
                  const provider = shadow.querySelector("[data-role=provider]");
                  return Boolean(
                    folder && heading && provider &&
                    (folder.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING) &&
                    (heading.compareDocumentPosition(provider) & Node.DOCUMENT_POSITION_FOLLOWING)
                  );
                }"""
            )
        )
        self.assertEqual(await download_directory.get_attribute("readonly"), "")
        await download_directory.click()
        self.assertEqual(await download_directory.input_value(), r"E:\Music\Blue Dot")
        model = host.locator("[data-role=model]")
        self.assertEqual(await model.evaluate("element => element.tagName"), "SELECT")
        self.assertEqual(
            await model.locator("option").all_text_contents(),
            ["openai/gpt-oss-20b:free"],
        )
        await model.select_option("openai/gpt-oss-20b:free")
        await host.locator("[data-role=save-settings]").click()
        await host.locator("[data-role=set-api-key]").click()

        self.assertEqual(
            commands,
            [
                {
                    "type": "choose_download_directory",
                    "download_directory": r"D:\Downloads",
                },
                {
                    "type": "save_settings",
                    "browser": "chrome",
                    "provider": "openrouter",
                    "model": "openai/gpt-oss-20b:free",
                    "download_directory": r"E:\Music\Blue Dot",
                    "clear_api_key": False,
                },
                {
                    "type": "set_api_key",
                    "provider": "openrouter",
                    "model": "openai/gpt-oss-20b:free",
                }
            ],
        )
        for command in commands:
            self.assertNotIn("api_key", command)

    async def test_clearing_the_key_takes_two_clicks(self):
        commands = []

        async def handler(source, command):
            if command["type"] == "get_settings":
                return {"ok": True, "settings": PUBLIC_SETTINGS}
            commands.append(command)
            cleared = {
                **PUBLIC_SETTINGS,
                "providers": {
                    **PUBLIC_SETTINGS["providers"],
                    "gemini": {**PUBLIC_SETTINGS["providers"]["gemini"], "has_api_key": False},
                },
            }
            return {"ok": True, "settings": cleared}

        page = await self.browser.new_page()
        await install_panel(page, handler)
        await page.route(
            "https://app.sessions.blue/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=TEST_APP_HTML,
            ),
        )
        await page.goto("https://app.sessions.blue/browse")

        host = page.locator("#bluedot-agent-panel")
        clear = host.locator("[data-role=clear-api-key]")
        await host.locator("[data-role=settings-toggle]").click()
        self.assertEqual(await clear.text_content(), "Удалить ключ")

        await clear.click()

        self.assertEqual(commands, [])
        self.assertEqual(await clear.get_attribute("data-state"), "confirm")
        self.assertEqual(await clear.text_content(), "Нажмите ещё раз для удаления")

        await host.locator("[data-role=provider]").select_option("groq")

        self.assertEqual(commands, [])
        self.assertEqual(await clear.text_content(), "Удалить ключ")

        await host.locator("[data-role=provider]").select_option("gemini")
        await clear.click()
        await clear.click()

        self.assertEqual(
            [command["type"] for command in commands],
            ["save_settings"],
        )
        self.assertTrue(commands[0]["clear_api_key"])
        self.assertEqual(await clear.text_content(), "Удалить ключ")
        self.assertEqual(
            await host.locator("[data-role=status]").text_content(),
            "Сохранённый API-ключ удалён.",
        )


if __name__ == "__main__":
    unittest.main()
