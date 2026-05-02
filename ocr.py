"""Mistral OCR service."""

from __future__ import annotations

import base64

import config


async def ocr_image(image_bytes: bytes) -> str:
    """Send an image to Mistral OCR and return the raw markdown text."""
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{encoded}"

    ocr_response = config.mistral_client.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "image_url", "image_url": data_uri},
    )

    return "\n".join(page.markdown for page in ocr_response.pages)
