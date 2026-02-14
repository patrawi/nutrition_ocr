"""
NutriTracker — Telegram bot that extracts nutrition data from food-label photos.

Pipeline:  Photo → Mistral OCR 3 → Gemini 3.0 Flash → Google Sheets
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime
from io import BytesIO

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google import genai
from mistralai import Mistral
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ── Environment ──────────────────────────────────────────────────────────────
load_dotenv()

TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]
MISTRAL_API_KEY: str = os.environ["MISTRAL_API_KEY"]
GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]
GOOGLE_SHEETS_ID: str = os.environ["GOOGLE_SHEETS_ID"]

# ── Clients ──────────────────────────────────────────────────────────────────
mistral_client = Mistral(api_key=MISTRAL_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

GEMINI_MODEL = "gemini-3-flash-preview"

# ── Google Auth (shared) ─────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

_google_creds: ServiceAccountCredentials | None = None
_gspread_client: gspread.Client | None = None


def _get_google_creds() -> ServiceAccountCredentials:
    """Return cached service-account credentials (created once).

    Supports two modes:
      • Railway / cloud:  Set GOOGLE_CREDENTIALS_JSON env var with the raw JSON string.
      • Local dev:        Set GOOGLE_SHEETS_CREDENTIALS env var with the file path.
    """
    global _google_creds
    if _google_creds is None:
        json_str = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if json_str:
            # Railway: credentials stored as env var (raw JSON string)
            info = json.loads(json_str)
            _google_creds = ServiceAccountCredentials.from_service_account_info(
                info, scopes=SCOPES,
            )
        else:
            # Local dev: credentials stored as a file path
            creds_path = os.environ["GOOGLE_SHEETS_CREDENTIALS"]
            _google_creds = ServiceAccountCredentials.from_service_account_file(
                creds_path, scopes=SCOPES,
            )
    return _google_creds


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_sheets_client() -> gspread.Spreadsheet:
    """Return a cached gspread Spreadsheet handle (reuses connection)."""
    global _gspread_client
    if _gspread_client is None:
        _gspread_client = gspread.authorize(_get_google_creds())
    return _gspread_client.open_by_key(GOOGLE_SHEETS_ID)




async def _ocr_image(image_bytes: bytes) -> str:
    """Send an image to Mistral OCR 3 and return the raw markdown text."""
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{encoded}"
    del encoded  # free the duplicate string early

    ocr_response = mistral_client.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "image_url", "image_url": data_uri},
    )
    del data_uri  # free after API call

    # Collect text from every page / chunk returned by the API.
    return "\n".join(page.markdown for page in ocr_response.pages)


async def _normalise(raw_ocr: str) -> dict:
    """Ask Gemini 3.0 Flash to extract structured nutrition data from OCR text."""
    prompt = (
        "Analyze this OCR text from a nutrition label. "
        "Extract: Item Name (guess if missing), Per Unit (serving size in g or ml) always add unit to the value, "
        "Calories, Protein (g), Carbs (g), Fat (g). "
        "Return ONLY valid JSON with keys: "
        '"item_name", "per_unit", "calories", "protein", "carbs", "fat".\n\n'
        f"OCR Text:\n{raw_ocr}"
    )

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    text = response.text.strip()

    # Strip markdown code-fence if Gemini wraps the answer.
    if text.startswith("```"):
        text = text.split("\n", 1)[1]  # drop opening fence line
        text = text.rsplit("```", 1)[0]  # drop closing fence
        text = text.strip()

    return json.loads(text)


def _append_to_sheet(nutrition: dict, raw_ocr: str) -> None:
    """Append a nutrition row to the first worksheet of the target spreadsheet.

    Column order (9 columns):
        1. วันที่ลงบันทึก  (Added Date)
        2. เวลาที่ลงบันทึก  (Time)
        3. รายการ           (Product)
        4. ต่อหน่วย g/ml    (Per Unit)
        5. แคลอรี่          (Calories)
        6. โปรตีน           (Protein)
        7. คาร์บ            (Carbs)
        8. ไขมัน            (Fat)
        9. รายละเอียดที่แปลงภาพ (Full Detail / raw OCR)
    """
    now = datetime.now()
    row = [
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        nutrition.get("item_name", "Unknown"),
        nutrition.get("per_unit", ""),
        nutrition.get("calories", ""),
        nutrition.get("protein", ""),
        nutrition.get("carbs", ""),
        nutrition.get("fat", ""),
        raw_ocr,
    ]
    sheet = _get_sheets_client()
    worksheet = sheet.sheet1
    worksheet.append_row(row, value_input_option="USER_ENTERED")


# ── Handlers ─────────────────────────────────────────────────────────────────

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
        image_bytes: bytes = buffer.getvalue()
        buffer.close()  # free the BytesIO buffer immediately
    except Exception as exc:
        logger.exception("Failed to download photo")
        await update.message.reply_text(f"❌ Could not download your photo: {exc}")
        return

    # ── Step 1: OCR via Mistral ──────────────────────────────────────────
    try:
        raw_ocr = await _ocr_image(image_bytes)
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
        nutrition = await _normalise(raw_ocr)
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
        _append_to_sheet(nutrition, raw_ocr)
        logger.info("Row appended to Google Sheet")
    except Exception as exc:
        logger.exception("Google Sheets write failed")
        await update.message.reply_text(f"❌ Failed to save to Google Sheets: {exc}")
        return

    # ── Step 4: Feedback ─────────────────────────────────────────────────
    name = nutrition.get("item_name", "Unknown")
    unit = nutrition.get("per_unit", "?")
    cal = nutrition.get("calories", "?")
    pro = nutrition.get("protein", "?")
    carb = nutrition.get("carbs", "?")
    fat = nutrition.get("fat", "?")

    await update.message.reply_text(
        f"✅ Saved *{name}*!\n"
        f"📦 Per unit: {unit}\n"
        f"🔥 Cal: {cal}  |  🥩 P: {pro}g  |  🍞 C: {carb}g  |  🧈 F: {fat}g",
        parse_mode="Markdown",
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    """Build and run the Telegram bot."""
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("🚀 NutriTracker bot is running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
