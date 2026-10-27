"""Tests for the rate limiter."""

from __future__ import annotations

from datetime import datetime, timedelta

from ratelimit import RateLimiter

T0 = datetime(2026, 10, 27, 9, 0, 0)


def _limiter(
    hourly_limit: int = 10, burst_limit: int = 3
) -> tuple[RateLimiter, list[datetime]]:
    clock_values: list[datetime] = [T0]

    def clock() -> datetime:
        return clock_values[-1]

    return (
        RateLimiter(clock=clock, hourly_limit=hourly_limit, burst_limit=burst_limit),
        clock_values,
    )


def test_allows_up_to_burst_limit() -> None:
    limiter, _ = _limiter()

    for _ in range(3):
        allowed, _ = limiter.check(1)
        assert allowed

    allowed, retry = limiter.check(1)
    assert not allowed
    assert retry > timedelta(0)


def test_denied_call_is_not_counted() -> None:
    limiter, clock_values = _limiter(burst_limit=3)

    for _ in range(3):
        limiter.check(1)
    assert not limiter.check(1)[0]

    clock_values[0] = T0 + timedelta(seconds=61)
    assert limiter.check(1)[0]


def test_burst_window_slides_after_a_minute() -> None:
    limiter, clock_values = _limiter()

    for _ in range(3):
        assert limiter.check(1)[0]

    clock_values[0] = T0 + timedelta(seconds=60)
    assert limiter.check(1)[0]


def test_hourly_limit_trips_when_spread_out() -> None:
    limiter, clock_values = _limiter(hourly_limit=10, burst_limit=3)

    for minute in range(10):
        clock_values[0] = T0 + timedelta(minutes=minute)
        assert limiter.check(1)[0]

    clock_values[0] = T0 + timedelta(minutes=10)
    allowed, retry = limiter.check(1)
    assert not allowed
    assert retry <= timedelta(hours=1)


def test_hourly_window_slides_after_an_hour() -> None:
    limiter, clock_values = _limiter(hourly_limit=1, burst_limit=5)

    assert limiter.check(1)[0]
    assert not limiter.check(1)[0]

    clock_values[0] = T0 + timedelta(hours=1)
    assert limiter.check(1)[0]


def test_users_are_independent() -> None:
    limiter, _ = _limiter(burst_limit=2)

    assert limiter.check(1)[0]
    assert limiter.check(1)[0]
    assert not limiter.check(1)[0]
    assert limiter.check(2)[0]
