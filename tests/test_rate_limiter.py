import time

import pytest

from google_scholar_search_mcp.rate_limiter import RateLimiter, ScholarRateLimitError


@pytest.mark.asyncio
async def test_enforces_minimum_delay():
    rl = RateLimiter(min_delay=0.1, max_delay=0.2)
    call_times: list[float] = []

    def record_time():
        call_times.append(time.monotonic())
        return "ok"

    await rl.execute(record_time, max_retries=0)
    await rl.execute(record_time, max_retries=0)

    assert len(call_times) == 2
    elapsed = call_times[1] - call_times[0]
    assert elapsed >= 0.09  # Allow 10ms tolerance for CI variance


@pytest.mark.asyncio
async def test_successful_call_returns_value():
    rl = RateLimiter(min_delay=0.01, max_delay=0.02)
    result = await rl.execute(lambda: 42, max_retries=0)
    assert result == 42


@pytest.mark.asyncio
async def test_non_rate_limit_errors_propagate():
    def bad_func():
        raise ValueError("some other error")

    rl = RateLimiter(min_delay=0.01, max_delay=0.02)
    with pytest.raises(ValueError, match="some other error"):
        await rl.execute(bad_func, max_retries=3)


@pytest.mark.asyncio
async def test_retries_on_dos_exception():
    call_count = 0

    class MockDOSException(Exception):
        pass

    MockDOSException.__name__ = "DOSException"

    def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise MockDOSException("temporarily blocked")
        return "recovered"

    rl = RateLimiter(min_delay=0.01, max_delay=0.02)
    result = await rl.execute(flaky_func, max_retries=3)
    assert result == "recovered"
    assert call_count == 3


@pytest.mark.asyncio
async def test_gives_up_after_max_retries():
    class MockDOSException(Exception):
        pass

    MockDOSException.__name__ = "DOSException"

    def always_blocked():
        raise MockDOSException("permanently blocked")

    rl = RateLimiter(min_delay=0.01, max_delay=0.02)
    with pytest.raises(ScholarRateLimitError):
        await rl.execute(always_blocked, max_retries=2)
