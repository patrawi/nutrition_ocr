"""Gemini OCR service."""

from __future__ import annotations

import logging

from google.genai import types

import config

logger = logging.getLogger(__name__)

OCR_PROMPT = (
    "You are an OCR engine. Transcribe every piece of text visible in this "
    "image exactly as written, preserving reading order, numbers and units. "
    "The image is likely a photo of a food nutrition label. "
    "Output the transcription as plain text only — no commentary, no markdown."
)


async def ocr_image(image_bytes: bytes) -> str:
    """Send an image to Gemini Flash and return the raw transcribed text."""
    image = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

    response = config.gemini_client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[OCR_PROMPT, image],
    )

    text = (response.text or "").strip()
    logger.info("OCR extracted %d chars", len(text))
    return text
