"""Tests for the Pending Entry store."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from extraction import Extraction
from models import NutritionData
from pending import PendingEntries

T0 = datetime(2026, 10, 19, 12, 0, 0)


def _extraction(**overrides) -> Extraction:
    nutrition = NutritionData(
        item_name=overrides.get("item_name", "Test Bar"),
        serving_value=overrides.get("serving_value", "100"),
        serving_unit=overrides.get("serving_unit", "g"),
        calories=overrides.get("calories", "120"),
        protein=overrides.get("protein", "5"),
        carbs=overrides.get("carbs", "20"),
        fat=overrides.get("fat", "3"),
    )
    return Extraction(nutrition=nutrition, raw_ocr="Energy 120 kcal")


def _store(
    now: datetime = T0, ttl_seconds: int = 3600, capacity: int = 20
) -> tuple[PendingEntries, list[datetime]]:
    clock_values: list[datetime] = [now]

    def clock() -> datetime:
        return clock_values[-1]

    return (
        PendingEntries(clock=clock, ttl_seconds=ttl_seconds, capacity=capacity),
        clock_values,
    )


def test_create_then_get_roundtrips_entry() -> None:
    store, _ = _store()

    entry_id = store.create(_extraction(), photo_time=T0, chat_id=1)
    entry = store.get(entry_id)

    assert entry is not None
    assert entry.id == entry_id
    assert entry.extraction.nutrition.item_name == "Test Bar"
    assert entry.photo_time == T0


def test_get_unknown_id_returns_none() -> None:
    store, _ = _store()

    assert store.get("nope") is None


def test_remove_drops_entry() -> None:
    store, _ = _store()
    entry_id = store.create(_extraction(), photo_time=T0, chat_id=1)

    store.remove(entry_id)

    assert store.get(entry_id) is None


def test_remove_unknown_id_is_noop() -> None:
    store, _ = _store()

    store.remove("nope")


def test_entry_expires_after_ttl() -> None:
    store, clock_values = _store(now=T0, ttl_seconds=3600)
    entry_id = store.create(_extraction(), photo_time=T0, chat_id=1)

    clock_values[0] = T0 + timedelta(seconds=3600)
    assert store.get(entry_id) is not None

    clock_values[0] = T0 + timedelta(seconds=3601)
    assert store.get(entry_id) is None


def test_correction_updates_nutrition_field() -> None:
    store, _ = _store()
    entry_id = store.create(_extraction(), photo_time=T0, chat_id=1)

    assert store.apply_correction(entry_id, "calories", " 300 ") is True

    entry = store.get(entry_id)
    assert entry is not None
    assert entry.extraction.nutrition.calories == "300"


def test_correction_with_unknown_field_is_rejected() -> None:
    store, _ = _store()
    entry_id = store.create(_extraction(), photo_time=T0, chat_id=1)

    assert store.apply_correction(entry_id, "vitamin_c", "99") is False


def test_correction_on_expired_entry_is_rejected() -> None:
    store, clock_values = _store(now=T0, ttl_seconds=3600)
    entry_id = store.create(_extraction(), photo_time=T0, chat_id=1)
    clock_values[0] = T0 + timedelta(seconds=3601)

    assert store.apply_correction(entry_id, "calories", "300") is False


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("100g", "100", "g"),
        ("15 ml", "15", "ml"),
        ("250", "250", None),
    ],
)
def test_serving_correction_parses_value_and_unit(
    text: str, value: str | None, unit: str | None
) -> None:
    store, _ = _store()
    entry_id = store.create(_extraction(), photo_time=T0, chat_id=1)

    assert store.apply_correction(entry_id, "serving", text) is True

    entry = store.get(entry_id)
    assert entry is not None
    assert entry.extraction.nutrition.serving_value == value
    assert entry.extraction.nutrition.serving_unit == unit


def test_serving_correction_without_number_is_rejected() -> None:
    store, _ = _store()
    entry_id = store.create(_extraction(), photo_time=T0, chat_id=1)

    assert store.apply_correction(entry_id, "serving", "one packet") is False

    entry = store.get(entry_id)
    assert entry is not None
    assert entry.extraction.nutrition.serving_value == "100"


def test_empty_item_name_correction_is_rejected() -> None:
    store, _ = _store()
    entry_id = store.create(_extraction(), photo_time=T0, chat_id=1)

    assert store.apply_correction(entry_id, "item_name", "   ") is False


def test_multiple_entries_are_independent() -> None:
    store, _ = _store()
    first = store.create(_extraction(item_name="First"), photo_time=T0, chat_id=1)
    second = store.create(_extraction(item_name="Second"), photo_time=T0, chat_id=1)

    store.apply_correction(first, "calories", "999")

    entry = store.get(second)
    assert entry is not None
    assert entry.extraction.nutrition.calories == "120"


def test_entry_binds_to_creating_chat() -> None:
    store, _ = _store()

    entry_id = store.create(_extraction(), photo_time=T0, chat_id=777)

    entry = store.get(entry_id)
    assert entry is not None
    assert entry.chat_id == 777


def test_full_reports_capacity() -> None:
    store, _ = _store(capacity=2)

    assert not store.full()
    store.create(_extraction(), photo_time=T0, chat_id=1)
    assert not store.full()
    store.create(_extraction(), photo_time=T0, chat_id=1)
    assert store.full()


def test_expired_entries_free_capacity() -> None:
    store, clock_values = _store(capacity=1)
    store.create(_extraction(), photo_time=T0, chat_id=1)
    assert store.full()

    clock_values[0] = T0 + timedelta(seconds=3601)

    assert not store.full()
