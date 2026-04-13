# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

## Project Overview

**NutriTracker** is a Telegram bot that extracts nutrition data from food-label photos and logs them to Google Sheets. The pipeline is: Photo → Mistral OCR → Gemini AI → Google Sheets.

## Environment Setup

1. Install dependencies: `pip install -r requirements.txt`
   - **Important**: `mistralai` is pinned to `>=1.0.0,<2.0.0` because v2.x has breaking API changes (import paths changed)
2. Copy `.env.example` to `.env` and fill in required API keys
3. Google Sheets requires either:
   - Local: `GOOGLE_SHEETS_CREDENTIALS=path/to/credentials.json` (service account file)
   - Railway/Cloud: `GOOGLE_CREDENTIALS_JSON` (raw JSON string of service account)

## Running the Bot

```bash
python3 main.py
```

The bot uses `python-telegram-bot` and runs via polling (not webhooks) by default.

## Architecture

The entire application lives in `main.py` (~270 lines) with these key components:

### Pipeline Flow

1. **Photo Handler** (`handle_photo`) — Receives photos from Telegram users
2. **OCR** (`_ocr_image`) — Sends image to Mistral OCR (`mistral-ocr-latest`), returns raw markdown text
3. **Normalization** (`_normalise`) — Sends OCR text to Gemini (`gemini-3-flash-preview`) to extract structured JSON: `item_name`, `per_unit`, `calories`, `protein`, `carbs`, `fat`
4. **Storage** (`_append_to_sheet`) — Appends row to Google Sheet with 9 columns (date, time, item name, serving size, calories, protein, carbs, fat, raw OCR text)

### Global State

- `_google_creds` — Cached Google service account credentials (lazy-initialized)
- `_gspread_client` — Cached gspread Spreadsheet handle (lazy-initialized)
- `mistral_client` / `gemini_client` — Module-level AI clients

### Telegram Handlers

- `/start` command → `start()` — Welcome message
- `filters.PHOTO` → `handle_photo()` — Main processing pipeline

### Error Handling

Each pipeline step has its own try/except block with user-facing error messages. Failed steps short-circuit the pipeline.

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | All bot logic (handlers, OCR, Gemini, Sheets) |
| `requirements.txt` | Python dependencies |
| `.env.example` | Required environment variables |
| `.gitignore` | Excludes `.env`, `credentials.json`, `venv/` |

## External Services

| Service | Library | Purpose |
|---------|---------|---------|
| Telegram Bot API | `python-telegram-bot` | User interface |
| Mistral OCR | `mistralai` | Image-to-text extraction |
| Google Gemini | `google-genai` | Structured data parsing |
| Google Sheets | `gspread` + `google-auth` | Data storage |
