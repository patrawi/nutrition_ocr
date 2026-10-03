"""Tests for Gemini OCR."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest

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
    from google.genai import types

    import config
    from ocr import ocr_image


@pytest.fixture(autouse=True)
def _reset_gemini_mocks():
    """The mocked genai module and client are global; clear calls between tests."""
    config.gemini_client.reset_mock()
    types.reset_mock()
    yield


def test_ocr_image_returns_stripped_transcription() -> None:
    mock_response = MagicMock()
    mock_response.text = "  Energy 120 kcal\nProtein 5 g  "

    config.gemini_client.models.generate_content.return_value = mock_response

    result = asyncio.run(ocr_image(b"fake-jpeg-bytes"))

    assert result == "Energy 120 kcal\nProtein 5 g"


def test_ocr_image_sends_prompt_and_image_to_gemini() -> None:
    mock_response = MagicMock()
    mock_response.text = "some text"
    config.gemini_client.models.generate_content.return_value = mock_response

    asyncio.run(ocr_image(b"fake-jpeg-bytes"))

    generate_content = config.gemini_client.models.generate_content
    generate_content.assert_called_once()
    kwargs = generate_content.call_args.kwargs
    assert kwargs["model"] == config.GEMINI_MODEL

    prompt, image = kwargs["contents"]
    assert isinstance(prompt, str)
    assert "nutrition label" in prompt
    types.Part.from_bytes.assert_called_once_with(
        data=b"fake-jpeg-bytes", mime_type="image/jpeg"
    )
    assert image is types.Part.from_bytes.return_value


def test_ocr_image_handles_missing_text() -> None:
    mock_response = MagicMock()
    mock_response.text = None
    config.gemini_client.models.generate_content.return_value = mock_response

    assert asyncio.run(ocr_image(b"fake-jpeg-bytes")) == ""
