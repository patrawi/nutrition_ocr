"""Google Sheets storage service."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

import config
from models import NutritionData

logger = logging.getLogger(__name__)

_google_creds: ServiceAccountCredentials | None = None
_gspread_client: gspread.Client | None = None


def _get_google_creds() -> ServiceAccountCredentials:
    """Return cached service-account credentials (created once).

    Supports two modes:
      • Railway / cloud:  GOOGLE_CREDENTIALS_JSON env var (raw JSON string)
      • Local dev:          GOOGLE_SHEETS_CREDENTIALS env var (file path)
    """
    global _google_creds
    if _google_creds is None:
        json_str = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if json_str:
            info = json.loads(json_str)
            _google_creds = ServiceAccountCredentials.from_service_account_info(
                info,
                scopes=config.SCOPES,
            )
        else:
            creds_path = os.environ["GOOGLE_SHEETS_CREDENTIALS"]
            _google_creds = ServiceAccountCredentials.from_service_account_file(
                creds_path,
                scopes=config.SCOPES,
            )
    return _google_creds


def _get_sheets_client() -> gspread.Spreadsheet:
    """Return a cached gspread Spreadsheet handle (reuses connection)."""
    global _gspread_client
    if _gspread_client is None:
        _gspread_client = gspread.authorize(_get_google_creds())
    return _gspread_client.open_by_key(config.GOOGLE_SHEETS_ID)


def append_nutrition_row(data: NutritionData, raw_ocr: str) -> None:
    """Append a nutrition row to the first worksheet.

    Column order (10 columns):
        1. วันที่ลงบันทึก   (Date)
        2. เวลาที่ลงบันทึก   (Time)
        3. รายการ            (Product)
        4. ปริมาณต่อหน่วย     (Serving Value)
        5. หน่วย              (Serving Unit)
        6. แคลอรี่           (Calories)
        7. โปรตีน            (Protein)
        8. คาร์บ             (Carbs)
        9. ไขมัน             (Fat)
       10. รายละเอียดที่แปลงภาพ (Raw OCR)
    """
    now = datetime.now()
    row = [
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        data.item_name,
        data.serving_value or "",
        data.serving_unit or "",
        data.calories or "",
        data.protein or "",
        data.carbs or "",
        data.fat or "",
        raw_ocr,
    ]
    sheet = _get_sheets_client()
    worksheet = sheet.sheet1
    worksheet.append_row(row, value_input_option="USER_ENTERED")
