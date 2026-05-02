"""Mistral OCR service."""

from __future__ import annotations

import base64
import logging

from mistralai.client.models import ImageURL, ImageURLChunk

import config

logger = logging.getLogger(__name__)


async def ocr_image(image_bytes: bytes) -> str:
    """Send an image to Mistral OCR and return the raw markdown text."""
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{encoded}"

    document = ImageURLChunk(
        type="image_url",
        image_url=ImageURL(url=data_uri),
    )

    ocr_response = config.mistral_client.ocr.process(
        model="mistral-ocr-latest",
        document=document,
    )

    logger.info("Mistral OCR pages count: %s", len(ocr_response.pages))
    for i, page in enumerate(ocr_response.pages):
        logger.info("Page %s markdown length: %s", i, len(page.markdown))
        logger.info("Page %s markdown preview: %s", i, page.markdown[:200])

    return "\n".join(page.markdown for page in ocr_response.pages)
