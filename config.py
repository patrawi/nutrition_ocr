"""Environment configuration."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]
GOOGLE_SHEETS_ID: str = os.environ["GOOGLE_SHEETS_ID"]

GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
