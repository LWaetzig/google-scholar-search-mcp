"""Detect Google Scholar's soft blocks.

Scholar rarely answers with a clean error. From a flagged client it redirects
to a JavaScript "Verifying..." page (``/sgsync``) or to the Google sign-in
page, both with HTTP 200, so ``scholarly`` parses them and silently finds zero
results. This module watches the final URL of every Scholar response and
remembers a block for a cooldown period, so callers can fail fast instead of
retrying into the wall.
"""

from __future__ import annotations

import threading
import time
import weakref
from typing import Any

import httpx

from .session_identity import apply_identity
from .throttle import throttle

SCHOLAR_HOST = "scholar.google.com"
_SIGN_IN_HOST = "accounts.google.com"
_VERIFY_PATH = "/sgsync"

_detectors: weakref.WeakSet[BlockDetector] = weakref.WeakSet()
_install_lock = threading.Lock()
_installed = False


def classify(response: httpx.Response) -> str | None:
    """Say whether a response is a block page.

    Args:
        response (httpx.Response): Final response, after redirects.

    Returns:
        str | None: Human-readable reason, or ``None`` for a normal response.
    """
    if response.status_code == 429:
        return "HTTP 429 Too Many Requests"
    if response.url.host == _SIGN_IN_HOST:
        return "redirected to the Google sign-in page"
    if response.url.path.startswith(_VERIFY_PATH):
        return "JavaScript bot verification (google.com/sgsync)"
    return None


def _install() -> None:
    """Patch ``httpx.Client.send`` once so detectors see Scholar responses.

    ``scholarly`` offers no request or response hook and hides the final URL,
    so this is the narrowest place to add the configured browser identity
    (:mod:`.session_identity`), to space requests (:mod:`.throttle`) and to
    look at the outcome. Requests to other
    hosts pass through untouched.
    """
    global _installed
    with _install_lock:
        if _installed:
            return
        original = httpx.Client.send

        def send(client: httpx.Client, request: httpx.Request, **kwargs: Any):
            apply_identity(request)
            if request.url.host != SCHOLAR_HOST:
                return original(client, request, **kwargs)
            throttle.wait()
            try:
                response = original(client, request, **kwargs)
            finally:
                throttle.mark()
            reason = classify(response)
            for detector in list(_detectors):
                detector._observe(reason)
            return response

        httpx.Client.send = send  # type: ignore[method-assign,assignment]
        _installed = True


class BlockDetector:
    """Track whether Scholar is currently blocking this client."""

    def __init__(self, cooldown_seconds: float = 900.0) -> None:
        """Create a detector and start watching Scholar traffic.

        Args:
            cooldown_seconds (float): How long to treat Scholar as blocked
                after a block was seen. ``0`` disables the cooldown.
        """
        self.cooldown_seconds = cooldown_seconds
        self._reason: str | None = None
        self._blocked_until = 0.0
        self._lock = threading.Lock()
        _detectors.add(self)
        _install()

    def _observe(self, reason: str | None) -> None:
        """Record a response classification.

        Args:
            reason (str | None): Block reason, or ``None`` for a normal response.
        """
        if reason is None:
            return
        with self._lock:
            self._reason = reason

    def reset(self) -> None:
        """Forget the block seen during the previous call."""
        with self._lock:
            self._reason = None

    @property
    def reason(self) -> str | None:
        """Reason of a block seen since the last :meth:`reset`, if any."""
        with self._lock:
            return self._reason

    def trip(self) -> None:
        """Start the cooldown after a confirmed block."""
        with self._lock:
            self._blocked_until = time.monotonic() + self.cooldown_seconds

    def cooldown_remaining(self) -> float:
        """Seconds left until Scholar should be tried again.

        Returns:
            float: ``0.0`` when Scholar may be tried.
        """
        with self._lock:
            return max(0.0, self._blocked_until - time.monotonic())
