"""Tests for nutrition data models and parsers."""

from __future__ import annotations

import pytest

from models import NutritionData, parse_serving_size


@pytest.mark.parametrize(
    ("input_text", "expected_value", "expected_unit"),
    [
        ("100g", "100", "g"),
        ("100ml", "100", "ml"),
        ("15 g", "15", "g"),
        ("1.5kg", "1.5", "kg"),
        ("250", "250", None),
        ("", None, None),
        ("unknown", None, "unknown"),
        ("  30   ml  ", "30", "ml"),
    ],
)
def test_parse_serving_size(
    input_text: str,
    expected_value: str | None,
    expected_unit: str | None,
) -> None:
    value, unit = parse_serving_size(input_text)
    assert value == expected_value
    assert unit == expected_unit


def test_nutrition_data_from_gemini_dict_new_format() -> None:
    data = {
        "item_name": "Protein Bar",
        "serving_value": "50",
        "serving_unit": "g",
        "calories": "200",
        "protein": "20",
        "carbs": "10",
        "fat": "5",
    }
    result = NutritionData.from_gemini_dict(data)
    assert result.item_name == "Protein Bar"
    assert result.serving_value == "50"
    assert result.serving_unit == "g"
    assert result.calories == "200"


def test_nutrition_data_from_gemini_dict_old_format_fallback() -> None:
    data = {
        "item_name": "Milk",
        "per_unit": "250ml",
        "calories": "150",
        "protein": "8",
        "carbs": "12",
        "fat": "5",
    }
    result = NutritionData.from_gemini_dict(data)
    assert result.serving_value == "250"
    assert result.serving_unit == "ml"
    assert result.item_name == "Milk"


def test_nutrition_data_from_gemini_dict_empty_fallback() -> None:
    data = {
        "item_name": "",
        "per_unit": "",
        "calories": "",
    }
    result = NutritionData.from_gemini_dict(data)
    assert result.item_name == "Unknown"
    assert result.serving_value is None
    assert result.serving_unit is None
    assert result.calories is None


def test_nutrition_data_format_summary() -> None:
    data = NutritionData(
        item_name="Test",
        serving_value="100",
        serving_unit="g",
        calories="300",
        protein="20",
        carbs="40",
        fat="10",
    )
    summary = data.format_summary()
    assert "100g" in summary
    assert "Cal: 300" in summary
    assert "P: 20g" in summary
