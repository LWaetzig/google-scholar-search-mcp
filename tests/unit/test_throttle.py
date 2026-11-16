from __future__ import annotations

import threading
import time

import httpx

from google_scholar_search_mcp.block_detector import BlockDetector
from google_scholar_search_mcp.throttle import RequestThrottle, throttle


def test_the_first_request_goes_at_once_and_later_ones_wait() -> None:
    t = RequestThrottle(0.1, 0.1)

    start = time.monotonic()
    t.wait()
    t.mark()
    first = time.monotonic() - start
    t.wait()
    second = time.monotonic() - start

    assert first < 0.05
    assert second >= 0.09


def test_the_delay_is_measured_from_the_end_of_the_previous_request() -> None:
    t = RequestThrottle(0.1, 0.1)
    t.wait()
    time.sleep(0.12)  # a slow request
    t.mark()

    start = time.monotonic()
    t.wait()
    t.mark()

    assert time.monotonic() - start >= 0.09


def test_zero_delays_never_wait() -> None:
    t = RequestThrottle(0, 0)
    start = time.monotonic()
    for _ in range(20):
        t.wait()
        t.mark()

    assert time.monotonic() - start < 0.1


def test_concurrent_callers_are_spaced_not_released_together() -> None:
    t = RequestThrottle(0.1, 0.1)
    t.wait()
    t.mark()
    stamps: list[float] = []

    def worker() -> None:
        t.wait()
        stamps.append(time.monotonic())
        t.mark()

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    stamps.sort()
    assert all(b - a >= 0.09 for a, b in zip(stamps, stamps[1:], strict=False))


def test_every_scholar_request_is_spaced_but_other_hosts_are_not() -> None:
    BlockDetector()  # installs the httpx hook
    throttle.configure(0.15, 0.15)
    sent: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(time.monotonic())
        return httpx.Response(200, text="ok")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        client.get("https://scholar.google.com/scholar?q=a")
        client.get("https://scholar.google.com/scholar?q=b")
        spaced = sent[1] - sent[0]
        client.get("https://example.com/")
        client.get("https://example.com/")
        unspaced = sent[3] - sent[2]

    assert spaced >= 0.14
    assert unspaced < 0.05


def test_a_failing_request_still_counts_for_spacing() -> None:
    BlockDetector()
    throttle.configure(0.1, 0.1)

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with httpx.Client(transport=httpx.MockTransport(boom)) as client:
        for _ in range(2):
            try:
                client.get("https://scholar.google.com/")
            except httpx.ConnectError:
                pass
        start = time.monotonic()
        try:
            client.get("https://scholar.google.com/")
        except httpx.ConnectError:
            pass

    assert time.monotonic() - start >= 0.09


def test_only_one_request_is_in_flight_at_a_time() -> None:
    t = RequestThrottle(0, 0)
    inside = 0
    peak = 0
    guard = threading.Lock()

    def worker() -> None:
        nonlocal inside, peak
        t.wait()
        with guard:
            inside += 1
            peak = max(peak, inside)
        time.sleep(0.02)
        with guard:
            inside -= 1
        t.mark()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert peak == 1
