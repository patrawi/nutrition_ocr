# NutriTracker

A Telegram bot that turns nutrition-label photos into rows in a Google Sheet.

## Language

**Label**:
A photo from which usable nutrition data can be extracted. A photo of anything else is not a Label.
_Avoid_: valid photo, good image

**Extraction**:
The structured nutrition data plus the raw OCR text produced from one photo.
_Avoid_: parse result, OCR output

**Pending Entry**:
An Extraction waiting for the user's confirm-or-discard decision. Not stored anywhere; if the bot restarts, Pending Entries are gone. An unanswered Pending Entry is discarded silently.
_Avoid_: draft, cache, session

**Correction**:
A user-supplied replacement value for one field of a Pending Entry, given before Save.
_Avoid_: edit, fix, override

**Save**:
Appending a confirmed row to the Google Sheet. Only happens on explicit user confirmation.
_Avoid_: log, write, commit
