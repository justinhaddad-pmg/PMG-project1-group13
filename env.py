"""Load secrets from a local .env file (not committed to git)."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_env(env_path: Path | None = None) -> bool:
    """Parse a .env file into os.environ. Returns True if the file exists."""
    path = env_path or ROOT / ".env"
    if not path.exists():
        return False

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
    return True


def generate_frontend_config() -> bool:
    """Write config.local.json for the browser app from YOUTUBE_API_KEY in .env."""
    load_env()
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        return False

    out = ROOT / "config.local.json"
    out.write_text(json.dumps({"youtubeApiKey": key}, indent=2) + "\n")
    return True
