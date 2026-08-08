from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


root = Path(SPECPATH)
package = root / "bluedot_agent"
datas = [
    (str(package / "panel.js"), "bluedot_agent"),
    (str(package / "resources"), "bluedot_agent/resources"),
    *collect_data_files("playwright"),
]
hiddenimports = collect_submodules("playwright")
icon = os.environ.get("BLUEDOT_BUILD_ICON")
if not icon:
    icon = str(root / ("BlueDotAgent.ico" if sys.platform == "win32" else "BlueDotAgentIcon.png"))

a = Analysis(
    [str(package / "__main__.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)


def without_playwright_browsers(entries):
    return [
        entry
        for entry in entries
        if all(".local-browsers" not in str(part) for part in entry[:2])
    ]


# Playwright's own PyInstaller hooks collect its local browser cache. The agent
# keeps the driver/installer, but downloads Firefox lazily into the user state.
a.datas = without_playwright_browsers(a.datas)
a.binaries = without_playwright_browsers(a.binaries)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BlueDotAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=icon,
)
collection = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="BlueDotAgent",
)

if sys.platform == "darwin":
    app = BUNDLE(
        collection,
        name="BlueDotAgent.app",
        icon=icon,
        bundle_identifier="app.bluedotagent.desktop",
        info_plist={
            "CFBundleDisplayName": "Blue Dot Agent",
            "CFBundleName": "Blue Dot Agent",
            "NSHighResolutionCapable": True,
        },
    )
