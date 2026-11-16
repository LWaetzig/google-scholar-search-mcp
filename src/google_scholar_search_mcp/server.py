from __future__ import annotations

import logging
import sys

from mcp.server.mcpserver import MCPServer

from .cache import TTLCache, normalize
from .config import Config
from .models import (
    BulkSearchResponse,
    CitationResponse,
    PaperDetails,
    PaperResult,
    SearchResponse,
)
from .rate_limiter import RateLimiter
from .scholar import ScholarClient, require_identifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("google-scholar-mcp")

config = Config.from_env()
scholar = ScholarClient(config)
# Request spacing (GS_MIN_DELAY / GS_MAX_DELAY) is applied per HTTP request by
# the throttle that ScholarClient configures, so the limiter only serializes
# and retries and adds no delay of its own.
limiter = RateLimiter(0.0, 0.0)
cache = TTLCache(config.cache_ttl_seconds, config.cache_max_entries)


def _paper_key(title: str | None, scholar_id: str | None) -> tuple[str, str]:
    """Cache key part identifying a paper; the id wins, as in the lookup."""
    if scholar_id and scholar_id.strip():
        return ("id", scholar_id.strip())
    return ("title", normalize(title))


async def _search(
    query: str,
    max_results: int,
    year_from: int | None,
    year_to: int | None,
    sort_by: str,
    include_patents: bool,
) -> list[PaperResult]:
    """Run a keyword search, answering repeats from the cache."""
    key = (
        "search",
        normalize(query),
        max_results,
        year_from,
        year_to,
        sort_by,
        include_patents,
    )
    if (hit := cache.get(key)) is not None:
        return hit
    scholar.ensure_available()
    papers = await limiter.execute(
        scholar.search_pubs,
        query,
        max_results=max_results,
        year_low=year_from,
        year_high=year_to,
        sort_by=sort_by,
        patents=include_patents,
        max_retries=config.max_retries,
    )
    cache.set(key, papers)
    return papers


def _build_instructions(cfg: Config) -> str:
    """Build the server instructions, including a pointer to the agent skill.

    Args:
        cfg (Config): Configuration; ``skill_url`` is mentioned when set.

    Returns:
        str: Instruction text sent to MCP clients.
    """
    text = (
        "Search Google Scholar for academic papers, citations, and BibTeX entries. "
        "Rate limiting is applied automatically. For bulk searches, use the bulk_search tool."
    )
    if cfg.skill_url:
        text += (
            "\n\nAn agent skill describing when and how to use these tools "
            f"(search strategy, rate limits, error handling) is available at: {cfg.skill_url}"
        )
    return text


mcp = MCPServer("Google Scholar", instructions=_build_instructions(config))


@mcp.tool()
async def search_papers(
    query: str,
    max_results: int = 10,
    year_from: int | None = None,
    year_to: int | None = None,
    sort_by: str = "relevance",
    include_patents: bool = True,
) -> SearchResponse:
    """Search Google Scholar for academic papers by keyword.

    Args:
        query (str): Search query (same syntax as Google Scholar search box).
        max_results (int): Maximum number of results to return (1-20, default 10).
        year_from (int | None): Filter to papers published in or after this year.
        year_to (int | None): Filter to papers published in or before this year.
        sort_by (str): Sort order — "relevance" (default) or "date".
        include_patents (bool): Include patents in results (default True).

    Returns:
        SearchResponse: Matching papers.

    Raises:
        ScholarBlockedError: If Google Scholar blocks the client.
        ScholarRateLimitError: If Google Scholar throttles the request after retries.
    """
    max_results = min(max(max_results, 1), 20)
    papers = await _search(
        query, max_results, year_from, year_to, sort_by, include_patents
    )
    return SearchResponse(query=query, total_results=len(papers), papers=papers)


@mcp.tool()
async def get_paper_details(
    title: str | None = None,
    scholar_id: str | None = None,
) -> PaperDetails:
    """Get full details of a specific paper.

    Identify the paper with ``scholar_id`` from an earlier search result when
    you have one; a title search takes the first hit, which can be a different
    paper.

    Args:
        title (str | None): The exact (or close) title of the paper.
        scholar_id (str | None): ``scholar_id`` of a paper from an earlier search result.

    Returns:
        PaperDetails: Details of the best-matching paper.

    Raises:
        ScholarBlockedError: If Google Scholar blocks the client.
        ScholarRateLimitError: If Google Scholar throttles the request after retries.
        ScholarInvalidArgumentError: If no identifier is given.
        ScholarNotFoundError: If nothing matches.
    """
    require_identifier(title, scholar_id)
    key = ("details", *_paper_key(title, scholar_id))
    if (hit := cache.get(key)) is not None:
        return hit
    scholar.ensure_available()
    details = await limiter.execute(
        scholar.get_paper_details,
        title,
        scholar_id=scholar_id,
        max_retries=config.max_retries,
    )
    cache.set(key, details)
    return details


