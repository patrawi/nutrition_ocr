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

- `config.py` — Environment variables and API clients (loaded at import time)
- `models.py` — `NutritionData` dataclass and `parse_serving_size` parser
- `ocr.py` — Gemini OCR (`ocr_image`)
- `normalizer.py` — Gemini extraction (`normalize_ocr`)
- `sheets.py` — Google Sheets auth and append logic (`append_nutrition_row`)
- `main.py` — Telegram handlers and pipeline wiring

### Pipeline Flow

1. **Photo Handler** (`handle_photo` in `main.py`) — Downloads photo
2. **OCR** (`ocr.ocr_image`) — Gemini vision OCR returns transcribed plain text
3. **Normalization** (`normalizer.normalize_ocr`) — Gemini extracts JSON with keys: `item_name`, `serving_value`, `serving_unit`, `calories`, `protein`, `carbs`, `fat`
4. **Model building** (`models.NutritionData.from_gemini_dict`) — Parses Gemini JSON; falls back to parsing `per_unit` if Gemini returns the old combined format
5. **Storage** (`sheets.append_nutrition_row`) — Appends a 10-column row to the first worksheet

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

- Preserve the global credential caching pattern in `sheets.py` (`_google_creds`, `_gspread_client`).
- `normalize_ocr` strips markdown code fences from Gemini output before parsing JSON — preserve this logic.
- `append_nutrition_row` uses `value_input_option="USER_ENTERED"` — keep this so numbers parse correctly in Sheets.
- `parse_serving_size` handles strings like `"100g"`, `"100ml"`, `"15 g"` and falls back gracefully on unparseable input.

### Critical Gemini OCR Gotchas

- **Migrated from Mistral OCR (Oct 2026)**: Mistral's free tier changed, so the OCR stage now uses the same `google-genai` client and `GEMINI_MODEL` as the normalizer — one API key, one SDK.
- **Model ID**: defaults to `gemini-3.8-flash`, overridable via the `GEMINI_MODEL` env var (both OCR and normalization share it).
- **Image parts must use typed models**: pass `types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")` — do not pass raw dicts.
- **`response.text` can be `None`**: `ocr_image` coalesces it to `""` so the empty-text guard in `handle_photo` still fires.
- **No test suite existed until recently** — linting is configured; tests live under `tests/`.

### Critical Gemini Normalization Gotcha

- Gemini may return integers (e.g., `{"calories": 100}`) instead of strings. `NutritionData.from_gemini_dict` coerces values with `str()` before stripping — preserve this when modifying the parser.
