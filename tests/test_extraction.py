"""Tests for the label extraction module."""

from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import MagicMock

import pytest

os.environ.update(
    {
        "TELEGRAM_TOKEN": "test",
        "GEMINI_API_KEY": "test",
        "GOOGLE_SHEETS_ID": "test",
        "GOOGLE_SHEETS_CREDENTIALS": "test.json",
    }
)

from google.genai import types

import config
from extraction import Extraction, extract_nutrition

GOOD_JSON = (
    '{"item_name": "Test Bar", "serving_value": 100, "serving_unit": "g", '
    '"calories": 120, "protein": 5, "carbs": 20, "fat": 3}'
)


def _client_with(*responses: MagicMock) -> MagicMock:
    client = MagicMock()
    client.models.generate_content.side_effect = list(responses)
    return client


def _response(text: str | None) -> MagicMock:
    response = MagicMock()
    response.text = text
    return response


def test_extract_returns_nutrition_and_raw_ocr() -> None:
    client = _client_with(
        _response("  Energy 120 kcal\nProtein 5 g  "),
        _response(f"```json\n{GOOD_JSON}\n```"),
    )

    extraction = asyncio.run(extract_nutrition(b"fake-jpeg", client=client))

    assert isinstance(extraction, Extraction)
    assert extraction.raw_ocr == "Energy 120 kcal\nProtein 5 g"
    assert extraction.nutrition.item_name == "Test Bar"
    assert extraction.nutrition.calories == "120"
    assert extraction.nutrition.serving_value == "100"
    assert extraction.is_label


def test_not_a_label_sentinel_is_flagged() -> None:
    client = _client_with(
        _response("garbled text"),
        _response(
            '{"item_name": "NOT_A_LABEL", "serving_value": null, '
            '"serving_unit": null, "calories": null, "protein": null, '
            '"carbs": null, "fat": null}'
        ),
    )

    extraction = asyncio.run(extract_nutrition(b"fake-jpeg", client=client))

    assert not extraction.is_label


def test_all_nulls_is_flagged() -> None:
    client = _client_with(
        _response("some label text"),
        _response(
            '{"item_name": "Mystery", "serving_value": null, '
            '"serving_unit": null, "calories": null, "protein": null, '
            '"carbs": null, "fat": null}'
        ),
    )

    extraction = asyncio.run(extract_nutrition(b"fake-jpeg", client=client))

    assert extraction.nutrition.item_name == "Mystery"
    assert not extraction.is_label


def test_empty_ocr_skips_normalisation() -> None:
    client = _client_with(_response(None))

    extraction = asyncio.run(extract_nutrition(b"fake-jpeg", client=client))

    assert extraction.raw_ocr == ""
    assert not extraction.is_label
    client.models.generate_content.assert_called_once()


def test_invalid_json_propagates() -> None:
    client = _client_with(_response("label text"), _response("not json at all"))

    with pytest.raises(json.JSONDecodeError):
        asyncio.run(extract_nutrition(b"fake-jpeg", client=client))


def test_both_calls_use_injected_client_and_configured_model() -> None:
    client = _client_with(_response("label text"), _response(GOOD_JSON))

    asyncio.run(extract_nutrition(b"fake-jpeg", client=client))

    calls = client.models.generate_content.call_args_list
    assert len(calls) == 2
    for call in calls:
        assert call.kwargs["model"] == config.GEMINI_MODEL
    prompt, image = calls[0].kwargs["contents"]
    assert "nutrition label" in prompt
    assert isinstance(image, types.Part)
    assert isinstance(calls[1].kwargs["contents"], str)
