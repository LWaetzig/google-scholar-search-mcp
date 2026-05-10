from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from scholarly import ProxyGenerator, scholarly

from .models import AuthorResult, PaperDetails, PaperResult

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[call-overload]
    except (ValueError, TypeError):
        return None


class ScholarClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        scholarly.set_timeout(self._config.timeout_seconds)
        scholarly.set_retries(self._config.max_retries)
        self._setup_proxy()
        self._initialized = True

    def _setup_proxy(self) -> None:
        from .config import ProxyType

        match self._config.proxy_type:
            case ProxyType.FREE:
                pg = ProxyGenerator()
                pg.FreeProxies()
                scholarly.use_proxy(pg)
            case ProxyType.SINGLE:
                pg = ProxyGenerator()
                pg.SingleProxy(
                    http=self._config.proxy_http,
                    https=self._config.proxy_https,
                )
                scholarly.use_proxy(pg)
            case ProxyType.SCRAPERAPI:
                pg = ProxyGenerator()
                pg.ScraperAPI(self._config.scraperapi_key)
                scholarly.use_proxy(pg)
            case _:
                pass

    def search_pubs(
        self,
        query: str,
        max_results: int = 10,
        year_low: int | None = None,
        year_high: int | None = None,
        sort_by: str = "relevance",
        patents: bool = True,
    ) -> list[PaperResult]:
        self._ensure_initialized()
        results = scholarly.search_pubs(
            query,
            year_low=year_low,
            year_high=year_high,
            sort_by=sort_by,
            patents=patents,
        )
        papers: list[PaperResult] = []
        for i, pub in enumerate(results):
            if i >= max_results:
                break
            papers.append(self._pub_to_paper_result(pub))
        return papers

    def get_paper_details(self, title: str) -> PaperDetails:
        self._ensure_initialized()
        results = scholarly.search_pubs(title)
        pub = next(results)
        pub = scholarly.fill(pub)
        return self._pub_to_paper_details(pub)

    def search_author(self, name: str, max_pubs: int = 5) -> AuthorResult:
        self._ensure_initialized()
        search = scholarly.search_author(name)
        author = next(search)
        author = scholarly.fill(
            author,
            sections=["basics", "indices", "publications"],
            publication_limit=max_pubs,
        )
        return self._author_to_result(author)

    def get_citations(
        self, title: str, max_results: int = 10
    ) -> tuple[str, int, list[PaperResult]]:
        self._ensure_initialized()
        results = scholarly.search_pubs(title)
        pub = next(results)
        total = pub.get("num_citations", 0)
        citing = scholarly.citedby(pub)
        papers: list[PaperResult] = []
        for i, cite in enumerate(citing):
            if i >= max_results:
                break
            papers.append(self._pub_to_paper_result(cite))
        cited_title = pub.get("bib", {}).get("title", title)
        return cited_title, total, papers

    def get_bibtex(self, title: str) -> str:
        self._ensure_initialized()
        results = scholarly.search_pubs(title)
        pub = next(results)
        pub = scholarly.fill(pub)
        return scholarly.bibtex(pub)

    @staticmethod
    def _pub_to_paper_result(pub: dict) -> PaperResult:
        bib = pub.get("bib", {})
        author_list = bib.get("author", [])
        if isinstance(author_list, str):
            author_list = [a.strip() for a in author_list.split(" and ")]
        cites_id = pub.get("cites_id")
        scholar_id = cites_id[0] if isinstance(cites_id, list) and cites_id else None
        return PaperResult(
            title=bib.get("title", "Unknown"),
            authors=author_list,
            year=_safe_int(bib.get("pub_year")),
            abstract=bib.get("abstract"),
            num_citations=pub.get("num_citations", 0),
            url=pub.get("pub_url") or pub.get("eprint_url"),
            pub_url=pub.get("pub_url"),
            venue=bib.get("venue"),
            scholar_id=scholar_id,
            author_pub_id=pub.get("author_pub_id"),
        )

    def _pub_to_paper_details(self, pub: dict) -> PaperDetails:
        base = self._pub_to_paper_result(pub)
        public_access_info = pub.get("public_access")
        public_access = None
        if isinstance(public_access_info, dict):
            public_access = public_access_info.get("available")
        elif isinstance(public_access_info, bool):
            public_access = public_access_info
        return PaperDetails(
            **base.model_dump(),
            cites_per_year=pub.get("cites_per_year", {}),
            public_access=public_access,
            bibtex=scholarly.bibtex(pub),
        )

    @staticmethod
    def _author_to_result(author: dict) -> AuthorResult:
        pubs: list[PaperResult] = []
        for pub in author.get("publications", []):
            bib = pub.get("bib", {})
            author_list = bib.get("author", [])
            if isinstance(author_list, str):
                author_list = [a.strip() for a in author_list.split(" and ")]
            pubs.append(
                PaperResult(
                    title=bib.get("title", "Unknown"),
                    authors=author_list,
                    year=_safe_int(bib.get("pub_year")),
                    num_citations=pub.get("num_citations", 0),
                    url=pub.get("pub_url"),
                    pub_url=pub.get("pub_url"),
                    author_pub_id=pub.get("author_pub_id"),
                )
            )
        return AuthorResult(
            name=author.get("name", "Unknown"),
            scholar_id=author.get("scholar_id"),
            affiliation=author.get("affiliation"),
            email_domain=author.get("email_domain"),
            interests=author.get("interests", []),
            cited_by=author.get("citedby", 0),
            h_index=author.get("hindex", 0),
            i10_index=author.get("i10index", 0),
            publications=pubs,
            homepage_url=author.get("homepage"),
        )
