from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from google_scholar_search_mcp.block_detector import BlockDetector, classify
from google_scholar_search_mcp.errors import ScholarBlockedError, ScholarNotFoundError
from google_scholar_search_mcp.scholar import ScholarClient

from .test_scholar import _fake_pub, _make_config


def _fake_google(blocked_by: str | None) -> httpx.Client:
    """An httpx client whose "Google" behaves like the real block pages."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "scholar.google.com":
            if blocked_by == "sgsync":
                return httpx.Response(
                    302, headers={"location": "https://www.google.com/sgsync?url=x"}
                )
            if blocked_by == "signin":
                return httpx.Response(
                    302,
                    headers={
                        "location": "https://accounts.google.com/v3/signin/identifier"
                    },
                )
            if blocked_by == "429":
                return httpx.Response(429)
        return httpx.Response(200, text="<html>ok</html>")

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def _get_scholar(blocked_by: str | None) -> None:
    with _fake_google(blocked_by) as client:
        client.get("https://scholar.google.com/scholar?q=x")


@pytest.mark.parametrize(
    ("blocked_by", "expected"),
    [("sgsync", "sgsync"), ("signin", "sign-in"), ("429", "429")],
)
def test_detects_each_block_signature(blocked_by: str, expected: str) -> None:
    detector = BlockDetector()

    _get_scholar(blocked_by)

    assert detector.reason is not None
    assert expected in detector.reason


def test_normal_responses_and_other_hosts_are_not_blocks() -> None:
    detector = BlockDetector()

    _get_scholar(None)
    with _fake_google("sgsync") as client:  # only Scholar's host is watched
        client.get("https://example.com/")

    assert detector.reason is None


def test_reset_clears_the_reason() -> None:
    detector = BlockDetector()
    _get_scholar("sgsync")

    detector.reset()

    assert detector.reason is None


def test_cooldown_starts_on_trip_and_can_be_disabled() -> None:
    detector = BlockDetector(cooldown_seconds=60)
    assert detector.cooldown_remaining() == 0
    detector.trip()
    assert 59 < detector.cooldown_remaining() <= 60

    disabled = BlockDetector(cooldown_seconds=0)
    disabled.trip()
    assert disabled.cooldown_remaining() == 0


def test_classify_ignores_ordinary_responses() -> None:
    request = httpx.Request("GET", "https://scholar.google.com/")
    assert classify(httpx.Response(200, request=request)) is None


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_empty_search_behind_a_block_page_is_blocked_not_empty(mock_scholarly) -> None:
    def blocked_search(*args, **kwargs):
        _get_scholar("sgsync")
        return iter([])

    mock_scholarly.search_pubs.side_effect = blocked_search
    client = ScholarClient(_make_config())

    with pytest.raises(ScholarBlockedError, match=r"\[BLOCKED\].*sgsync"):
        client.search_pubs("anything")


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_title_lookup_behind_a_block_page_is_blocked(mock_scholarly) -> None:
    def blocked_search(*args, **kwargs):
        _get_scholar("signin")
        return iter([])

    mock_scholarly.search_pubs.side_effect = blocked_search
    client = ScholarClient(_make_config())

    with pytest.raises(ScholarBlockedError):
        client.get_bibtex("anything")


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_empty_without_a_block_is_still_a_genuine_miss(mock_scholarly) -> None:
    mock_scholarly.search_pubs.return_value = iter([])
    client = ScholarClient(_make_config())

    with pytest.raises(ScholarNotFoundError):
        client.get_bibtex("really not a paper")
    mock_scholarly.search_pubs.return_value = iter([])
    assert client.search_pubs("no hits") == []


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_a_block_starts_the_cooldown_and_ensure_available_fails_fast(
    mock_scholarly,
) -> None:
    def blocked_search(*args, **kwargs):
        _get_scholar("sgsync")
        return iter([])

    mock_scholarly.search_pubs.side_effect = blocked_search
    client = ScholarClient(_make_config())
    client.ensure_available()  # fine before any block

    with pytest.raises(ScholarBlockedError):
        client.search_pubs("x")

    with pytest.raises(ScholarBlockedError, match="not retrying"):
        client.ensure_available()


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_the_block_flag_does_not_leak_into_the_next_call(mock_scholarly) -> None:
    calls = iter([True, False])

    def search(*args, **kwargs):
        if next(calls):
            _get_scholar("sgsync")
            return iter([])
        return iter([_fake_pub()])

    mock_scholarly.search_pubs.side_effect = search
    client = ScholarClient(_make_config())

    with pytest.raises(ScholarBlockedError):
        client.search_pubs("x")
    assert len(client.search_pubs("y")) == 1


async def test_server_fails_fast_without_spending_a_delay_during_the_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcp.client import Client

    from google_scholar_search_mcp import server

    server.scholar._detector.trip()
    try:
        async with Client(server.mcp) as client:
            result = await client.call_tool("search_papers", {"query": "x"})
    finally:
        server.scholar._detector._blocked_until = 0.0

    assert result.is_error
    assert "[BLOCKED]" in result.content[0].text  # type: ignore[union-attr]
    assert server.limiter._last_request_time == 0.0  # limiter never ran


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_a_block_with_cookies_configured_says_they_probably_expired(
    mock_scholarly,
) -> None:
    import dataclasses

    def blocked_search(*args, **kwargs):
        _get_scholar("sgsync")
        return iter([])

    mock_scholarly.search_pubs.side_effect = blocked_search
    client = ScholarClient(dataclasses.replace(_make_config(), cookies="NID=abc"))

    with pytest.raises(ScholarBlockedError, match="probably expired"):
        client.search_pubs("x")


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_a_block_without_cookies_suggests_configuring_them(mock_scholarly) -> None:
    def blocked_search(*args, **kwargs):
        _get_scholar("sgsync")
        return iter([])

    mock_scholarly.search_pubs.side_effect = blocked_search
    client = ScholarClient(_make_config())

    with pytest.raises(ScholarBlockedError, match="set-cookies"):
        client.search_pubs("x")
