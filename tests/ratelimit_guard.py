"""Verify that every request to Google Scholar goes through the rate limiter.

Used by the integration suite so that the live tests are as polite as the real
server. The guard watches two things:

* **No bypass:** an HTTP request to ``scholar.google.com`` must be issued from
  inside ``RateLimiter.execute``. Detected with a ``ContextVar`` that
  ``asyncio.to_thread`` copies into the worker thread.
* **Spacing:** consecutive limiter permits are at least ``min_delay`` apart.

Problems are *collected*, not raised: ``scholarly`` swallows exceptions inside
its retry loop, which would turn a violation into a misleading "blocked" skip.
"""

from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest
import requests

from google_scholar_search_mcp.rate_limiter import RateLimiter

SCHOLAR_HOST = "scholar.google.com"


class RateLimitGuard:
    """Record limiter permits and Scholar requests, and report violations."""

    def __init__(self, min_delay: float, tolerance: float = 0.05) -> None:
        """Create a guard.

        Args:
            min_delay (float): Minimum seconds the limiter must keep between
                two requests (``GS_MIN_DELAY``).
            tolerance (float): Allowed timing jitter in seconds.
        """
        self.min_delay = min_delay
        self.tolerance = tolerance
        self.permits: list[float] = []
        self.requests_seen = 0
        self.violations: list[str] = []
        self._inside: ContextVar[bool] = ContextVar("inside_limiter", default=False)

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Patch the limiter and the HTTP clients.

        Args:
            monkeypatch (pytest.MonkeyPatch): Undoes the patches on teardown.
        """
        guard = self
        orig_execute = RateLimiter.execute
        orig_wait = RateLimiter._wait
        orig_httpx_send = httpx.Client.send
        orig_requests_send = requests.Session.send

        async def execute(limiter: RateLimiter, *args: Any, **kwargs: Any) -> Any:
            token = guard._inside.set(True)
            try:
                return await orig_execute(limiter, *args, **kwargs)
            finally:
                guard._inside.reset(token)

        async def wait(limiter: RateLimiter) -> None:
            await orig_wait(limiter)
            guard.permits.append(time.monotonic())

        def httpx_send(client: httpx.Client, request: httpx.Request, **kw: Any):
            guard._note_request(request.url.host, str(request.url))
            return orig_httpx_send(client, request, **kw)

        def requests_send(session: requests.Session, request: Any, **kw: Any):
            guard._note_request(urlsplit(request.url).hostname, request.url)
            return orig_requests_send(session, request, **kw)

        monkeypatch.setattr(RateLimiter, "execute", execute)
        monkeypatch.setattr(RateLimiter, "_wait", wait)
        monkeypatch.setattr(httpx.Client, "send", httpx_send)
        monkeypatch.setattr(requests.Session, "send", requests_send)

    def _note_request(self, host: str | None, url: str) -> None:
        """Record a request and flag it if it bypassed the limiter.

        Args:
            host (str | None): Host of the request.
            url (str): Full URL, for the report.
        """
        if host != SCHOLAR_HOST:
            return
        self.requests_seen += 1
        if not self._inside.get():
            self.violations.append(f"unthrottled request to Scholar: {url[:120]}")

    def problems(self) -> list[str]:
        """Return everything wrong so far.

        Returns:
            list[str]: Bypassed requests and permits spaced closer than
            ``min_delay``; empty when the limiter was respected.
        """
        found = list(self.violations)
        floor = self.min_delay - self.tolerance
        for earlier, later in zip(self.permits, self.permits[1:], strict=False):
            if later - earlier < floor:
                found.append(
                    f"requests {later - earlier:.2f}s apart, below the "
                    f"{self.min_delay:.2f}s minimum"
                )
        return found
