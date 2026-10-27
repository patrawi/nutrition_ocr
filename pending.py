"""Pending Entry store: extractions waiting for the user's confirm-or-discard.

In-memory only — if the bot restarts, pending entries are gone (accepted
trade-off). Entries expire silently after the TTL; expiry is checked lazily
on access, so no background timer exists. Each entry is bound to the chat
that created it, and the store holds at most `capacity` live entries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from uuid import uuid4

from extraction import Extraction
from models import parse_serving_size

logger = logging.getLogger(__name__)

CORRECTABLE_FIELDS = ("item_name", "serving", "calories", "protein", "carbs", "fat")


@dataclass
class PendingEntry:
    """One Extraction awaiting the user's decision, with the time it was shot."""

    id: str
    chat_id: int
    extraction: Extraction
    photo_time: datetime
    created_at: datetime


class PendingEntries:
    def __init__(
        self,
        clock: Callable[[], datetime] = datetime.now,
        ttl_seconds: int = 3600,
        capacity: int = 20,
    ) -> None:
        self._clock = clock
        self._ttl = timedelta(seconds=ttl_seconds)
        self._capacity = capacity
        self._entries: dict[str, PendingEntry] = {}

    def full(self) -> bool:
        """True when no new Pending Entry fits; check before expensive work."""
        self._expire(self._clock())
        return len(self._entries) >= self._capacity

    def create(self, extraction: Extraction, photo_time: datetime, chat_id: int) -> str:
        entry_id = uuid4().hex[:12]
        self._entries[entry_id] = PendingEntry(
            id=entry_id,
            chat_id=chat_id,
            extraction=extraction,
            photo_time=photo_time,
            created_at=self._clock(),
        )
        return entry_id

    def get(self, entry_id: str) -> PendingEntry | None:
        self._expire(self._clock())
        return self._entries.get(entry_id)

    def remove(self, entry_id: str) -> None:
        self._entries.pop(entry_id, None)

    def apply_correction(self, entry_id: str, field: str, value: str) -> bool:
        """Replace one field of a live entry; False for expired/unknown/invalid."""
        entry = self.get(entry_id)
        if entry is None or field not in CORRECTABLE_FIELDS:
            return False

        text = value.strip()
        if not text:
            return False

        nutrition = entry.extraction.nutrition
        if field == "serving":
            parsed_value, parsed_unit = parse_serving_size(text)
            if parsed_value is None:
                return False
            nutrition.serving_value = parsed_value
            nutrition.serving_unit = parsed_unit
        else:
            setattr(nutrition, field, text)

        logger.info("Corrected %s of pending entry %s", field, entry_id)
        return True

    def _expire(self, now: datetime) -> None:
        expired = [
            entry_id
            for entry_id, entry in self._entries.items()
            if now - entry.created_at > self._ttl
        ]
        for entry_id in expired:
            logger.info("Pending entry %s expired", entry_id)
            del self._entries[entry_id]
