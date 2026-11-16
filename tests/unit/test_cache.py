from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from google_scholar_search_mcp import server
from google_scholar_search_mcp.cache import TTLCache, normalize
from google_scholar_search_mcp.errors import ScholarBlockedError
from google_scholar_search_mcp.models import PaperDetails, PaperResult


def test_returns_what_was_stored_and_counts_hits_and_misses() -> None:
    cache = TTLCache(60, 10)
    assert cache.get("k") is None
    cache.set("k", [1])

    assert cache.get("k") == [1]
    assert (cache.hits, cache.misses) == (1, 1)


def test_entries_expire(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(
        "google_scholar_search_mcp.cache.time.monotonic", lambda: now[0]
    )
    cache = TTLCache(60, 10)
    cache.set("k", "v")

    now[0] += 59
    assert cache.get("k") == "v"
    now[0] += 2
    assert cache.get("k") is None


def test_least_recently_used_entry_is_dropped() -> None:
    cache = TTLCache(60, 2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")
    cache.set("c", 3)

    assert cache.get("b") is None
    assert cache.get("a") == 1 and cache.get("c") == 3


def test_ttl_zero_disables_the_cache() -> None:
    cache = TTLCache(0, 10)
    cache.set("k", "v")

    assert not cache.enabled
    assert cache.get("k") is None


def test_normalize_ignores_case_and_spacing() -> None:
    assert normalize("  Attention   Is ALL you need ") == "attention is all you need"
    assert normalize(None) == ""


@pytest.fixture
def rig(monkeypatch: pytest.MonkeyPatch):
    """Server with a fresh cache and a scholar whose calls are counted."""
    monkeypatch.setattr(server, "cache", TTLCache(60, 50))
    scholar = MagicMock()
    scholar.search_pubs = MagicMock(return_value=[PaperResult(title="A")])
    scholar.get_paper_details = MagicMock(return_value=PaperDetails(title="A"))
    scholar.get_bibtex = MagicMock(return_value="@article{a}")
    scholar.get_citations = MagicMock(return_value=("A", 1, [PaperResult(title="C")]))
    limiter = MagicMock()

    async def execute(func, *args, **kwargs):
        kwargs.pop("max_retries", None)
        return func(*args, **kwargs)

    limiter.execute = AsyncMock(side_effect=execute)
    monkeypatch.setattr(server, "scholar", scholar)
    monkeypatch.setattr(server, "limiter", limiter)
    return scholar


async def test_a_repeated_search_does_not_reach_scholar(rig) -> None:
    first = await server.search_papers("Deep Learning")
    again = await server.search_papers("  deep   learning ")

    assert rig.search_pubs.call_count == 1
    assert again.papers == first.papers


async def test_different_parameters_are_different_searches(rig) -> None:
    await server.search_papers("x", max_results=5)
    await server.search_papers("x", max_results=6)
    await server.search_papers("x", max_results=5, year_from=2020)

    assert rig.search_pubs.call_count == 3


async def test_bulk_search_shares_the_cache_with_single_searches(rig) -> None:
    await server.search_papers("x", max_results=5)
    result = await server.bulk_search(["x", "y"], max_results_per_query=5)

    assert rig.search_pubs.call_count == 2  # "x" came from the cache
    assert result.completed_queries == 2


async def test_details_bibtex_and_citations_are_cached_by_id_or_title(rig) -> None:
    for _ in range(2):
        await server.get_paper_details("Some Title")
        await server.get_bibtex(scholar_id=" 123 ")
        await server.get_citations("Some Title", max_results=3)

    assert rig.get_paper_details.call_count == 1
    assert rig.get_bibtex.call_count == 1
    assert rig.get_citations.call_count == 1


async def test_an_id_and_a_title_are_not_mixed_up(rig) -> None:
    await server.get_bibtex("123")
    await server.get_bibtex(scholar_id="123")

    assert rig.get_bibtex.call_count == 2


async def test_errors_are_not_cached(rig) -> None:
    rig.search_pubs.side_effect = [
        ScholarBlockedError("blocked"),
        [PaperResult(title="A")],
    ]

    with pytest.raises(ScholarBlockedError):
        await server.search_papers("x")
    result = await server.search_papers("x")

    assert result.papers[0].title == "A"


async def test_cached_answers_are_served_even_while_scholar_is_blocked(rig) -> None:
    await server.search_papers("x")
    rig.ensure_available.side_effect = ScholarBlockedError("cooldown")

    result = await server.search_papers("x")

    assert result.total_results == 1
