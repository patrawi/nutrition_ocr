"""Label extraction: photo bytes → structured nutrition data.

One deep interface for the whole extraction stage. Behind it: two Gemini
round-trips (vision OCR, then JSON extraction), markdown fence stripping,
and the "is this actually a label?" guard.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from google.genai import Client, types

import config
from models import NutritionData

logger = logging.getLogger(__name__)

OCR_PROMPT = (
    "You are an OCR engine. Transcribe every piece of text visible in this "
    "image exactly as written, preserving reading order, numbers and units. "
    "The image is likely a photo of a food nutrition label. "
    "Output the transcription as plain text only — no commentary, no markdown."
)

NOT_A_LABEL = "NOT_A_LABEL"

_client: Client | None = None


def _get_client() -> Client:
    """Return the lazily-created Gemini client (cached like sheets.py creds)."""
    global _client
    if _client is None:
        _client = Client(api_key=config.GEMINI_API_KEY)
    return _client


@dataclass
class Extraction:
    """Everything one label photo yielded."""

    nutrition: NutritionData
    raw_ocr: str

    @property
    def is_label(self) -> bool:
        """True when the photo produced usable nutrition data."""
        if not self.raw_ocr.strip():
            return False
        if self.nutrition.item_name == NOT_A_LABEL:
            return False
        return any(
            value is not None
            for value in (
                self.nutrition.serving_value,
                self.nutrition.calories,
                self.nutrition.protein,
                self.nutrition.carbs,
                self.nutrition.fat,
            )
        )


async def extract_nutrition(
    image_bytes: bytes, client: Client | None = None
) -> Extraction:
    """Extract nutrition data from a nutrition-label photo.

    Accepts a Gemini client so callers (and tests) can inject a fake;
    lazily creates the real one when omitted.
    """
    gemini = client or _get_client()

    raw_ocr = await _ocr_image(gemini, image_bytes)
    if not raw_ocr.strip():
        logger.info("OCR returned no text — skipping normalisation")
        return Extraction(nutrition=_no_data(), raw_ocr="")

    data = await _normalize_ocr(gemini, raw_ocr)
    nutrition = NutritionData.from_gemini_dict(data)
    logger.info("Extraction result: %s", nutrition)
    return Extraction(nutrition=nutrition, raw_ocr=raw_ocr)


async def _ocr_image(gemini: Client, image_bytes: bytes) -> str:
    image = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
    response = gemini.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[OCR_PROMPT, image],
    )
    text = (response.text or "").strip()
    logger.info("OCR extracted %d chars", len(text))
    return text


async def _normalize_ocr(gemini: Client, raw_ocr: str) -> dict:
    prompt = (
        "Extract nutrition info from this OCR text (likely a food label photo).\n"
        "Return ONLY a JSON object with these keys. "
        "Use null for any field you cannot find.\n\n"
        "Keys:\n"
        '- "item_name": product name as a string, or null.\n'
        '- "serving_value": numeric serving size (e.g. 100, 15, 1.5) '
        "as a number, or null.\n"
        '- "serving_unit": unit string — one of g, ml, mg, kg, oz, lb — or null.\n'
        '- "calories": number, or null.\n'
        '- "protein": grams of protein as a number, or null.\n'
        '- "carbs": grams of carbs as a number, or null.\n'
        '- "fat": grams of fat as a number, or null.\n\n'
        "Rules:\n"
        '- Prefer the "per serving" column if both serving and 100g '
        "columns are present.\n"
        '- Look for patterns like "Calories 120", "Energy 120 kcal", '
        '"Protein 5g".\n'
        '- If serving size says "1 packet (30g)", serving_value=30, serving_unit="g".\n'
        "- If the OCR text is garbled, not a nutrition label, or you cannot "
        "extract any meaningful data, "
        f'return all nulls AND set item_name to "{NOT_A_LABEL}".\n'
        "- Output raw JSON only — no markdown fences, no explanation.\n\n"
        f"OCR Text:\n{raw_ocr}"
    )

    logger.debug("Sending %d chars to Gemini:\n%s", len(raw_ocr), raw_ocr)

    response = gemini.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
    )

    text = (response.text or "").strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
        text = text.strip()

    result = json.loads(text)
    logger.info("Gemini raw result: %s", result)
    return result


def _no_data() -> NutritionData:
    return NutritionData(
        item_name="Unknown",
        serving_value=None,
        serving_unit=None,
        calories=None,
        protein=None,
        carbs=None,
        fat=None,
    )
