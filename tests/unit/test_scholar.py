from unittest.mock import MagicMock, patch

import pytest

from google_scholar_search_mcp.config import Config, ProxyType
from scholarly.data_types import PublicationSource

from google_scholar_search_mcp.errors import (
    ScholarInvalidArgumentError,
    ScholarNotFoundError,
)
from google_scholar_search_mcp.models import PaperResult
from google_scholar_search_mcp.scholar import ScholarClient


def _make_config() -> Config:
    return Config(
        min_delay_seconds=0.01,
        max_delay_seconds=0.02,
        max_retries=1,
        proxy_type=ProxyType.NONE,
        proxy_http=None,
        proxy_https=None,
        scraperapi_key=None,
        timeout_seconds=10,
    )


def _fake_pub(title: str = "Test Paper", year: str = "2023") -> dict:
    return {
        "bib": {
            "title": title,
            "author": ["Author A", "Author B"],
            "pub_year": year,
            "abstract": "An abstract.",
            "venue": "Test Journal",
        },
        "num_citations": 42,
        "pub_url": "https://example.com/paper",
        "eprint_url": "https://example.com/eprint",
        "cites_id": ["abc123"],
        "author_pub_id": "pub_001",
    }


def test_pub_to_paper_result():
    result = ScholarClient._pub_to_paper_result(_fake_pub())
    assert isinstance(result, PaperResult)
    assert result.title == "Test Paper"
    assert result.authors == ["Author A", "Author B"]
    assert result.year == 2023
    assert result.num_citations == 42
    assert result.scholar_id == "abc123"


def test_pub_to_paper_result_handles_string_authors():
    pub = _fake_pub()
    pub["bib"]["author"] = "Author A and Author B"
    result = ScholarClient._pub_to_paper_result(pub)
    assert result.authors == ["Author A", "Author B"]


def test_pub_to_paper_result_handles_missing_fields():
    pub = {"bib": {}, "num_citations": 0}
    result = ScholarClient._pub_to_paper_result(pub)
    assert result.title == "Unknown"
    assert result.authors == []
    assert result.year is None
    assert result.scholar_id is None


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_search_pubs(mock_scholarly):
    mock_scholarly.search_pubs.return_value = iter([_fake_pub(), _fake_pub("Paper 2")])
    mock_scholarly.set_timeout = MagicMock()
    mock_scholarly.set_retries = MagicMock()

    client = ScholarClient(_make_config())
    results = client.search_pubs("test query", max_results=2)

    assert len(results) == 2
    assert results[0].title == "Test Paper"
    assert results[1].title == "Paper 2"
    mock_scholarly.search_pubs.assert_called_once()


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_search_pubs_respects_max_results(mock_scholarly):
    pubs = [_fake_pub(f"Paper {i}") for i in range(10)]
    mock_scholarly.search_pubs.return_value = iter(pubs)
    mock_scholarly.set_timeout = MagicMock()
    mock_scholarly.set_retries = MagicMock()

    client = ScholarClient(_make_config())
    results = client.search_pubs("test", max_results=3)

    assert len(results) == 3


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_get_bibtex(mock_scholarly):
    mock_scholarly.search_pubs.return_value = iter([_fake_pub()])
    mock_scholarly.fill.return_value = _fake_pub()
    mock_scholarly.bibtex.return_value = "@article{test, title={Test Paper}}"
    mock_scholarly.set_timeout = MagicMock()
    mock_scholarly.set_retries = MagicMock()

    client = ScholarClient(_make_config())
    bib = client.get_bibtex("Test Paper")

    assert "@article" in bib


def test_author_to_result():
    author_data = {
        "name": "Jane Doe",
        "scholar_id": "scholar123",
        "affiliation": "MIT",
        "email_domain": "mit.edu",
        "interests": ["AI", "ML"],
        "citedby": 5000,
        "hindex": 42,
        "i10index": 100,
        "homepage": "https://janedoe.com",
        "publications": [_fake_pub()],
    }
    result = ScholarClient._author_to_result(author_data)
    assert result.name == "Jane Doe"
    assert result.h_index == 42
    assert result.cited_by == 5000
    assert len(result.publications) == 1
    assert result.publications[0].title == "Test Paper"


@patch("google_scholar_search_mcp.scholar.scholarly")
@pytest.mark.parametrize("method", ["get_paper_details", "get_citations", "get_bibtex"])
def test_title_lookups_raise_not_found(mock_scholarly, method):
    mock_scholarly.search_pubs.return_value = iter([])

    client = ScholarClient(_make_config())

    with pytest.raises(ScholarNotFoundError, match=r"\[NOT_FOUND\].*No Such Paper"):
        getattr(client, method)("No Such Paper")


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_search_author_raises_not_found(mock_scholarly):
    mock_scholarly.search_author.return_value = iter([])

    client = ScholarClient(_make_config())

    with pytest.raises(ScholarNotFoundError, match="Nobody"):
        client.search_author("Nobody")


