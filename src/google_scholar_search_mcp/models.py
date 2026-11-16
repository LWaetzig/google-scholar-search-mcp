from __future__ import annotations

from pydantic import BaseModel, Field


class PaperResult(BaseModel):
    """A paper in a search result list."""

    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    num_citations: int = 0
    url: str | None = None
    pub_url: str | None = None
    venue: str | None = None
    scholar_id: str | None = None


class PaperDetails(PaperResult):
    """A paper with details, citation history and BibTeX."""

    cites_per_year: dict[int, int] = Field(default_factory=dict)
    public_access: bool | None = None
    bibtex: str | None = None


class SearchResponse(BaseModel):
    """Result of a single keyword search."""

    query: str
    total_results: int
    papers: list[PaperResult]
    message: str | None = None


class BulkSearchResponse(BaseModel):
    """Combined result of several searches run in one call."""

    results: list[SearchResponse]
    total_queries: int
    completed_queries: int
    errors: list[str] = Field(default_factory=list)


class CitationResponse(BaseModel):
    """Papers that cite a given paper."""

    cited_paper_title: str | None = None
    total_citations: int | None = None
    citations: list[PaperResult]
