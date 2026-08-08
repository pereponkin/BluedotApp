from __future__ import annotations

import asyncio
import struct
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from playwright.async_api import async_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOGO = PROJECT_ROOT / "BlueDotSessionsLogo.svg"
OUTPUT_ICON = PROJECT_ROOT / "BlueDotAgent.ico"
PREVIEW_PNG = PROJECT_ROOT / "BlueDotAgentIcon.png"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def _icon_svg(size: int) -> str:
    root = ET.parse(SOURCE_LOGO).getroot()
    paths = root.findall(f"{{{SVG_NAMESPACE}}}path")
    if len(paths) < 4:
        raise RuntimeError("The Blue Dot source logo does not contain the expected paths")

    dot = paths[0]
    microphone = paths[-3:]
    dot.set("fill", "#606161")
    for path in microphone:
        path.set("fill", "#7473C8")

    namespace_declaration = f' xmlns:ns0="{SVG_NAMESPACE}"'

    def serialize(path: ET.Element) -> str:
        return (
            ET.tostring(path, encoding="unicode")
            .replace("ns0:", "")
            .replace(namespace_declaration, "")
        )

    shapes = serialize(dot) + "".join(serialize(path) for path in microphone)
    return f"""<!doctype html>
<html>
  <head>
    <style>
      html, body {{ margin: 0; width: {size}px; height: {size}px; overflow: hidden; }}
      svg {{ display: block; }}
    </style>
  </head>
  <body>
    <svg width="{size}" height="{size}" viewBox="-4 -4 56 56"
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="-4" y="-4" width="56" height="56" rx="12" fill="#101A2A" />
      {shapes}
    </svg>
  </body>
</html>"""


def _write_ico(png_files: list[Path]) -> None:
    images = [path.read_bytes() for path in png_files]
    header_size = 6 + 16 * len(images)
    offset = header_size
    entries = []

    for size, image in zip(ICON_SIZES, images, strict=True):
        dimension = 0 if size == 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(image),
                offset,
            )
        )
        offset += len(image)

    with OUTPUT_ICON.open("wb") as output:
        output.write(struct.pack("<HHH", 0, 1, len(images)))
        output.writelines(entries)
        output.writelines(images)


async def build() -> None:
    with tempfile.TemporaryDirectory(prefix="bluedot-icon-") as temp_directory:
        temp_path = Path(temp_directory)
        png_files: list[Path] = []

        async with async_playwright() as playwright:
            browser = await playwright.firefox.launch(headless=True)
            try:
                for size in ICON_SIZES:
                    page = await browser.new_page(viewport={"width": size, "height": size})
                    await page.set_content(_icon_svg(size))
                    png_path = temp_path / f"icon-{size}.png"
                    await page.screenshot(path=png_path)
                    await page.close()
                    png_files.append(png_path)
            finally:
                await browser.close()

        PREVIEW_PNG.write_bytes(png_files[-1].read_bytes())
        _write_ico(png_files)


if __name__ == "__main__":
    asyncio.run(build())
