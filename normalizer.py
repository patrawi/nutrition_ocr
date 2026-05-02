"""Gemini normalization service."""

from __future__ import annotations

import json
import logging

import config

logger = logging.getLogger(__name__)


async def normalize_ocr(raw_ocr: str) -> dict:
    """Ask Gemini to extract structured nutrition data from OCR text.

    Expected JSON keys: item_name, serving_value, serving_unit,
    calories, protein, carbs, fat.
    """
    prompt = (
        "Analyze this OCR text from a nutrition label. "
        "Extract: Item Name (guess if missing), "
        "Serving Value (numeric only, e.g. 100, 15, 1.5), "
        "Serving Unit (g, ml, mg, kg, oz, lb — use the unit from the label), "
        "Calories, Protein (g), Carbs (g), Fat (g). "
        "Return ONLY valid JSON with keys: "
        '"item_name", "serving_value", "serving_unit", "calories", '
        '"protein", "carbs", "fat".\n\n'
        f"OCR Text:\n{raw_ocr}"
    )

    response = config.gemini_client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
    )

    text = response.text.strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
        text = text.strip()

    return json.loads(text)
