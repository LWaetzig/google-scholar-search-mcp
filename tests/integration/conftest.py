"""Fixtures for integration tests.

These tests talk to the live Google Scholar service through the real MCP
protocol (in-memory client <-> the actual server object), so they exercise
tool registration, argument validation, rate limiting and error mapping.
Keep them few and cheap: Scholar blocks automated traffic.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Iterator
from typing import Any

import pytest
from mcp.client import Client
from mcp_types import CallToolResult

from ..ratelimit_guard import RateLimitGuard

# Must be set before the server module is imported: it reads Config at import.
# Deliberately NOT overriding GS_MIN_DELAY / GS_MAX_DELAY: the live tests use the
# same rate limiting as production (5-15 s), or whatever the caller configured.
os.environ.setdefault("GS_MAX_RETRIES", "1")
os.environ.setdefault("GS_SKILL_URL", "")

from google_scholar_search_mcp import server  # noqa: E402

KNOWN_TITLE = "Attention is all you need"

CallTool = Callable[..., Awaitable[CallToolResult]]


@pytest.fixture(scope="session", autouse=True)
def rate_limit_guard() -> Iterator[RateLimitGuard]:
    """Watch all Scholar traffic of the session.

    Yields:
        RateLimitGuard: Installed guard; patches are undone afterwards.
    """
    guard = RateLimitGuard(min_delay=server.config.min_delay_seconds)
    with pytest.MonkeyPatch.context() as mp:
        guard.install(mp)
        yield guard


@pytest.fixture(autouse=True)
def enforce_rate_limit(rate_limit_guard: RateLimitGuard) -> Iterator[None]:
    """Fail a test that sent Scholar traffic around or too fast for the limiter.

    Args:
        rate_limit_guard (RateLimitGuard): Session guard.

    Yields:
        None: Runs the test, then checks the guard.
    """
    yield
    problems = rate_limit_guard.problems()
    assert not problems, "rate limiting not respected:\n" + "\n".join(problems)


def error_text(result: CallToolResult) -> str:
    """Join the text blocks of a tool result.

    Args:
        result (CallToolResult): Result returned by the client.

    Returns:
        str: All text content, newline separated.
    """
    return "\n".join(getattr(block, "text", "") for block in result.content)


@pytest.fixture
def call() -> CallTool:
    """Return a tool caller that skips the test when Scholar blocks us.

    A CAPTCHA or throttle is an environment problem, not a regression. The
    in-memory client is opened per call because an anyio task group must be
    entered and exited in the same task, which pytest fixtures do not guarantee.

    Returns:
        CallTool: ``await call("tool", key=value)`` returning the raw result.
        Pass ``expect_not_found=True`` when ``[NOT_FOUND]`` is the outcome
        under test.
    """

    async def _call(
        tool: str, *, expect_not_found: bool = False, **arguments: Any
    ) -> CallToolResult:
        async with Client(server.mcp) as client:
            result = await client.call_tool(tool, arguments)
        text = error_text(result)
        # Scholar often blocks silently (sign-in redirect -> empty results),
        # so NOT_FOUND for a well-known paper also means "blocked here".
        blocked = ("[BLOCKED]", "[RATE_LIMITED]", "[NOT_FOUND]")
        if result.is_error and any(code in text for code in blocked):
            if not (expect_not_found and "[NOT_FOUND]" in text):
                pytest.skip(f"Google Scholar is blocking this environment: {text}")
        return result

    return _call
