from unittest.mock import MagicMock, patch

import pytest

from google_scholar_search_mcp.config import Config, ProxyType

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


@patch("google_scholar_search_mcp.scholar.scholarly")
@pytest.mark.parametrize("method", ["get_paper_details", "get_citations", "get_bibtex"])
def test_title_lookups_raise_not_found(mock_scholarly, method):
    mock_scholarly.search_pubs.return_value = iter([])

    client = ScholarClient(_make_config())

    with pytest.raises(ScholarNotFoundError, match=r"\[NOT_FOUND\].*No Such Paper"):
        getattr(client, method)("No Such Paper")


def _client(mock_scholarly: MagicMock) -> ScholarClient:
    mock_scholarly.set_timeout = MagicMock()
    mock_scholarly.set_retries = MagicMock()
    return ScholarClient(_make_config())


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
@pytest.mark.parametrize("value", [None, "", "   "])
def test_every_lookup_requires_an_identifier(mock_scholarly, value):
    client = _client(mock_scholarly)

    for method in (client.get_paper_details, client.get_citations, client.get_bibtex):
        with pytest.raises(ScholarInvalidArgumentError, match=r"\[INVALID_ARGUMENT\]"):
            method(value)
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
def test_citations_by_title_use_the_papers_id_for_a_single_plain_request(
    mock_scholarly,
):
    mock_scholarly.search_pubs.return_value = iter([_fake_pub("Cited Paper")])
    mock_scholarly.search_citedby.return_value = iter([_fake_pub("Citer")])
    client = _client(mock_scholarly)

    title, total, papers = client.get_citations("Cited Paper")

    assert (title, total) == ("Cited Paper", 42)
    assert len(papers) == 1
    mock_scholarly.search_citedby.assert_called_once_with("abc123")
    mock_scholarly.citedby.assert_not_called()


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_citations_of_a_paper_without_an_id_fall_back_to_scholarly(mock_scholarly):
    pub = _fake_pub("Cited Paper")
    del pub["cites_id"]
    mock_scholarly.search_pubs.side_effect = lambda *a, **k: iter([pub])
    mock_scholarly.citedby.return_value = iter([_fake_pub("Citer")])
    client = _client(mock_scholarly)

    assert len(client.get_citations("Cited Paper")[2]) == 1
    assert client.get_citations("Cited Paper", offset=10)[2] == []
    mock_scholarly.citedby.assert_called_once()


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_search_passes_the_offset_to_scholar(mock_scholarly):
    mock_scholarly.search_pubs.return_value = iter([_fake_pub()])
    client = _client(mock_scholarly)

    client.search_pubs("x", offset=30)

    assert mock_scholarly.search_pubs.call_args.kwargs["start_index"] == 30


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_citation_pages_pass_the_offset_to_scholar(mock_scholarly):
    mock_scholarly.search_citedby.side_effect = lambda *a, **k: iter([_fake_pub()])
    mock_scholarly.search_pubs.return_value = iter([_fake_pub("Cited Paper")])
    client = _client(mock_scholarly)

    client.get_citations(scholar_id="777", offset=20)
    client.get_citations("Cited Paper", offset=40)

    calls = mock_scholarly.search_citedby.call_args_list
    assert calls[0].args == ("777",) and calls[0].kwargs == {"start_index": 20}
    assert calls[1].args == ("abc123",) and calls[1].kwargs == {"start_index": 40}


@patch("google_scholar_search_mcp.scholar.scholarly")
def test_an_offset_past_the_last_result_is_an_empty_page_not_an_error(
    mock_scholarly,
):
    mock_scholarly.search_pubs.return_value = iter([])
    client = _client(mock_scholarly)

    assert client.search_pubs("x", offset=500) == []


def test_scholar_id_comes_from_the_cited_by_link_of_a_search_result():
    pub = _fake_pub()
    del pub["cites_id"]
    pub["citedby_url"] = (
        "/scholar?cites=2960712678066186980&as_sdt=2005&sciodt=0,5&hl=en"
    )

    assert ScholarClient._pub_to_paper_result(pub).scholar_id == "2960712678066186980"


def test_an_uncited_search_result_has_no_scholar_id():
    pub = _fake_pub()
    del pub["cites_id"]

    assert ScholarClient._pub_to_paper_result(pub).scholar_id is None
