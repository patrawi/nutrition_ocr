# 🥗 NutriTracker Bot

A Telegram bot that extracts nutrition data from food-label photos and logs it to Google Sheets — powered by **Mistral OCR** and **Gemini AI**.

## How It Works

```
📸 Photo → 🔍 Mistral OCR 3 → 🤖 Gemini 3.0 Flash → 📊 Google Sheets
```

1. Send a photo of a nutrition label to the bot on Telegram
2. **Mistral OCR** extracts raw text from the image
3. **Gemini** parses structured nutrition data (calories, protein, carbs, fat, serving size)
4. The data is saved to your **Google Sheet** automatically

### Google Sheet Columns

| # | Column | Description |
|---|--------|-------------|
| 1 | วันที่ลงบันทึก | Date recorded |
| 2 | เวลาที่ลงบันทึก | Time recorded |
| 3 | รายการ | Product name |
| 4 | ต่อหน่วย g/ml | Serving size |
| 5 | แคลอรี่ | Calories |
| 6 | โปรตีน | Protein (g) |
| 7 | คาร์บ | Carbs (g) |
| 8 | ไขมัน | Fat (g) |
| 9 | รายละเอียดที่แปลงภาพ | Raw OCR text |

## Tech Stack

- **Python 3.12+**
- **[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)** — Telegram Bot API
- **[Mistral AI](https://mistral.ai/)** — OCR (image → text)
- **[Google Gemini](https://ai.google.dev/)** — AI text parsing (text → structured JSON)
- **[gspread](https://github.com/burnash/gspread)** — Google Sheets API

## Setup

### 1. Clone & install

```bash
git clone <your-repo-url>
cd food_tracker_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Get API keys

| Service | Where to get it |
|---------|----------------|
| Telegram Bot Token | [@BotFather](https://t.me/BotFather) on Telegram |
| Mistral API Key | [console.mistral.ai](https://console.mistral.ai/) |
| Gemini API Key | [aistudio.google.com](https://aistudio.google.com/apikey) |
| Google Service Account | [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts) → Create key (JSON) |

### 3. Set up Google Sheets

1. Create a new Google Spreadsheet
2. Copy the **Spreadsheet ID** from the URL (`https://docs.google.com/spreadsheets/d/{THIS_PART}/edit`)
3. Share the spreadsheet with your service account email (found in `credentials.json` → `client_email`)

### 4. Configure environment

Create a `.env` file:

```env
TELEGRAM_TOKEN=your_telegram_bot_token
MISTRAL_API_KEY=your_mistral_api_key
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_SHEETS_CREDENTIALS=credentials.json
GOOGLE_SHEETS_ID=your_spreadsheet_id
```

### 5. Run

```bash
python3 main.py
```

## Deploy to Railway

1. Push your code to GitHub (make sure `.env` and `credentials.json` are in `.gitignore`)
2. Create a new project on [Railway](https://railway.app/)
3. Connect your GitHub repo
4. Add these **environment variables** in Railway's dashboard:

| Variable | Value |
|----------|-------|
| `TELEGRAM_TOKEN` | Your bot token |
| `MISTRAL_API_KEY` | Your Mistral key |
| `GEMINI_API_KEY` | Your Gemini key |
| `GOOGLE_SHEETS_ID` | Your spreadsheet ID |
| `GOOGLE_CREDENTIALS_JSON` | Entire `credentials.json` content as a single-line JSON string |

> **Note:** On Railway, use `GOOGLE_CREDENTIALS_JSON` (raw JSON string) instead of `GOOGLE_SHEETS_CREDENTIALS` (file path). The bot auto-detects which one is set.

To get the single-line JSON string:

```bash
cat credentials.json | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)))" | pbcopy
```

## Project Structure

```
food_tracker_bot/
├── main.py              # Bot logic (handlers, OCR, Gemini, Sheets)
├── requirements.txt     # Python dependencies
├── credentials.json     # Google service account key (not committed)
├── .env                 # Environment variables (not committed)
├── .gitignore           # Git ignore rules
└── README.md            # This file
```

## License

MIT
