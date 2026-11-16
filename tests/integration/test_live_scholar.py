"""Live Google Scholar checks. Run with ``pytest -m integration``.

Each test costs one or two Scholar requests (3-6 s apart). A block is reported
as a skip by the ``call`` fixture.
"""

from __future__ import annotations

import pytest

from .conftest import KNOWN_TITLE, CallTool, error_text


async def _skip_unless_scholar_answers(call: CallTool) -> None:
    """Skip unless Scholar returns results for a famous query.

    Without this, a silent block (empty results) is indistinguishable from a
    genuine "not found".
    """
    result = await call("search_papers", query=KNOWN_TITLE, max_results=1)
    data = result.structured_content
    if result.is_error or not data or data["total_results"] == 0:
        pytest.skip("Google Scholar returns no results for a famous query here")


async def test_search_papers(call: CallTool) -> None:
    await _skip_unless_scholar_answers(call)

    result = await call("search_papers", query=KNOWN_TITLE, max_results=3)

    assert not result.is_error, error_text(result)
    data = result.structured_content
    assert data is not None
    assert 1 <= data["total_results"] <= 3
    assert all(p["title"] for p in data["papers"])


async def test_get_paper_details(call: CallTool) -> None:
    result = await call("get_paper_details", title=KNOWN_TITLE)

    assert not result.is_error, error_text(result)
    data = result.structured_content
    assert data is not None
    assert "attention" in data["title"].lower()
    assert data["num_citations"] > 1000
    assert data["bibtex"]


async def test_get_bibtex(call: CallTool) -> None:
    result = await call("get_bibtex", title=KNOWN_TITLE)

    assert not result.is_error, error_text(result)
    assert "@" in error_text(result)


async def test_get_citations(call: CallTool) -> None:
    result = await call("get_citations", title=KNOWN_TITLE, max_results=2)

    assert not result.is_error, error_text(result)
    data = result.structured_content
    assert data is not None
    assert data["total_citations"] > 1000
    assert len(data["citations"]) == 2


async def test_search_author(call: CallTool) -> None:
    result = await call("search_author", name="Geoffrey Hinton", max_publications=2)

    assert not result.is_error, error_text(result)
    data = result.structured_content
    assert data is not None
    assert "hinton" in data["name"].lower()
    assert data["h_index"] > 50


async def test_unknown_title_returns_not_found(call: CallTool) -> None:
    await _skip_unless_scholar_answers(call)

    result = await call(
        "get_bibtex",
        title="zxqv unlikely nonexistent paper title 8f3k29dj1",
        expect_not_found=True,
    )

    assert result.is_error
    assert "[NOT_FOUND]" in error_text(result)


async def test_author_ids_chain_into_paper_tools(call: CallTool) -> None:
    """author -> scholar_id -> author again -> author_pub_id -> details/bibtex/citations."""
    await _skip_unless_scholar_answers(call)
    first = await call("search_author", name="Geoffrey Hinton", max_publications=1)
    assert not first.is_error, error_text(first)
    author = first.structured_content
    assert author and author["scholar_id"]

    by_id = await call(
        "search_author", scholar_id=author["scholar_id"], max_publications=1
    )
    assert not by_id.is_error, error_text(by_id)
    assert by_id.structured_content["scholar_id"] == author["scholar_id"]

    pub = by_id.structured_content["publications"][0]
    assert pub["author_pub_id"]

    details = await call("get_paper_details", author_pub_id=pub["author_pub_id"])
    assert not details.is_error, error_text(details)
    assert details.structured_content["title"]

    bibtex = await call("get_bibtex", author_pub_id=pub["author_pub_id"])
    assert not bibtex.is_error, error_text(bibtex)
    assert "@" in error_text(bibtex)


async def test_scholar_id_chains_from_search_into_citations(call: CallTool) -> None:
    await _skip_unless_scholar_answers(call)
    search = await call("search_papers", query=KNOWN_TITLE, max_results=1)
    paper = search.structured_content["papers"][0]
    if not paper["scholar_id"]:
        pytest.skip("search result carries no scholar_id")

    citations = await call(
        "get_citations", scholar_id=paper["scholar_id"], max_results=2
    )

    assert not citations.is_error, error_text(citations)
    data = citations.structured_content
    assert len(data["citations"]) == 2
    assert data["total_citations"] is None or data["total_citations"] > 1000


async def test_unknown_author_id_returns_not_found(call: CallTool) -> None:
    await _skip_unless_scholar_answers(call)

    result = await call(
        "search_author", scholar_id="zzzzzzzzzzzz", expect_not_found=True
    )

    assert result.is_error
    assert "[NOT_FOUND]" in error_text(result)
