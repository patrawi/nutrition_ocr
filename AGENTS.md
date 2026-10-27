# AGENTS.md

This file provides guidance to the AI agent when working with code in this repository.

## Project Overview

NutriTracker is a Telegram bot that extracts nutrition data from food-label photos and logs them to Google Sheets. Pipeline: Photo → Gemini OCR → Gemini AI → Google Sheets.

## Environment Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in required API keys
3. Google Sheets requires either:
   - Local: `GOOGLE_SHEETS_CREDENTIALS=path/to/credentials.json` (service account file)
   - Railway/Cloud: `GOOGLE_CREDENTIALS_JSON` (raw JSON string of service account)

## Running the Bot

```bash
python3 main.py
```

The bot uses `python-telegram-bot` and runs via polling (not webhooks) by default.

## Code Style & Linting

- Use **Ruff** for linting and formatting. Run: `ruff check .` and `ruff format .`
- Target Python 3.12+ (configured in `pyproject.toml`)
- Run tests with: `pytest`
- Dev dependencies: `pip install -r requirements-dev.txt`

## Architecture

The app is split into focused modules:

- `config.py` — Environment variables (loaded at import time; no clients created here)
- `access.py` — Gatekeeper: `gate(update, context)` drops updates not from an Authorized User (silent drop + INFO log). Registered as a group -1 `TypeHandler` so it runs before every handler.
- `ratelimit.py` — `RateLimiter.check(user_id)` sliding-window limiter (10/hour + 3/min burst, injected clock) guarding the photo seam.
- `models.py` — `NutritionData` dataclass and `parse_serving_size` parser
- `extraction.py` — Label extraction deep module: `extract_nutrition(image_bytes, client=None)` → `Extraction` (`nutrition`, `raw_ocr`, `is_label`). Hides both Gemini round-trips (vision OCR + JSON extraction), markdown fence stripping, and the not-a-label guard. The Gemini client is accepted at the interface (injectable for tests) and lazily created when omitted.
- `pending.py` — Pending Entry store: `PendingEntries.create/get/remove/apply_correction`. In-memory only, silent lazy expiry (default 1h TTL, clock injectable). `Correction` validates: `serving` goes through `parse_serving_size` and is rejected without a number; other fields must be non-empty.
- `sheets.py` — Google Sheets auth and append logic (`append_nutrition_row`)
- `main.py` — Telegram handlers and pipeline wiring (Telegram concerns only)

### Pipeline Flow

1. **Photo Handler** (`handle_photo` in `main.py`) — Captures `photo_time` (this becomes the row's Date/Time), downloads photo
2. **Extraction** (`extraction.extract_nutrition`) — Gemini vision OCR returns transcribed text, then Gemini extracts JSON with keys: `item_name`, `serving_value`, `serving_unit`, `calories`, `protein`, `carbs`, `fat`; builds `NutritionData` and exposes `is_label` (a computed property: False on empty OCR, the `NOT_A_LABEL` sentinel, or all-null data)
3. **Guard** (`main.py` checks `extraction.is_label`) — Rejects non-label photos before storage
4. **Pending Entry** (`main.py` + `pending.py`) — Summary + inline keyboard ([✅ บันทึก] [✏️ แก้ค่า] [❌ ยกเลิก]); nothing reaches the Sheet until the user confirms. Multiple pendings stack independently (keyed by id); field-edits are one-per-chat (`active_edits`, F2 rule)
5. **Save** (`sheets.append_nutrition_row(data, raw_ocr, timestamp=photo_time)`) — Appends a 10-column row on explicit ✅ only

### Google Sheets Column Order (10 columns)

1. วันที่ลงบันทึก (Date)
2. เวลาที่ลงบันทึก (Time)
3. รายการ (Product)
4. ปริมาณต่อหน่วย (Serving Value)
5. หน่วย (Serving Unit)
6. แคลอรี่ (Calories)
7. โปรตีน (Protein)
8. คาร์บ (Carbs)
9. ไขมัน (Fat)
10. รายละเอียดที่แปลงภาพ (Raw OCR)

### Important Implementation Details

- **Security posture**: fail-closed `AUTHORIZED_USER_IDS` gate; unauthorized updates are dropped silently (never replied); guard state (allowlist, rate limits, pending entries) is in-memory by design. Pending Entries are bound to their chat — wrong-chat button presses answer the same "expired" message. User-less updates (e.g. channel posts) count as unauthorized.
- Preserve the global credential caching pattern in `sheets.py` (`_google_creds`, `_gspread_client`) and the lazy Gemini client in `extraction.py` (`_client`).
- `_normalize_ocr` in `extraction.py` strips markdown code fences from Gemini output before parsing JSON — preserve this logic.
- `append_nutrition_row` uses `value_input_option="USER_ENTERED"` — keep this so numbers parse correctly in Sheets.
- `parse_serving_size` handles strings like `"100g"`, `"100ml"`, `"15 g"` and falls back gracefully on unparseable input.

### Critical Gemini Extraction Gotchas

- **Migrated from Mistral OCR (Oct 2026)**: Mistral's free tier changed, so both stages (vision OCR + JSON extraction) live in `extraction.py` and share one `google-genai` client and `GEMINI_MODEL` — one API key, one SDK.
- **Model ID**: defaults to `gemini-3.8-flash`, overridable via the `GEMINI_MODEL` env var (both stages share it).
- **Image parts must use typed models**: pass `types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")` — do not pass raw dicts.
- **`response.text` can be `None`**: both stages coalesce it to `""`; empty OCR short-circuits and skips the normalisation call.
- **The Gemini client is injectable**: `extract_nutrition(image_bytes, client=None)` — tests inject a `MagicMock`; do not reintroduce a module-global client in `config.py`.
- **No test suite existed until recently** — linting is configured; tests live under `tests/`.

### Critical Gemini Normalization Gotcha

- Gemini may return integers (e.g., `{"calories": 100}`) instead of strings. `NutritionData.from_gemini_dict` coerces values with `str()` before stripping — preserve this when modifying the parser.
