from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, TypeVar

from scholarly import ProxyGenerator, scholarly

from .errors import ScholarNotFoundError
from .models import AuthorResult, PaperDetails, PaperResult

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _safe_int(value: object) -> int | None:
    """Convert a value to ``int`` without raising.

    Args:
        value (object): Value to convert, e.g. a year string from Scholar.

    Returns:
        int | None: The integer, or ``None`` if ``value`` is ``None`` or
        not convertible.
    """
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[call-overload]
    except (ValueError, TypeError):
        return None


def _first(results: Iterator[T], what: str) -> T:
    """Return the first item of a ``scholarly`` result iterator.

    Args:
        results (Iterator[T]): Lazy search results.
        what (str): Description of the lookup, used in the error message.

    Returns:
        T: The first result.

    Raises:
        ScholarNotFoundError: If the iterator is empty. A bare
            ``StopIteration`` must not leave a worker thread, as it cannot
            propagate through an ``asyncio`` future.
    """
    try:
        return next(results)
    except StopIteration:
        raise ScholarNotFoundError(
            f"No Google Scholar result for {what}. Try the exact title from a "
            "search result, fewer words, or a different spelling. If well-known "
            "papers also return nothing, Scholar may be silently blocking this "
            "IP (sign-in redirect): raise GS_MIN_DELAY or set GS_PROXY_TYPE."
        ) from None


class ScholarClient:
    """Synchronous wrapper around ``scholarly`` that returns typed models."""

    def __init__(self, config: Config) -> None:
        """Create a client; ``scholarly`` is configured lazily on first use.

        Args:
            config (Config): Timeout, retry and proxy settings.
        """
        self._config = config
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Apply timeout, retries and proxy to ``scholarly`` once.

        Returns:
            None: Does nothing after the first call.
        """
        if self._initialized:
            return
        scholarly.set_timeout(self._config.timeout_seconds)
        scholarly.set_retries(self._config.max_retries)
        self._setup_proxy()
        self._initialized = True

    def _setup_proxy(self) -> None:
        """Install the proxy selected by ``config.proxy_type`` in ``scholarly``.

        Returns:
            None: With ``ProxyType.NONE`` nothing is changed.
        """
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
        """Search publications by keyword.

        Args:
            query (str): Search query.
            max_results (int): Maximum number of papers to return.
            year_low (int | None): Earliest publication year.
            year_high (int | None): Latest publication year.
            sort_by (str): ``"relevance"`` or ``"date"``.
            patents (bool): Whether to include patents.

        Returns:
            list[PaperResult]: Up to ``max_results`` papers.

        Raises:
            MaxTriesExceededException: If Scholar blocks the request
                (raised by ``scholarly``).
        """
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
        """Fetch full details and BibTeX of the best match for a title.

        Args:
            title (str): Paper title.

        Returns:
            PaperDetails: Details of the first search hit.

        Raises:
            ScholarNotFoundError: If the search finds no paper.
        """
        self._ensure_initialized()
        results = scholarly.search_pubs(title)
        pub = _first(results, f"title {title!r}")
        pub = scholarly.fill(pub)
        return self._pub_to_paper_details(pub)

    def search_author(self, name: str, max_pubs: int = 5) -> AuthorResult:
        """Look up an author profile by name.

        Args:
            name (str): Author name.
            max_pubs (int): Number of publications to load.

        Returns:
            AuthorResult: Profile of the first matching author.

        Raises:
            ScholarNotFoundError: If no author matches.
        """
        self._ensure_initialized()
        search = scholarly.search_author(name)
        author = _first(search, f"author {name!r}")
        author = scholarly.fill(
            author,
            sections=["basics", "indices", "publications"],
            publication_limit=max_pubs,
        )
        return self._author_to_result(author)

    def get_citations(
        self, title: str, max_results: int = 10
    ) -> tuple[str, int, list[PaperResult]]:
        """Fetch papers that cite the best match for a title.

        Args:
            title (str): Title of the cited paper.
            max_results (int): Maximum number of citing papers to return.

        Returns:
            tuple[str, int, list[PaperResult]]: The matched paper's title,
            its total citation count and the citing papers.

        Raises:
            ScholarNotFoundError: If the search finds no paper.
        """
        self._ensure_initialized()
        results = scholarly.search_pubs(title)
        pub = _first(results, f"title {title!r}")
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
        """Get the BibTeX entry of the best match for a title.

        Args:
            title (str): Paper title.

        Returns:
            str: BibTeX entry.

        Raises:
            ScholarNotFoundError: If the search finds no paper.
        """
        self._ensure_initialized()
        results = scholarly.search_pubs(title)
        pub = _first(results, f"title {title!r}")
        pub = scholarly.fill(pub)
        return scholarly.bibtex(pub)

    @staticmethod
    def _pub_to_paper_result(pub: dict) -> PaperResult:
        """Convert a ``scholarly`` publication dict to a model.

        Args:
            pub (dict): Publication as returned by ``scholarly``.

        Returns:
            PaperResult: The publication with missing fields defaulted.
        """
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
        """Convert a filled ``scholarly`` publication dict to a detailed model.

        Args:
            pub (dict): Publication filled via ``scholarly.fill``.

        Returns:
            PaperDetails: The paper with citation history, access flag and BibTeX.
        """
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
        """Convert a ``scholarly`` author dict to a model.

        Args:
            author (dict): Author filled via ``scholarly.fill``.

        Returns:
            AuthorResult: The profile with its publications.
        """
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
