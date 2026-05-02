"""Data models and parsers for nutrition extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class NutritionData:
    """Structured nutrition data extracted from a label."""

    item_name: str
    serving_value: str | None
    serving_unit: str | None
    calories: str | None
    protein: str | None
    carbs: str | None
    fat: str | None

    @classmethod
    def from_gemini_dict(cls, data: dict) -> NutritionData:
        """Build from Gemini JSON with fallback parsing for combined fields."""
        value = _none_if_empty(data.get("serving_value"))
        unit = _none_if_empty(data.get("serving_unit"))

        if value is None and unit is None:
            per_unit = _none_if_empty(data.get("per_unit"))
            if per_unit:
                value, unit = parse_serving_size(per_unit)

        return cls(
            item_name=data.get("item_name") or "Unknown",
            serving_value=value,
            serving_unit=unit,
            calories=_none_if_empty(data.get("calories")),
            protein=_none_if_empty(data.get("protein")),
            carbs=_none_if_empty(data.get("carbs")),
            fat=_none_if_empty(data.get("fat")),
        )

    def format_summary(self) -> str:
        """Format a user-facing summary."""
        serving = f"{self.serving_value or '?'}{self.serving_unit or ''}"
        return (
            f"📦 Per unit: {serving}\n"
            f"🔥 Cal: {self.calories or '?'}  |  "
            f"🥩 P: {self.protein or '?'}g  |  "
            f"🍞 C: {self.carbs or '?'}g  |  "
            f"🧈 F: {self.fat or '?'}g"
        )


def parse_serving_size(text: str) -> tuple[str | None, str | None]:
    """Parse strings like '100g', '100ml', '15 g' into (value, unit).

    Returns (None, None) for empty input.
    Returns (None, original_text) when no numeric value is found.
    """
    text = text.strip().lower()
    if not text:
        return None, None
    match = re.match(r"^([\d.]+)\s*(g|ml|mg|kg|l|oz|lb)$", text)
    if match:
        return match.group(1), match.group(2)

    num_match = re.match(r"^([\d.]+)$", text)
    if num_match:
        return num_match.group(1), None

    return None, text


def _none_if_empty(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None
