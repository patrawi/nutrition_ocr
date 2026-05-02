"""Mistral OCR service."""

from __future__ import annotations

import base64
import logging

import config

logger = logging.getLogger(__name__)


async def ocr_image(image_bytes: bytes) -> str:
    """Send an image to Mistral OCR and return the raw markdown text."""
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{encoded}"

    ocr_response = config.mistral_client.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "image_url", "image_url": data_uri},
    )

    logger.info("Mistral OCR response type: %s", type(ocr_response))
    logger.info("Mistral OCR response attrs: %s", dir(ocr_response))
    if hasattr(ocr_response, "pages"):
        logger.info("Mistral OCR pages count: %s", len(ocr_response.pages))
        for i, page in enumerate(ocr_response.pages):
            logger.info("Page %s type: %s, attrs: %s", i, type(page), dir(page))
    else:
        logger.warning("Mistral OCR response has no 'pages' attr")

    return "\n".join(page.markdown for page in ocr_response.pages)