@mcp.tool()
async def get_citations(
    title: str | None = None,
    max_results: int = 10,
    scholar_id: str | None = None,
) -> CitationResponse:
    """Get papers that cite a given paper.

    With only ``scholar_id`` the cited paper's title is not fetched (one
    request fewer) and is omitted.

    Args:
        title (str | None): Title of the paper whose citations to retrieve.
        max_results (int): Maximum citing papers to return (1-20, default 10).
        scholar_id (str | None): ``scholar_id`` of a paper from an earlier search result.

    Returns:
        CitationResponse: Citing papers, plus the cited paper's title and the total citation count when known.

    Raises:
        ScholarBlockedError: If Google Scholar blocks the client.
        ScholarRateLimitError: If Google Scholar throttles the request after retries.
        ScholarInvalidArgumentError: If no identifier is given.
        ScholarNotFoundError: If nothing matches.
    """
    require_identifier(title, scholar_id)
    max_results = min(max(max_results, 1), 20)
    key = ("citations", *_paper_key(title, scholar_id), max_results)
    if (hit := cache.get(key)) is not None:
        return hit
    scholar.ensure_available()
    cited_title, total, papers = await limiter.execute(
        scholar.get_citations,
        title,
        max_results=max_results,
        scholar_id=scholar_id,
        max_retries=config.max_retries,
    )
    response = CitationResponse(
        cited_paper_title=cited_title,
        total_citations=total,
        citations=papers,
    )
    cache.set(key, response)
    return response


@mcp.tool()
async def bulk_search(
    queries: list[str],
    max_results_per_query: int = 5,
    year_from: int | None = None,
    year_to: int | None = None,
) -> BulkSearchResponse:
    """Search Google Scholar for multiple queries sequentially with rate limiting.

    Use this for batch literature reviews. Each query runs one at a time with
    delays between them to avoid being blocked.

    Args:
        queries (list[str]): List of search queries (maximum 10).
        max_results_per_query (int): Results per query (1-10, default 5).
        year_from (int | None): Filter to papers published in or after this year.
        year_to (int | None): Filter to papers published in or before this year.

    Returns:
        BulkSearchResponse: One result per query plus per-query errors; failed queries do not abort the batch.
    """
    queries = queries[:10]
    max_results_per_query = min(max(max_results_per_query, 1), 10)
    results: list[SearchResponse] = []
    errors: list[str] = []

    for query in queries:
        try:
            papers = await _search(
                query, max_results_per_query, year_from, year_to, "relevance", True
            )
            results.append(
                SearchResponse(query=query, total_results=len(papers), papers=papers)
            )
        except Exception as e:
            logger.error("Bulk search failed for query '%s': %s", query, e)
            errors.append(f"Query '{query}': {e}")
            results.append(
                SearchResponse(
                    query=query, total_results=0, papers=[], message=f"Error: {e}"
                )
            )

    return BulkSearchResponse(
        results=results,
        total_queries=len(queries),
        completed_queries=len(queries) - len(errors),
        errors=errors,
    )


@mcp.tool()
async def get_bibtex(
    title: str | None = None,
    scholar_id: str | None = None,
) -> str:
    """Get BibTeX citation entry for a paper.

    Identify the paper with ``scholar_id`` from an earlier search result when
    you have one.

    Args:
        title (str | None): Title of the paper to get BibTeX for.
        scholar_id (str | None): ``scholar_id`` of a paper from an earlier search result.

    Returns:
        str: BibTeX entry.

    Raises:
        ScholarBlockedError: If Google Scholar blocks the client.
        ScholarRateLimitError: If Google Scholar throttles the request after retries.
        ScholarInvalidArgumentError: If no identifier is given.
        ScholarNotFoundError: If nothing matches.
    """
    require_identifier(title, scholar_id)
    key = ("bibtex", *_paper_key(title, scholar_id))
    if (hit := cache.get(key)) is not None:
        return hit
    scholar.ensure_available()
    bibtex = await limiter.execute(
        scholar.get_bibtex,
        title,
        scholar_id=scholar_id,
        max_retries=config.max_retries,
    )
    cache.set(key, bibtex)
    return bibtex


def main() -> None:
    """Run the MCP server over stdio.

    Returns:
        None: Blocks until the client disconnects.
    """
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
