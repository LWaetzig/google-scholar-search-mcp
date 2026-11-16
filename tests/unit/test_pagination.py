"""Paging through search results and citations at the tool level."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from google_scholar_search_mcp import server
from google_scholar_search_mcp.cache import TTLCache
from google_scholar_search_mcp.errors import ScholarInvalidArgumentError
from google_scholar_search_mcp.models import PaperResult


def _papers(n: int) -> list[PaperResult]:
    return [PaperResult(title=f"P{i}") for i in range(n)]


@pytest.fixture
def rig(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setattr(server, "cache", TTLCache(60, 50))
    scholar = MagicMock()
    limiter = MagicMock()

    async def execute(func, *args, **kwargs):
        kwargs.pop("max_retries", None)
        return func(*args, **kwargs)

    limiter.execute = AsyncMock(side_effect=execute)
    monkeypatch.setattr(server, "scholar", scholar)
    monkeypatch.setattr(server, "limiter", limiter)
    return scholar


async def test_a_full_page_points_to_the_next_one(rig: MagicMock) -> None:
    rig.search_pubs.return_value = _papers(10)

    first = await server.search_papers("x", max_results=10)

    assert (first.offset, first.next_offset) == (0, 10)
    assert rig.search_pubs.call_args.kwargs["offset"] == 0


async def test_following_the_next_offset_fetches_the_next_page(rig: MagicMock) -> None:
    rig.search_pubs.return_value = _papers(10)
    first = await server.search_papers("x")
    assert first.next_offset is not None

    second = await server.search_papers("x", offset=first.next_offset)

    assert rig.search_pubs.call_args.kwargs["offset"] == 10
    assert (second.offset, second.next_offset) == (10, 20)


async def test_a_short_page_is_the_last_one(rig: MagicMock) -> None:
    rig.search_pubs.return_value = _papers(3)

    result = await server.search_papers("x", max_results=10, offset=20)

    assert result.next_offset is None
    assert result.total_results == 3


async def test_an_empty_page_is_a_normal_answer(rig: MagicMock) -> None:
    rig.search_pubs.return_value = []

    result = await server.search_papers("x", offset=40)

    assert result.papers == [] and result.next_offset is None


async def test_pages_are_cached_separately(rig: MagicMock) -> None:
    rig.search_pubs.return_value = _papers(10)

    await server.search_papers("x")
    await server.search_papers("x", offset=10)
    await server.search_papers("x", offset=10)

    assert rig.search_pubs.call_count == 2


async def test_negative_offsets_count_as_zero(rig: MagicMock) -> None:
    rig.search_pubs.return_value = _papers(10)

    result = await server.search_papers("x", offset=-5)

    assert result.offset == 0


@pytest.mark.parametrize(("offset", "size"), [(1000, 10), (995, 10), (5000, 1)])
async def test_paging_past_scholars_limit_is_rejected_without_a_request(
    rig: MagicMock, offset: int, size: int
) -> None:
    with pytest.raises(ScholarInvalidArgumentError, match="first 1000"):
        await server.search_papers("x", max_results=size, offset=offset)
    with pytest.raises(ScholarInvalidArgumentError, match="first 1000"):
        await server.get_citations("T", max_results=size, offset=offset)

    rig.search_pubs.assert_not_called()
    rig.get_citations.assert_not_called()


async def test_the_last_page_before_the_limit_has_no_next(rig: MagicMock) -> None:
    rig.search_pubs.return_value = _papers(10)

    result = await server.search_papers("x", max_results=10, offset=990)

    assert result.next_offset is None


async def test_citation_pages_stop_at_the_known_total(rig: MagicMock) -> None:
    rig.get_citations.return_value = ("T", 25, _papers(10))

    first = await server.get_citations("T", max_results=10)
    second = await server.get_citations("T", max_results=10, offset=10)
    rig.get_citations.return_value = ("T", 20, _papers(10))
    exact = await server.get_citations("Other", max_results=10, offset=10)

    assert (first.offset, first.next_offset) == (0, 10)
    assert second.next_offset == 20
    assert rig.get_citations.call_args_list[1].kwargs["offset"] == 10
    assert exact.next_offset is None  # 10 + 10 reaches the total of 20


async def test_citation_pages_continue_when_the_total_is_unknown(
    rig: MagicMock,
) -> None:
    rig.get_citations.return_value = (None, None, _papers(5))

    full = await server.get_citations(scholar_id="1", max_results=5)
    rig.get_citations.return_value = (None, None, _papers(2))
    short = await server.get_citations(scholar_id="1", max_results=5, offset=5)

    assert full.next_offset == 5
    assert short.next_offset is None


async def test_bulk_search_always_returns_first_pages(rig: MagicMock) -> None:
    rig.search_pubs.return_value = _papers(5)

    result = await server.bulk_search(["a"], max_results_per_query=5)

    assert rig.search_pubs.call_args.kwargs["offset"] == 0
    assert result.results[0].offset == 0
    assert result.results[0].next_offset == 5  # continue with search_papers
