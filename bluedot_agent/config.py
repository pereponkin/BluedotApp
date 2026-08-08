from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent


def default_state_directory(
    *,
    platform: str = sys.platform,
    environ: Mapping[str, str] = os.environ,
    home: Path | None = None,
) -> Path:
    user_home = home or Path.home()
    if platform == "win32":
        return Path(environ.get("LOCALAPPDATA", user_home / "AppData" / "Local")) / "BlueDotAgent"
    if platform == "darwin":
        return user_home / "Library" / "Application Support" / "BlueDotAgent"
    return Path(environ.get("XDG_DATA_HOME", user_home / ".local" / "share")) / "BlueDotAgent"


STATE_DIR = Path(
    os.environ.get(
        "BLUEDOT_STATE_DIR",
        default_state_directory(),
    )
)
PROFILE_DIR = Path(os.environ.get("BLUEDOT_PROFILE_DIR", STATE_DIR / "profile"))
LEGACY_PROFILE_DIR = PROJECT_ROOT / ".browser-profile"
LOG_DIR = Path(os.environ.get("BLUEDOT_LOG_DIR", STATE_DIR / "logs"))


def load_yaml(name: str) -> dict[str, Any]:
    resource = resources.files(__package__) / "resources" / name
    with resource.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    if not isinstance(loaded, dict):
        raise ValueError(f"{name} must contain a YAML object")

    return loaded
