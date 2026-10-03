"""Tests for Gemini normalizer."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import MagicMock, patch

os.environ.update(
    {
        "TELEGRAM_TOKEN": "test",
        "GEMINI_API_KEY": "test",
        "GOOGLE_SHEETS_ID": "test",
        "GOOGLE_SHEETS_CREDENTIALS": "test.json",
    }
)

with patch.dict(
    "sys.modules",
    {
        "gspread": MagicMock(),
        "google.genai": MagicMock(),
        "google.oauth2.service_account": MagicMock(),
        "telegram": MagicMock(),
        "telegram.ext": MagicMock(),
        "dotenv": MagicMock(),
    },
):
    import config
    from normalizer import normalize_ocr


def test_normalize_ocr_strips_markdown_fences() -> None:
    mock_response = MagicMock()
    mock_response.text = (
        "```json\n"
        '{"item_name": "Test", "serving_value": "100", "serving_unit": "g", '
        '"calories": "100", "protein": "10", "carbs": "20", "fat": "5"}\n'
        "```"
    )

    config.gemini_client.models.generate_content.return_value = mock_response

    result = asyncio.run(normalize_ocr("some ocr text"))

    assert result["item_name"] == "Test"
    assert result["serving_value"] == "100"
    assert result["serving_unit"] == "g"
