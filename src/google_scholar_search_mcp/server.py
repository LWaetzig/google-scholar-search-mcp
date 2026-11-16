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
from .errors import ScholarInvalidArgumentError
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


SCHOLAR_RESULT_LIMIT = 1000


def _check_offset(offset: int, max_results: int) -> int:
    """Validate a paging offset against what Google Scholar serves.

    Args:
        offset (int): Requested number of results to skip; negatives count as 0.
        max_results (int): Page size of the call.

    Returns:
        int: The offset to use.

    Raises:
        ScholarInvalidArgumentError: If the page would reach past Scholar's
            limit of 1000 results per query.
    """
    offset = max(offset, 0)
    if offset + max_results > SCHOLAR_RESULT_LIMIT:
        raise ScholarInvalidArgumentError(
            f"Google Scholar serves only the first {SCHOLAR_RESULT_LIMIT} results of a "
            f"query (offset {offset} + {max_results} results is past that). Narrow "
            "the query instead, e.g. with year_from / year_to or more specific terms."
        )
    return offset


def _next_offset(
    offset: int, returned: int, asked: int, total: int | None
) -> int | None:
    """Offset of the following page, or ``None`` when there is none.

    Args:
        offset (int): Offset of this page.
        returned (int): Number of results on this page.
        asked (int): Number of results that were requested.
        total (int | None): Total number of results, when known.

    Returns:
        int | None: ``offset + returned`` while more results can exist: the
        page came back full, the known total is not reached and Scholar's
        1000-result limit is not hit.
    """
    following = offset + returned
    if returned < asked or following >= SCHOLAR_RESULT_LIMIT:
        return None
    if total is not None and following >= total:
        return None
    return following


async def _search(
    query: str,
    max_results: int,
    year_from: int | None,
    year_to: int | None,
    sort_by: str,
    include_patents: bool,
    offset: int = 0,
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
        offset,
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
        offset=offset,
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
    offset: int = 0,
) -> SearchResponse:
    """Search Google Scholar for academic papers by keyword.

    To page, call again with ``offset`` set to the ``next_offset`` of the
    previous response (``None`` means there are no more results). Each page
    costs at least one slow request: only page when the user needs more.

    Args:
        query (str): Search query (same syntax as Google Scholar search box).
        max_results (int): Maximum number of results to return (1-20, default 10).
        year_from (int | None): Filter to papers published in or after this year.
        year_to (int | None): Filter to papers published in or before this year.
        sort_by (str): Sort order — "relevance" (default) or "date".
        include_patents (bool): Include patents in results (default True).
        offset (int): Number of results to skip (default 0). Scholar serves at
            most the first 1000 results of a query.

    Returns:
        SearchResponse: Matching papers, with ``offset`` and ``next_offset`` for paging.

    Raises:
        ScholarBlockedError: If Google Scholar blocks the client.
        ScholarRateLimitError: If Google Scholar throttles the request after retries.
        ScholarInvalidArgumentError: If ``offset`` reaches past the first 1000 results.
    """
    max_results = min(max(max_results, 1), 20)
    offset = _check_offset(offset, max_results)
    papers = await _search(
        query, max_results, year_from, year_to, sort_by, include_patents, offset
    )
    return SearchResponse(
        query=query,
        total_results=len(papers),
        papers=papers,
        offset=offset,
        next_offset=_next_offset(offset, len(papers), max_results, None),
    )


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
    offset: int = 0,
) -> CitationResponse:
    """Get papers that cite a given paper.

    With only ``scholar_id`` the cited paper's title is not fetched (one
    request fewer) and is omitted. To page, call again with ``offset`` set to
    the ``next_offset`` of the previous response (``None``: no more), and
    prefer ``scholar_id`` for the following pages.

    Args:
        title (str | None): Title of the paper whose citations to retrieve.
        max_results (int): Maximum citing papers to return (1-20, default 10).
        scholar_id (str | None): ``scholar_id`` of a paper from an earlier search result.
        offset (int): Number of citing papers to skip (default 0). Scholar
            serves at most the first 1000.

    Returns:
        CitationResponse: Citing papers, the cited paper's title and the total citation count when known, and ``offset`` / ``next_offset`` for paging.

    Raises:
        ScholarBlockedError: If Google Scholar blocks the client.
        ScholarRateLimitError: If Google Scholar throttles the request after retries.
        ScholarInvalidArgumentError: If no identifier is given.
        ScholarNotFoundError: If nothing matches.
    """
    require_identifier(title, scholar_id)
    max_results = min(max(max_results, 1), 20)
    offset = _check_offset(offset, max_results)
    key = ("citations", *_paper_key(title, scholar_id), max_results, offset)
    if (hit := cache.get(key)) is not None:
        return hit
    scholar.ensure_available()
    cited_title, total, papers = await limiter.execute(
        scholar.get_citations,
        title,
        max_results=max_results,
        scholar_id=scholar_id,
        offset=offset,
        max_retries=config.max_retries,
    )
    response = CitationResponse(
        cited_paper_title=cited_title,
        total_citations=total,
        citations=papers,
        offset=offset,
        next_offset=_next_offset(offset, len(papers), max_results, total),
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
    delays between them to avoid being blocked. Only first pages are returned;
    to see more of one query, call ``search_papers`` with its ``next_offset``.

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
                SearchResponse(
                    query=query,
                    total_results=len(papers),
                    papers=papers,
                    next_offset=_next_offset(
                        0, len(papers), max_results_per_query, None
                    ),
                )
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
