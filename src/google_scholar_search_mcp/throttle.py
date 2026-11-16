"""Spacing between individual HTTP requests to Google Scholar.

One tool call can send several requests (a title lookup searches first and then
fetches the record; ``scholarly`` also retries internally). Spacing whole tool
calls would let those requests go out back to back, which is exactly the burst
pattern Scholar's bot detection looks for. This throttle sits at the HTTP layer
(see :mod:`.block_detector`) and spaces every request instead.
"""

from __future__ import annotations

import random
import threading
import time


class RequestThrottle:
    """Make consecutive requests wait a random delay, measured from the last reply.

    Requests are also serialized: :meth:`wait` takes a slot that only
    :meth:`mark` gives back, so two threads can never have a request in flight
    at the same time.
    """

    def __init__(self, min_delay: float = 0.0, max_delay: float = 0.0) -> None:
        """Create a throttle.

        Args:
            min_delay (float): Minimum seconds between one request finishing
                and the next starting. ``0`` together with ``max_delay=0``
                disables spacing.
            max_delay (float): Maximum seconds; the actual delay is random in
                ``[min_delay, max_delay]``.
        """
        self._slot = threading.Lock()
        self._state = threading.Lock()
        self._finished = 0.0
        self.min_delay = min_delay
        self.max_delay = max_delay

    def configure(self, min_delay: float, max_delay: float) -> None:
        """Change the delays.

        Args:
            min_delay (float): Minimum seconds between requests.
            max_delay (float): Maximum seconds between requests.
        """
        with self._state:
            self.min_delay = min_delay
            self.max_delay = max(min_delay, max_delay)

    def reset(self) -> None:
        """Forget when the last request finished (the next one goes at once)."""
        with self._state:
            self._finished = 0.0

    def wait(self) -> None:
        """Take the request slot, sleeping until the next request may be sent.

        Must be paired with :meth:`mark`, in a ``try``/``finally``. Concurrent
        callers queue up on the slot, so their requests go out one after another.
        """
        self._slot.acquire()
        try:
            with self._state:
                delay = random.uniform(self.min_delay, self.max_delay)
                finished = self._finished
            remaining = finished + delay - time.monotonic()
            if remaining > 0 and finished > 0:
                time.sleep(remaining)
        except BaseException:
            self._slot.release()
            raise

    def mark(self) -> None:
        """Record that the request finished and give the slot back."""
        with self._state:
            self._finished = time.monotonic()
        self._slot.release()


throttle = RequestThrottle()
