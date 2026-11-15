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
