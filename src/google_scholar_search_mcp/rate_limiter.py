from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable
from typing import Any

from scholarly import MaxTriesExceededException

logger = logging.getLogger(__name__)


class ScholarRateLimitError(Exception):
    """Raised when Google Scholar blocks or throttles requests after retries."""


class RateLimiter:
    """Serializes requests with a random delay and retries on rate limiting."""

    def __init__(self, min_delay: float = 5.0, max_delay: float = 15.0) -> None:
        """Create a rate limiter.

        Args:
            min_delay (float): Minimum seconds between two requests.
            max_delay (float): Maximum seconds between two requests.
        """
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> Any:
        """Run a blocking function in a thread, throttled and with retries.

        Args:
            func (Callable[..., Any]): Blocking callable to execute.
            *args (Any): Positional arguments for ``func``.
            max_retries (int): Retries after a rate-limit error, with
                exponential backoff (default 3).
            **kwargs (Any): Keyword arguments for ``func``.

        Returns:
            Any: Whatever ``func`` returns.

        Raises:
            ScholarRateLimitError: If Scholar keeps blocking or throttling
                the request after all retries.
            Exception: Any other error raised by ``func`` is re-raised.
        """
        for attempt in range(max_retries + 1):
            await self._wait()
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            
            except MaxTriesExceededException:
                
                raise ScholarRateLimitError(
                    "Google Scholar is blocking requests. "
                    "Try again later or configure a proxy via GS_PROXY_TYPE."
                )
            except Exception as e:
                if "DOSException" in type(e).__name__ or "429" in str(e):
                    if attempt < max_retries:
                        backoff = min(10 * (2**attempt), 120)
                        logger.warning(
                            "Rate limited (attempt %d/%d), backing off %.0fs",
                            attempt + 1,
                            max_retries,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    raise ScholarRateLimitError(
                        "Google Scholar rate limit exceeded after retries. "
                        "Configure a proxy via GS_PROXY_TYPE or try later."
                    )
                raise

        raise ScholarRateLimitError("Max retries exceeded.")

    async def _wait(self) -> None:
        """Sleep until a random delay has passed since the previous request.

        Returns:
            None: Resolves once the caller may send its request.
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            delay = random.uniform(self._min_delay, self._max_delay)
            remaining = delay - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_request_time = time.monotonic()
