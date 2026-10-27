"""NutriTracker — Telegram bot that extracts nutrition data from food-label photos.

Pipeline: Photo → Label extraction (Gemini OCR + normalisation) → Pending Entry →
user confirms → Google Sheets
"""

from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from typing import NamedTuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

import config
from access import gate
from extraction import extract_nutrition
from pending import CORRECTABLE_FIELDS, PendingEntries
from ratelimit import RateLimiter
from sheets import append_nutrition_row

logging.basicConfig(
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

pending_entries = PendingEntries()
rate_limiter = RateLimiter()


class EditSession(NamedTuple):
    entry_id: str
    field: str
    summary_message_id: int


# One field-edit in progress per chat (F2)
active_edits: dict[int, EditSession] = {}


FIELD_LABELS = {
    "item_name": "ชื่อสินค้า",
    "serving": "ปริมาณต่อหน่วย",
    "calories": "แคลอรี่",
    "protein": "โปรตีน",
    "carbs": "คาร์บ",
    "fat": "ไขมัน",
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — greet the user and explain usage."""
    await update.message.reply_text(
        "👋 Welcome to *NutriTracker*!\n\n"
        "Send me a photo of a food nutrition label and I'll:\n"
        "1️⃣  Extract the text (Gemini OCR)\n"
        "2️⃣  Parse the nutrition facts (Gemini)\n"
        "3️⃣  Show you a summary to check before saving\n\n"
        "Just snap a photo, check the numbers, tap ✅ บันทึก!",
        parse_mode="Markdown",
    )


def _summary_text(entry_id: str, nutrition, raw_ocr_len: int) -> str:
    return (
        f"📋 *บันทึกนี้ใช่ไหม?*\n\n"
        f"*{nutrition.item_name}*\n{nutrition.format_summary()}\n\n"
        f"_{raw_ocr_len} chars OCR_ · `{entry_id}`"
    )


def _confirm_keyboard(entry_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ บันทึก", callback_data=f"p:{entry_id}:save"),
                InlineKeyboardButton("✏️ แก้ค่า", callback_data=f"p:{entry_id}:edit"),
            ],
            [InlineKeyboardButton("❌ ยกเลิก", callback_data=f"p:{entry_id}:cancel")],
        ]
    )


def _edit_menu_keyboard(entry_id: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(FIELD_LABELS[f], callback_data=f"f:{entry_id}:{f}"),
            InlineKeyboardButton(FIELD_LABELS[g], callback_data=f"f:{entry_id}:{g}"),
        ]
        for f, g in zip(CORRECTABLE_FIELDS[::2], CORRECTABLE_FIELDS[1::2])
    ]
    rows.append([InlineKeyboardButton("↩️ กลับ", callback_data=f"p:{entry_id}:back")])
    return InlineKeyboardMarkup(rows)


def _back_keyboard(entry_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ กลับ", callback_data=f"p:{entry_id}:back")]]
    )


def _expired_text() -> str:
    return "⌛ รายการนี้หมดอายุแล้ว ถ่ายใหม่ได้เลย 📸"


async def _render_summary(query, entry) -> None:
    await query.edit_message_text(
        _summary_text(
            entry.id, entry.extraction.nutrition, len(entry.extraction.raw_ocr)
        ),
        reply_markup=_confirm_keyboard(entry.id),
        parse_mode="Markdown",
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pipeline: throttle → download → extract → Pending Entry → confirm."""
    photo_time = datetime.now()

    # ── Throttle the expensive path before paying for anything ─────────
    allowed, retry = rate_limiter.check(update.effective_user.id)
    if not allowed:
        minutes = max(1, round(retry.total_seconds() / 60))
        await update.message.reply_text(
            f"⏳ ช้าๆหน่อยน้องพี่ตามไม่ทัน ลองใหม่ในอีก ~{minutes} นาทีนะ"
        )
        return

    if pending_entries.full():
        await update.message.reply_text(
            "📦 ค้างอยู่เยอะแล้วนะ กด ✅ หรือ ❌ รายการเก่าก่อน แล้วค่อยถ่ายใหม่"
        )
        return

    await update.message.reply_text("📷 Got your photo! Processing…")

    # ── Download the highest-resolution photo ────────────────────────────
    try:
        photo_file = await update.message.photo[-1].get_file()
        buffer = BytesIO()
        await photo_file.download_to_memory(buffer)
        image_bytes = buffer.getvalue()
        buffer.close()
    except Exception:
        logger.exception("Failed to download photo")
        await update.message.reply_text("❌ รับรูปไม่สำเร็จ ลองส่งใหม่อีกครั้งนะ")
        return

    # ── Extract (OCR + normalise + label guard behind one interface) ────
    try:
        extraction = await extract_nutrition(image_bytes)
    except Exception:
        logger.exception("Label extraction failed")
        await update.message.reply_text("❌ อ่านฉลากไม่สำเร็จ ลองถ่ายใหม่ให้ภาพชัดกว่านี้นะ 📸")
        return

    if not extraction.is_label:
        await update.message.reply_text(
            "⚠️ Could not extract nutrition data from this image. "
            "Make sure it's a clear photo of a nutrition facts label."
        )
        return

    # ── Pending Entry: nothing is saved until the user confirms ─────────
    entry_id = pending_entries.create(
        extraction, photo_time, chat_id=update.effective_chat.id
    )
    await update.message.reply_text(
        _summary_text(entry_id, extraction.nutrition, len(extraction.raw_ocr)),
        reply_markup=_confirm_keyboard(entry_id),
        parse_mode="Markdown",
    )


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route confirm-keyboard presses: save / edit menu / cancel / back."""
    query = update.callback_query
    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != "p":
        await query.answer()
        return
    entry_id, action = parts[1], parts[2]

    if action == "cancel":
        await query.answer()
        entry = pending_entries.get(entry_id)
        if entry is None or entry.chat_id != update.effective_chat.id:
            await query.edit_message_text(_expired_text())
            return
        pending_entries.remove(entry_id)
        await query.edit_message_text("❌ ยกเลิกแล้ว")
        return

    entry = pending_entries.get(entry_id)
    if entry is None or entry.chat_id != update.effective_chat.id:
        await query.answer()
        await query.edit_message_text(_expired_text())
        return

    if action == "save":
        await query.answer()
        try:
            append_nutrition_row(
                entry.extraction.nutrition,
                entry.extraction.raw_ocr,
                timestamp=entry.photo_time,
            )
            pending_entries.remove(entry_id)
            logger.info("Row appended to Google Sheet (confirmed %s)", entry_id)
            await query.edit_message_text(
                f"✅ บันทึก *{entry.extraction.nutrition.item_name}* เรียบร้อย!\n\n"
                f"{entry.extraction.nutrition.format_summary()}",
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception("Google Sheets write failed")
            await query.edit_message_text("❌ บันทึกไม่สำเร็จ ลองกดบันทึกใหม่อีกครั้งนะ")

    elif action == "edit":
        if update.effective_chat.id in active_edits:
            await query.answer("กำลังแก้รายการอื่นอยู่ จบอันนี้ก่อนนะ", show_alert=True)
            return
        await query.answer()
        await query.edit_message_text(
            "✏️ แก้ค่าไหน?", reply_markup=_edit_menu_keyboard(entry_id)
        )

    elif action == "back":
        session = active_edits.get(update.effective_chat.id)
        if session is not None and session.entry_id == entry_id:
            active_edits.pop(update.effective_chat.id, None)
        await query.answer()
        await _render_summary(query, entry)


async def handle_field_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User picked which field to correct — arm the one-edit-per-chat session."""
    query = update.callback_query
    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != "f":
        await query.answer()
        return
    entry_id, field = parts[1], parts[2]
    if field not in CORRECTABLE_FIELDS:
        await query.answer()
        return

    chat_id = update.effective_chat.id
    if chat_id in active_edits:
        await query.answer("กำลังแก้รายการอื่นอยู่ จบอันนี้ก่อนนะ", show_alert=True)
        return

    entry = pending_entries.get(entry_id)
    if entry is None or entry.chat_id != update.effective_chat.id:
        await query.answer()
        await query.edit_message_text(_expired_text())
        return

    await query.answer()
    active_edits[chat_id] = EditSession(entry_id, field, query.message.message_id)
    await query.edit_message_text(
        f"✏️ พิมพ์ค่าใหม่สำหรับ *{FIELD_LABELS[field]}* "
        f"(ปัจจุบัน: {_current_value(entry, field)})\n"
        f"พิมพ์ข้อความตอบกลับมาได้เลย",
        reply_markup=_back_keyboard(entry_id),
        parse_mode="Markdown",
    )


def _current_value(entry, field: str) -> str:
    n = entry.extraction.nutrition
    if field == "item_name":
        return n.item_name
    if field == "serving":
        return f"{n.serving_value or '?'}{n.serving_unit or ''}"
    return getattr(n, field) or "?"


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive the Correction for an armed field-edit, then re-render summary."""
    chat_id = update.effective_chat.id
    session = active_edits.get(chat_id)
    if session is None:
        return

    entry = pending_entries.get(session.entry_id)
    if entry is None:
        active_edits.pop(chat_id, None)
        await update.message.reply_text(_expired_text())
        return

    if not pending_entries.apply_correction(
        session.entry_id, session.field, update.message.text
    ):
        await update.message.reply_text(
            f"🤔 ค่าไม่เข้าใจ ลองพิมพ์ใหม่สำหรับ *{FIELD_LABELS[session.field]}* "
            f"(ปริมาณเช่น `100g` หรือ `250`)",
            parse_mode="Markdown",
        )
        return

    active_edits.pop(chat_id, None)
    summary = _summary_text(
        session.entry_id, entry.extraction.nutrition, len(entry.extraction.raw_ocr)
    )
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=session.summary_message_id,
            text=summary,
            reply_markup=_confirm_keyboard(session.entry_id),
            parse_mode="Markdown",
        )
    except BadRequest:
        logger.info("Summary message gone — replying a fresh one")
        await update.message.reply_text(
            summary,
            reply_markup=_confirm_keyboard(session.entry_id),
            parse_mode="Markdown",
        )


def main() -> None:
    """Build and run the Telegram bot."""
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # Gatekeeper runs before every handler; strangers are dropped silently.
    app.add_handler(TypeHandler(Update, gate), group=-1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_button, pattern=r"^p:"))
    app.add_handler(CallbackQueryHandler(handle_field_pick, pattern=r"^f:"))

    logger.info("🚀 NutriTracker bot is running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