def _client(mock_scholarly: MagicMock) -> ScholarClient:
    mock_scholarly.set_timeout = MagicMock()
    mock_scholarly.set_retries = MagicMock()
    return ScholarClient(_make_config())


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_details_by_author_pub_id_skips_search(mock_scholarly):
    mock_scholarly.fill.side_effect = lambda stub: {**_fake_pub(), **stub}
    mock_scholarly.bibtex.return_value = "@article{x}"
    client = _client(mock_scholarly)

    details = client.get_paper_details(author_pub_id=" auth:pub1 ")

    stub = mock_scholarly.fill.call_args.args[0]
    assert stub["author_pub_id"] == "auth:pub1"
    assert stub["source"] == PublicationSource.AUTHOR_PUBLICATION_ENTRY
    mock_scholarly.search_pubs.assert_not_called()
    mock_scholarly.search_pubs_custom_url.assert_not_called()
    assert details.bibtex == "@article{x}"


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_details_by_scholar_id_uses_cluster_url(mock_scholarly):
    mock_scholarly.search_pubs_custom_url.return_value = iter([_fake_pub()])
    mock_scholarly.fill.return_value = _fake_pub()
    mock_scholarly.bibtex.return_value = "@article{x}"
    client = _client(mock_scholarly)

    details = client.get_paper_details(scholar_id="12345")

    assert "cluster=12345" in mock_scholarly.search_pubs_custom_url.call_args.args[0]
    mock_scholarly.search_pubs.assert_not_called()
    assert details.title == "Test Paper"


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_author_pub_id_wins_over_scholar_id_and_title(mock_scholarly):
    mock_scholarly.fill.side_effect = lambda stub: {**_fake_pub(), **stub}
    mock_scholarly.bibtex.return_value = "@article{x}"
    client = _client(mock_scholarly)

    client.get_bibtex("Some Title", scholar_id="1", author_pub_id="a:b")

    mock_scholarly.search_pubs.assert_not_called()
    mock_scholarly.search_pubs_custom_url.assert_not_called()


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_unknown_author_pub_id_is_not_found(mock_scholarly):
    mock_scholarly.fill.side_effect = AttributeError("'NoneType' has no 'text'")
    client = _client(mock_scholarly)

    with pytest.raises(ScholarNotFoundError, match="author_pub_id"):
        client.get_bibtex(author_pub_id="bad:id")


@patch("google_scholar_search_mcp.scholar.scholarly")
@pytest.mark.parametrize("value", [None, "", "   "])
def test_every_lookup_requires_an_identifier(mock_scholarly, value):
    client = _client(mock_scholarly)

    for method in (client.get_paper_details, client.get_citations, client.get_bibtex):
        with pytest.raises(ScholarInvalidArgumentError, match=r"\[INVALID_ARGUMENT\]"):
            method(value)
    with pytest.raises(ScholarInvalidArgumentError):
        client.search_author(value)
    mock_scholarly.search_pubs.assert_not_called()


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_citations_by_scholar_id_is_a_single_request_flow(mock_scholarly):
    citing = MagicMock()
    citing.total_results = 1234
    citing.__iter__.return_value = iter([_fake_pub("Citer 1"), _fake_pub("Citer 2")])
    mock_scholarly.search_citedby.return_value = citing
    client = _client(mock_scholarly)

    title, total, papers = client.get_citations(scholar_id="777", max_results=1)

    mock_scholarly.search_citedby.assert_called_once_with("777")
    mock_scholarly.search_pubs.assert_not_called()
    assert title is None
    assert total == 1234
    assert [p.title for p in papers] == ["Citer 1"]


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_citations_by_author_pub_id(mock_scholarly):
    pub = {**_fake_pub("Cited Paper"), "num_citations": 99}
    mock_scholarly.fill.return_value = pub
    mock_scholarly.citedby.return_value = iter([_fake_pub("Citer")])
    client = _client(mock_scholarly)

    title, total, papers = client.get_citations(author_pub_id="a:b")

    assert (title, total) == ("Cited Paper", 99)
    assert [p.title for p in papers] == ["Citer"]
    mock_scholarly.search_pubs.assert_not_called()


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_citations_by_title_still_works(mock_scholarly):
    mock_scholarly.search_pubs.return_value = iter([_fake_pub("Cited Paper")])
    mock_scholarly.citedby.return_value = iter([_fake_pub("Citer")])
    client = _client(mock_scholarly)

    title, total, papers = client.get_citations("Cited Paper")

    assert (title, total) == ("Cited Paper", 42)
    assert len(papers) == 1


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_search_author_by_scholar_id_skips_name_search(mock_scholarly):
    mock_scholarly.search_author_id.return_value = {"scholar_id": "EmD_lTEAAAAJ"}
    mock_scholarly.fill.return_value = {
        "name": "Marie Curie",
        "scholar_id": "EmD_lTEAAAAJ",
        "publications": [],
    }
    client = _client(mock_scholarly)

    result = client.search_author(scholar_id="EmD_lTEAAAAJ", max_pubs=3)

    mock_scholarly.search_author.assert_not_called()
    mock_scholarly.search_author_id.assert_called_once_with("EmD_lTEAAAAJ")
    assert mock_scholarly.fill.call_args.kwargs["publication_limit"] == 3
    assert result.scholar_id == "EmD_lTEAAAAJ"


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_unknown_author_scholar_id_is_not_found(mock_scholarly):
    mock_scholarly.search_author_id.side_effect = IndexError("list index out of range")
    client = _client(mock_scholarly)

    with pytest.raises(ScholarNotFoundError, match="scholar_id"):
        client.search_author(scholar_id="nope")
