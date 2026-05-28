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
        "Extract nutrition info from this OCR text (likely a food label photo).\n"
        "Return ONLY a JSON object with these keys. Use null for any field you cannot find.\n\n"
        "Keys:\n"
        '- "item_name": product name as a string, or null.\n'
        '- "serving_value": numeric serving size (e.g. 100, 15, 1.5) as a number, or null.\n'
        '- "serving_unit": unit string — one of g, ml, mg, kg, oz, lb — or null.\n'
        '- "calories": number, or null.\n'
        '- "protein": grams of protein as a number, or null.\n'
        '- "carbs": grams of carbs as a number, or null.\n'
        '- "fat": grams of fat as a number, or null.\n\n'
        "Rules:\n"
        "- Prefer the \"per serving\" column if both serving and 100g columns are present.\n"
        "- Look for patterns like \"Calories 120\", \"Energy 120 kcal\", \"Protein 5g\".\n"
        '- If serving size says "1 packet (30g)", serving_value=30, serving_unit="g".\n'
        "- If the OCR text is garbled, not a nutrition label, or you cannot extract any meaningful data, "
        'return all nulls AND set item_name to "NOT_A_LABEL".\n'
        "- Output raw JSON only — no markdown fences, no explanation.\n\n"
        f"OCR Text:\n{raw_ocr}"
    )

    logger.info("Sending %d chars to Gemini:\n%s", len(raw_ocr), raw_ocr)

    response = config.gemini_client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
    )

    text = response.text.strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
        text = text.strip()

    result = json.loads(text)
    logger.info("Gemini raw result: %s", result)
    return result
