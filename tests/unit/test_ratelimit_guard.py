"""The guard that keeps integration tests polite must itself work."""

from __future__ import annotations

import httpx
import pytest

from google_scholar_search_mcp.rate_limiter import RateLimiter

from ..ratelimit_guard import RateLimitGuard


def _fetch(url: str) -> int:
    """Send a request that never touches the network."""
    transport = httpx.MockTransport(lambda request: httpx.Response(200))
    with httpx.Client(transport=transport) as client:
        return client.get(url).status_code


@pytest.fixture
def guard(monkeypatch: pytest.MonkeyPatch) -> RateLimitGuard:
    g = RateLimitGuard(min_delay=0.1)
    g.install(monkeypatch)
    return g


async def test_requests_through_the_limiter_are_clean(guard: RateLimitGuard) -> None:
    limiter = RateLimiter(min_delay=0.1, max_delay=0.12)

    await limiter.execute(_fetch, "https://scholar.google.com/scholar?q=a")
    await limiter.execute(_fetch, "https://scholar.google.com/scholar?q=b")

    assert guard.requests_seen == 2
    assert len(guard.permits) == 2
    assert guard.problems() == []


async def test_request_outside_the_limiter_is_flagged(guard: RateLimitGuard) -> None:
    _fetch("https://scholar.google.com/scholar?q=a")

    assert any("unthrottled" in p for p in guard.problems())


async def test_other_hosts_are_ignored(guard: RateLimitGuard) -> None:
    _fetch("https://example.com/")

    assert guard.requests_seen == 0
    assert guard.problems() == []


async def test_too_small_a_gap_is_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    strict = RateLimitGuard(min_delay=5)
    strict.install(monkeypatch)
    fast = RateLimiter(min_delay=0, max_delay=0)

    await fast.execute(_fetch, "https://scholar.google.com/a")
    await fast.execute(_fetch, "https://scholar.google.com/b")

    assert any("below the 5.00s minimum" in p for p in strict.problems())


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("get_bibtex", {}),
        ("get_paper_details", {}),
        ("get_citations", {}),
        ("search_author", {}),
    ],
)
async def test_invalid_arguments_are_rejected_before_the_limiter(
    guard: RateLimitGuard, tool: str, args: dict
) -> None:
    from mcp.client import Client

    from google_scholar_search_mcp import server

    async with Client(server.mcp) as client:
        result = await client.call_tool(tool, args)

    assert result.is_error
    assert guard.permits == []  # no delay was spent on a call that cannot succeed
