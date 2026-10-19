"""Shared test fixtures: fake env vars so config.py imports cleanly."""

from __future__ import annotations

import os

os.environ.update(
    {
        "TELEGRAM_TOKEN": "test",
        "GEMINI_API_KEY": "test",
        "GOOGLE_SHEETS_ID": "test",
        "GOOGLE_SHEETS_CREDENTIALS": "test.json",
    }
)
