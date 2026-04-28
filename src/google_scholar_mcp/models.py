from __future__ import annotations

from pydantic import BaseModel, Field


class PaperResult(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    num_citations: int = 0
    url: str | None = None
    pub_url: str | None = None
    venue: str | None = None
    scholar_id: str | None = None
    author_pub_id: str | None = None


class PaperDetails(PaperResult):
    cites_per_year: dict[int, int] = Field(default_factory=dict)
    public_access: bool | None = None
    bibtex: str | None = None


class AuthorResult(BaseModel):
    name: str
    scholar_id: str | None = None
    affiliation: str | None = None
    email_domain: str | None = None
    interests: list[str] = Field(default_factory=list)
    cited_by: int = 0
    h_index: int = 0
    i10_index: int = 0
    publications: list[PaperResult] = Field(default_factory=list)
    homepage_url: str | None = None


class SearchResponse(BaseModel):
    query: str
    total_results: int
    papers: list[PaperResult]
    message: str | None = None


class BulkSearchResponse(BaseModel):
    results: list[SearchResponse]
    total_queries: int
    completed_queries: int
    errors: list[str] = Field(default_factory=list)


class CitationResponse(BaseModel):
    cited_paper_title: str
    total_citations: int
    citations: list[PaperResult]
