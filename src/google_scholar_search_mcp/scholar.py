from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, TypeVar

from scholarly import ProxyGenerator, scholarly
from scholarly.data_types import PublicationSource

from .errors import ScholarInvalidArgumentError, ScholarNotFoundError
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


def require_identifier(
    title: str | None, scholar_id: str | None, author_pub_id: str | None
) -> None:
    """Ensure at least one way to identify a paper was given.

    Args:
        title (str | None): Paper title.
        scholar_id (str | None): Scholar cluster id (``PaperResult.scholar_id``).
        author_pub_id (str | None): Author-profile publication id
            (``PaperResult.author_pub_id``).

    Raises:
        ScholarInvalidArgumentError: If all three are empty.
    """
    if not any(v and v.strip() for v in (title, scholar_id, author_pub_id)):
        raise ScholarInvalidArgumentError(
            "Provide one of: author_pub_id, scholar_id or title. IDs come from "
            "earlier search results and are more reliable than titles."
        )


def require_author_identifier(name: str | None, scholar_id: str | None) -> None:
    """Ensure an author can be identified.

    Args:
        name (str | None): Author name.
        scholar_id (str | None): Scholar profile id.

    Raises:
        ScholarInvalidArgumentError: If both are empty.
    """
    if not any(v and v.strip() for v in (name, scholar_id)):
        raise ScholarInvalidArgumentError(
            "Provide scholar_id (from an earlier author result) or name."
        )


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

    def _locate_pub(
        self,
        title: str | None,
        scholar_id: str | None,
        author_pub_id: str | None,
        *,
        fill: bool,
    ) -> dict:
        """Resolve a paper from an ID or title, preferring the most exact ID.

        Precedence: ``author_pub_id`` > ``scholar_id`` > ``title``.

        Args:
            title (str | None): Paper title; best search hit is used.
            scholar_id (str | None): Scholar cluster id; the first entry of the
                cluster (the paper's best version) is used.
            author_pub_id (str | None): Author-profile publication id
                (``"<author>:<publication>"``).
            fill (bool): Fetch the full record. Always done for
                ``author_pub_id``, whose stub is useless unfilled.

        Returns:
            dict: ``scholarly`` publication.

        Raises:
            ScholarInvalidArgumentError: If no identifier is given.
            ScholarNotFoundError: If nothing matches.
        """
        require_identifier(title, scholar_id, author_pub_id)
        if author_pub_id and author_pub_id.strip():
            stub = {
                "container_type": "Publication",
                "source": PublicationSource.AUTHOR_PUBLICATION_ENTRY,
                "author_pub_id": author_pub_id.strip(),
                "bib": {},
                "filled": False,
            }
            try:
                return scholarly.fill(stub)
            except (AttributeError, IndexError, KeyError) as e:
                raise ScholarNotFoundError(
                    f"No Google Scholar publication for author_pub_id "
                    f"{author_pub_id!r} (unknown id, or Scholar returned an "
                    "unexpected page). Use an id from a search_author result."
                ) from e
        if scholar_id and scholar_id.strip():
            cluster = scholar_id.strip()
            results = scholarly.search_pubs_custom_url(
                f"/scholar?hl=en&cluster={cluster}"
            )
            pub = _first(results, f"scholar_id {cluster!r}")
        else:
            results = scholarly.search_pubs(title)
            pub = _first(results, f"title {title!r}")
        return scholarly.fill(pub) if fill else pub

    def get_paper_details(
        self,
        title: str | None = None,
        *,
        scholar_id: str | None = None,
        author_pub_id: str | None = None,
    ) -> PaperDetails:
        """Fetch full details and BibTeX of a paper.

        Args:
            title (str | None): Paper title (best search hit is used).
            scholar_id (str | None): Scholar cluster id from a search result.
            author_pub_id (str | None): Author-profile publication id.

        Returns:
            PaperDetails: Details of the identified paper.

        Raises:
            ScholarInvalidArgumentError: If no identifier is given.
            ScholarNotFoundError: If nothing matches.
        """
        self._ensure_initialized()
        pub = self._locate_pub(title, scholar_id, author_pub_id, fill=True)
        return self._pub_to_paper_details(pub)

    def search_author(
        self,
        name: str | None = None,
        max_pubs: int = 5,
        *,
        scholar_id: str | None = None,
    ) -> AuthorResult:
        """Look up an author profile by Scholar id or by name.

        Args:
            name (str | None): Author name; the first match is used.
            max_pubs (int): Number of publications to load.
            scholar_id (str | None): Scholar profile id (``AuthorResult.scholar_id``).
                Takes precedence over ``name``.

        Returns:
            AuthorResult: The author profile.

        Raises:
            ScholarInvalidArgumentError: If neither ``name`` nor ``scholar_id`` is given.
            ScholarNotFoundError: If no author matches.
        """
        require_author_identifier(name, scholar_id)
        self._ensure_initialized()
        if scholar_id and scholar_id.strip():
            author_id = scholar_id.strip()
            try:
                author = scholarly.search_author_id(author_id)
                author = scholarly.fill(
                    author,
                    sections=["basics", "indices", "publications"],
                    publication_limit=max_pubs,
                )
            except (AttributeError, IndexError, KeyError) as e:
                raise ScholarNotFoundError(
                    f"No Google Scholar author for scholar_id {author_id!r} "
                    "(unknown id, or Scholar returned an unexpected page)."
                ) from e
            return self._author_to_result(author)
        search = scholarly.search_author(name)
        author = _first(search, f"author {name!r}")
        author = scholarly.fill(
            author,
            sections=["basics", "indices", "publications"],
            publication_limit=max_pubs,
        )
        return self._author_to_result(author)

    def get_citations(
        self,
        title: str | None = None,
        max_results: int = 10,
        *,
        scholar_id: str | None = None,
        author_pub_id: str | None = None,
    ) -> tuple[str | None, int | None, list[PaperResult]]:
        """Fetch papers that cite a paper.

        With only ``scholar_id`` the cited paper is not fetched (saving a
        request), so its title is ``None`` and the total comes from the result
        page header.

        Args:
            title (str | None): Title of the cited paper.
            max_results (int): Maximum number of citing papers to return.
            scholar_id (str | None): Scholar cluster id from a search result.
            author_pub_id (str | None): Author-profile publication id.

        Returns:
            tuple[str | None, int | None, list[PaperResult]]: The cited paper's
            title (if known), its total citation count (if known) and the
            citing papers.

        Raises:
            ScholarInvalidArgumentError: If no identifier is given.
            ScholarNotFoundError: If the paper is not found.
        """
        require_identifier(title, scholar_id, author_pub_id)
        self._ensure_initialized()
        cited_title: str | None
        total: int | None
        if (author_pub_id and author_pub_id.strip()) or not (
            scholar_id and scholar_id.strip()
        ):
            pub = self._locate_pub(title, None, author_pub_id, fill=False)
            total = pub.get("num_citations", 0)
            citing = scholarly.citedby(pub)
            cited_title = pub.get("bib", {}).get("title", title)
        else:
            citing = scholarly.search_citedby(scholar_id.strip())  # type: ignore[union-attr]
            total = _safe_int(getattr(citing, "total_results", None))
            cited_title = None
        papers: list[PaperResult] = []
        for i, cite in enumerate(citing):
            if i >= max_results:
                break
            papers.append(self._pub_to_paper_result(cite))
        return cited_title, total, papers

    def get_bibtex(
        self,
        title: str | None = None,
        *,
        scholar_id: str | None = None,
        author_pub_id: str | None = None,
    ) -> str:
        """Get the BibTeX entry of a paper.

        Args:
            title (str | None): Paper title (best search hit is used).
            scholar_id (str | None): Scholar cluster id from a search result.
            author_pub_id (str | None): Author-profile publication id.

        Returns:
            str: BibTeX entry.

        Raises:
            ScholarInvalidArgumentError: If no identifier is given.
            ScholarNotFoundError: If nothing matches.
        """
        self._ensure_initialized()
        pub = self._locate_pub(title, scholar_id, author_pub_id, fill=True)
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
