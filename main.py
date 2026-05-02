"""NutriTracker — Telegram bot that extracts nutrition data from food-label photos.

Pipeline: Photo → Mistral OCR → Gemini AI → Google Sheets
"""

from __future__ import annotations

import json
import logging
from io import BytesIO

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from models import NutritionData
from normalizer import normalize_ocr
from ocr import ocr_image
from sheets import append_nutrition_row

logging.basicConfig(
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — greet the user and explain usage."""
    await update.message.reply_text(
        "👋 Welcome to *NutriTracker*!\n\n"
        "Send me a photo of a food nutrition label and I'll:\n"
        "1️⃣  Extract the text (Mistral OCR)\n"
        "2️⃣  Parse the nutrition facts (Gemini)\n"
        "3️⃣  Save everything to your Google Sheet\n\n"
        "Just snap a photo and send it! 📸",
        parse_mode="Markdown",
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pipeline: download → OCR → normalise → store → reply."""
    await update.message.reply_text("📷 Got your photo! Processing…")

    # ── Step 0: Download the highest-resolution photo ────────────────────
    try:
        photo_file = await update.message.photo[-1].get_file()
        buffer = BytesIO()
        await photo_file.download_to_memory(buffer)
        image_bytes = buffer.getvalue()
        buffer.close()
    except Exception as exc:
        logger.exception("Failed to download photo")
        await update.message.reply_text(f"❌ Could not download your photo: {exc}")
        return

    # ── Step 1: OCR via Mistral ──────────────────────────────────────────
    try:
        raw_ocr = await ocr_image(image_bytes)
        if not raw_ocr.strip():
            await update.message.reply_text(
                "⚠️ OCR returned empty text. Is this a clear nutrition label?"
            )
            return
        logger.info("OCR succeeded (%d chars)", len(raw_ocr))
    except Exception as exc:
        logger.exception("Mistral OCR failed")
        await update.message.reply_text(f"❌ OCR failed: {exc}")
        return

    # ── Step 2: Normalise via Gemini ─────────────────────────────────────
    try:
        gemini_dict = await normalize_ocr(raw_ocr)
        nutrition = NutritionData.from_gemini_dict(gemini_dict)
        logger.info("Gemini normalisation result: %s", nutrition)
    except json.JSONDecodeError:
        logger.exception("Gemini returned invalid JSON")
        await update.message.reply_text(
            "❌ Could not parse nutrition data — Gemini returned invalid JSON."
        )
        return
    except Exception as exc:
        logger.exception("Gemini normalisation failed")
        await update.message.reply_text(f"❌ Normalisation failed: {exc}")
        return

    # ── Step 3: Save to Google Sheets ────────────────────────────────────
    try:
        append_nutrition_row(nutrition, raw_ocr)
        logger.info("Row appended to Google Sheet")
    except Exception as exc:
        logger.exception("Google Sheets write failed")
        await update.message.reply_text(f"❌ Failed to save to Google Sheets: {exc}")
        return

    # ── Step 4: Feedback ─────────────────────────────────────────────────
    await update.message.reply_text(
        f"✅ Saved *{nutrition.item_name}*!\n{nutrition.format_summary()}",
        parse_mode="Markdown",
    )


def main() -> None:
    """Build and run the Telegram bot."""
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("🚀 NutriTracker bot is running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
