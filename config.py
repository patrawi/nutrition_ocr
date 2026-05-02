"""Environment configuration and API clients."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from google import genai
from mistralai.client import Mistral

load_dotenv()

TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]
MISTRAL_API_KEY: str = os.environ["MISTRAL_API_KEY"]
GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]
GOOGLE_SHEETS_ID: str = os.environ["GOOGLE_SHEETS_ID"]

mistral_client = Mistral(api_key=MISTRAL_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

GEMINI_MODEL = "gemini-3-flash-preview"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
