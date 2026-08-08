from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.async_api import async_playwright

from bluedot_agent.browser import launch_context


async def smoke(browser: str) -> None:
    with TemporaryDirectory() as directory:
        async with async_playwright() as playwright:
            context = await launch_context(
                playwright,
                Path(directory) / "profile",
                headed=False,
                browser=browser,
            )
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto("data:text/html,<title>Blue Dot Agent smoke</title>")
                if await page.title() != "Blue Dot Agent smoke":
                    raise RuntimeError("browser smoke page did not load")
            finally:
                await context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("browser", choices=("firefox", "chrome"))
    arguments = parser.parse_args()
    asyncio.run(smoke(arguments.browser))
