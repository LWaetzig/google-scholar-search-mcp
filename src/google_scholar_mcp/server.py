from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from .config import Config
from .models import (
    AuthorResult,
    BulkSearchResponse,
    CitationResponse,
    PaperDetails,
    SearchResponse,
)
from .rate_limiter import RateLimiter
from .scholar import ScholarClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("google-scholar-mcp")

config = Config.from_env()
scholar = ScholarClient(config)
limiter = RateLimiter(config.min_delay_seconds, config.max_delay_seconds)

mcp = FastMCP(
    "Google Scholar",
    instructions=(
        "Search Google Scholar for academic papers, authors, citations, and BibTeX entries. "
        "Rate limiting is applied automatically. For bulk searches, use the bulk_search tool."
    ),
)


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
        query: Search query (same syntax as Google Scholar search box).
        max_results: Maximum number of results to return (1-20, default 10).
        year_from: Filter to papers published in or after this year.
        year_to: Filter to papers published in or before this year.
        sort_by: Sort order — "relevance" (default) or "date".
        include_patents: Include patents in results (default True).
    """
    max_results = min(max(max_results, 1), 20)
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
    return SearchResponse(
        query=query,
        total_results=len(papers),
        papers=papers,
    )


@mcp.tool()
async def search_author(
    name: str,
    max_publications: int = 5,
) -> AuthorResult:
    """Find a Google Scholar author profile by name.

    Args:
        name: Author name to search for (e.g. "Albert Einstein").
        max_publications: Number of publications to include (1-20, default 5).
    """
    max_publications = min(max(max_publications, 1), 20)
    return await limiter.execute(
        scholar.search_author,
        name,
        max_pubs=max_publications,
        max_retries=config.max_retries,
    )


@mcp.tool()
async def get_paper_details(title: str) -> PaperDetails:
    """Get full details of a specific paper by its title.

    Args:
        title: The exact (or close) title of the paper.
    """
    return await limiter.execute(
        scholar.get_paper_details,
        title,
        max_retries=config.max_retries,
    )


@mcp.tool()
async def get_citations(
    title: str,
    max_results: int = 10,
) -> CitationResponse:
    """Get papers that cite a given paper.

    Args:
        title: Title of the paper whose citations to retrieve.
        max_results: Maximum citing papers to return (1-20, default 10).
    """
    max_results = min(max(max_results, 1), 20)
    cited_title, total, papers = await limiter.execute(
        scholar.get_citations,
        title,
        max_results=max_results,
        max_retries=config.max_retries,
    )
    return CitationResponse(
        cited_paper_title=cited_title,
        total_citations=total,
        citations=papers,
    )


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
        queries: List of search queries (maximum 10).
        max_results_per_query: Results per query (1-10, default 5).
        year_from: Filter to papers published in or after this year.
        year_to: Filter to papers published in or before this year.
    """
    queries = queries[:10]
    max_results_per_query = min(max(max_results_per_query, 1), 10)
    results: list[SearchResponse] = []
    errors: list[str] = []

    for query in queries:
        try:
            papers = await limiter.execute(
                scholar.search_pubs,
                query,
                max_results=max_results_per_query,
                year_low=year_from,
                year_high=year_to,
                max_retries=config.max_retries,
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
async def get_bibtex(title: str) -> str:
    """Get BibTeX citation entry for a paper.

    Args:
        title: Title of the paper to get BibTeX for.
    """
    return await limiter.execute(
        scholar.get_bibtex,
        title,
        max_retries=config.max_retries,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
