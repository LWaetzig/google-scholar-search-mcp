from unittest.mock import MagicMock, patch

from google_scholar_mcp.config import Config, ProxyType
from google_scholar_mcp.models import PaperResult
from google_scholar_mcp.scholar import ScholarClient


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


@patch("google_scholar_mcp.scholar.scholarly")
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


@patch("google_scholar_mcp.scholar.scholarly")
def test_search_pubs_respects_max_results(mock_scholarly):
    pubs = [_fake_pub(f"Paper {i}") for i in range(10)]
    mock_scholarly.search_pubs.return_value = iter(pubs)
    mock_scholarly.set_timeout = MagicMock()
    mock_scholarly.set_retries = MagicMock()

    client = ScholarClient(_make_config())
    results = client.search_pubs("test", max_results=3)

    assert len(results) == 3


@patch("google_scholar_mcp.scholar.scholarly")
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
