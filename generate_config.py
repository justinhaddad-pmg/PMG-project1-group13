#!/usr/bin/env python3
"""Generate config.local.json from .env for the browser app."""

import sys

from env import generate_frontend_config, load_env

if not load_env():
    print("❌  No .env file found. Copy .env.example to .env and add your keys.")
    sys.exit(1)

if not generate_frontend_config():
    print("❌  YOUTUBE_API_KEY is missing or empty in .env")
    sys.exit(1)

print("✅  Wrote config.local.json")
