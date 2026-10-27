"""Tests for the Gatekeeper."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from telegram.ext import ApplicationHandlerStop

import config
from access import gate


def _update(user_id: int | None) -> SimpleNamespace:
    user = SimpleNamespace(id=user_id) if user_id is not None else None
    return SimpleNamespace(effective_user=user)


def test_gate_allows_authorized_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "AUTHORIZED_USER_IDS", frozenset({42}))

    asyncio.run(gate(_update(42), None))


def test_gate_drops_unauthorized_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "AUTHORIZED_USER_IDS", frozenset({42}))

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(gate(_update(43), None))


def test_gate_drops_userless_update(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "AUTHORIZED_USER_IDS", frozenset({42}))

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(gate(_update(None), None))


def test_gate_drops_everyone_when_allowlist_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "AUTHORIZED_USER_IDS", frozenset())

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(gate(_update(42), None))
