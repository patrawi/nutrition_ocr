"""Tests for Google Sheets storage."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

import sheets
from models import NutritionData

T0 = datetime(2026, 10, 19, 12, 30, 45)


@pytest.fixture
def appended_row(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    worksheet = MagicMock()
    spreadsheet = MagicMock()
    spreadsheet.sheet1 = worksheet
    monkeypatch.setattr(sheets, "_get_sheets_client", lambda: spreadsheet)
    return worksheet.append_row


def _nutrition() -> NutritionData:
    return NutritionData(
        item_name="Test Bar",
        serving_value="100",
        serving_unit="g",
        calories="120",
        protein="5",
        carbs="20",
        fat="3",
    )


def test_row_uses_given_timestamp(appended_row: MagicMock) -> None:
    sheets.append_nutrition_row(_nutrition(), "raw ocr", timestamp=T0)

    row = appended_row.call_args.args[0]
    assert row[0] == "2026-10-19"
    assert row[1] == "12:30:45"


def test_row_defaults_to_now(appended_row: MagicMock) -> None:
    sheets.append_nutrition_row(_nutrition(), "raw ocr")

    row = appended_row.call_args.args[0]
    assert row[0] == datetime.now().strftime("%Y-%m-%d")


def test_row_layout_matches_sheet_columns(appended_row: MagicMock) -> None:
    sheets.append_nutrition_row(_nutrition(), "raw ocr", timestamp=T0)

    kwargs = appended_row.call_args.kwargs
    assert kwargs["value_input_option"] == "USER_ENTERED"
    row = appended_row.call_args.args[0]
    assert len(row) == 10
    assert row[2:9] == ["Test Bar", "100", "g", "120", "5", "20", "3"]
    assert row[9] == "raw ocr"
