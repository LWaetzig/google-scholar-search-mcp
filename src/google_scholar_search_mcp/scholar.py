from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from typing import TYPE_CHECKING, TypeVar

from scholarly import ProxyGenerator, scholarly

from .block_detector import BlockDetector
from .errors import (
    ScholarBlockedError,
    ScholarInvalidArgumentError,
    ScholarNotFoundError,
)
from .models import PaperDetails, PaperResult
from .session_identity import login_cookie_names, parse_cookies, set_identity
from .throttle import throttle

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


_CITES_PARAM = re.compile(r"[?&]cites=(\d+)")


def _scholar_id_of(pub: dict) -> str | None:
    """Find the Scholar cluster id of a ``scholarly`` publication.

    Search results carry it only inside their "Cited by" link
    (``citedby_url``, ``...?cites=<id>``); profile entries have ``cites_id``.
    A paper nobody cites has neither.

    Args:
        pub (dict): Publication as returned by ``scholarly``.

    Returns:
        str | None: The id, or ``None`` if the publication has none.
    """
    cites_id = pub.get("cites_id")
    if isinstance(cites_id, list) and cites_id:
        return str(cites_id[0])
    found = _CITES_PARAM.search(str(pub.get("citedby_url") or ""))
    return found.group(1) if found else None


def require_identifier(title: str | None, scholar_id: str | None) -> None:
    """Ensure at least one way to identify a paper was given.

    Args:
        title (str | None): Paper title.
        scholar_id (str | None): Scholar cluster id (``PaperResult.scholar_id``).

    Raises:
        ScholarInvalidArgumentError: If both are empty.
    """
    if not any(v and v.strip() for v in (title, scholar_id)):
        raise ScholarInvalidArgumentError(
            "Provide scholar_id (from an earlier search result) or title. IDs are "
            "more reliable than titles."
        )


class ScholarClient:
    """Synchronous wrapper around ``scholarly`` that returns typed models."""

    def __init__(self, config: Config) -> None:
        """Create a client; ``scholarly`` is configured lazily on first use.

        Args:
            config (Config): Timeout, retry, proxy, cookie and cooldown settings.
        """
        self._config = config
        self._initialized = False
        self._detector = BlockDetector(config.block_cooldown_seconds)
        set_identity(config.cookies, config.user_agent)
        throttle.configure(config.min_delay_seconds, config.max_delay_seconds)
        risky = login_cookie_names(parse_cookies(config.cookies))
        if risky:
            logger.warning(
                "GS_COOKIES contains Google LOGIN cookies (%s). Use cookies from a "
                "private window where you are NOT logged in.",
                ", ".join(risky),
            )

    def ensure_available(self) -> None:
        """Fail fast while Scholar is known to be blocking this client.

        Raises:
            ScholarBlockedError: During the cooldown after a detected block.
        """
        remaining = self._detector.cooldown_remaining()
        if remaining > 0:
            raise ScholarBlockedError(
                f"Google Scholar blocked this client recently; not retrying for "
                f"another {remaining / 60:.0f} min to avoid making it worse "
                "(GS_BLOCK_COOLDOWN). Do not retry now; tell the user."
            )

    def _raise_if_blocked(self) -> None:
        """Turn a block seen during this call into :class:`ScholarBlockedError`.

        Raises:
            ScholarBlockedError: If a response was a bot-check or sign-in page.
        """
        reason = self._detector.reason
        if reason is None:
            return
        self._detector.trip()
        if self._config.cookies:
            advice = (
                "The configured browser cookies (GS_COOKIES / GS_COOKIES_FILE) were "
                "not accepted: they have probably expired. Tell the user to renew "
                "them with `google-scholar-mcp set-cookies` (README: 'Using "
                "browser cookies') and restart the server."
            )
        else:
            advice = (
                "Waiting, another network, browser cookies (run "
                "`google-scholar-mcp set-cookies`) or a JavaScript-capable "
                "proxy (GS_PROXY_TYPE=scraperapi) may help."
            )
        raise ScholarBlockedError(
            f"Google Scholar is blocking this client ({reason}); it returns a "
            f"bot check instead of results. Do not retry now; tell the user. {advice}"
        )

    def _first(self, results: Iterator[T], what: str) -> T:
        """Return the first item of a ``scholarly`` result iterator.

        Args:
            results (Iterator[T]): Lazy search results.
            what (str): Description of the lookup, used in the error message.

        Returns:
            T: The first result.

        Raises:
            ScholarBlockedError: If the empty result is a block page.
            ScholarNotFoundError: If the iterator is empty. A bare
                ``StopIteration`` must not leave a worker thread, as it cannot
                propagate through an ``asyncio`` future.
        """
        try:
            return next(results)
        except StopIteration:
            self._raise_if_blocked()
            raise ScholarNotFoundError(
                f"No Google Scholar result for {what}. Try the exact title from a "
                "search result, fewer words, or a different spelling."
            ) from None

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
        offset: int = 0,
    ) -> list[PaperResult]:
        """Search publications by keyword.

        Args:
            query (str): Search query.
            max_results (int): Maximum number of papers to return.
            year_low (int | None): Earliest publication year.
            year_high (int | None): Latest publication year.
            sort_by (str): ``"relevance"`` or ``"date"``.
            patents (bool): Whether to include patents.
            offset (int): Number of leading results to skip (for paging).

        Returns:
            list[PaperResult]: Up to ``max_results`` papers, starting at
            ``offset``; empty when the offset is past the last result.

        Raises:
            ScholarBlockedError: If Scholar answers with a bot check instead
                of results.
            MaxTriesExceededException: If Scholar blocks the request
                (raised by ``scholarly``).
        """
        self._ensure_initialized()
        self._detector.reset()
        results = scholarly.search_pubs(
            query,
            year_low=year_low,
            year_high=year_high,
            sort_by=sort_by,
            patents=patents,
            start_index=offset,
        )
        papers: list[PaperResult] = []
        for i, pub in enumerate(results):
            if i >= max_results:
                break
            papers.append(self._pub_to_paper_result(pub))
        if not papers:
            self._raise_if_blocked()
        return papers

    def _locate_pub(
        self,
        title: str | None,
        scholar_id: str | None,
        *,
        fill: bool,
    ) -> dict:
        """Resolve a paper from an ID or title, preferring the ID.

        Args:
            title (str | None): Paper title; best search hit is used.
            scholar_id (str | None): Scholar cluster id; the first entry of the
                cluster (the paper's best version) is used.
            fill (bool): Fetch the full record.

        Returns:
            dict: ``scholarly`` publication.

        Raises:
            ScholarInvalidArgumentError: If no identifier is given.
            ScholarNotFoundError: If nothing matches.
        """
        require_identifier(title, scholar_id)
        if scholar_id and scholar_id.strip():
            cluster = scholar_id.strip()
            results = scholarly.search_pubs_custom_url(
                f"/scholar?hl=en&cluster={cluster}"
            )
            pub = self._first(results, f"scholar_id {cluster!r}")
        else:
            results = scholarly.search_pubs(title)
            pub = self._first(results, f"title {title!r}")
        return scholarly.fill(pub) if fill else pub

    def get_paper_details(
        self,
        title: str | None = None,
        *,
        scholar_id: str | None = None,
    ) -> PaperDetails:
        """Fetch full details and BibTeX of a paper.

        Args:
            title (str | None): Paper title (best search hit is used).
            scholar_id (str | None): Scholar cluster id from a search result.

        Returns:
            PaperDetails: Details of the identified paper.

        Raises:
            ScholarInvalidArgumentError: If no identifier is given.
            ScholarNotFoundError: If nothing matches.
        """
        self._ensure_initialized()
        self._detector.reset()
        pub = self._locate_pub(title, scholar_id, fill=True)
        return self._pub_to_paper_details(pub)

    def get_citations(
        self,
        title: str | None = None,
        max_results: int = 10,
        *,
        scholar_id: str | None = None,
        offset: int = 0,
    ) -> tuple[str | None, int | None, list[PaperResult]]:
        """Fetch papers that cite a paper.

        With ``scholar_id`` the cited paper is not fetched (saving a request),
        so its title is ``None`` and the total comes from the result page
        header.

        Args:
            title (str | None): Title of the cited paper.
            max_results (int): Maximum number of citing papers to return.
            scholar_id (str | None): Scholar cluster id from a search result.
            offset (int): Number of leading citing papers to skip (for paging).

        Returns:
            tuple[str | None, int | None, list[PaperResult]]: The cited paper's
            title (if known), its total citation count (if known) and the
            citing papers.

        Raises:
            ScholarInvalidArgumentError: If no identifier is given.
            ScholarNotFoundError: If the paper is not found.
        """
        require_identifier(title, scholar_id)
        self._ensure_initialized()
        self._detector.reset()
        cited_title: str | None
        total: int | None
        paging = {"start_index": offset} if offset > 0 else {}
        if scholar_id and scholar_id.strip():
            citing = scholarly.search_citedby(scholar_id.strip(), **paging)
            total = _safe_int(getattr(citing, "total_results", None))
            cited_title = None
        else:
            pub = self._locate_pub(title, None, fill=False)
            total = pub.get("num_citations", 0)
            cited_title = pub.get("bib", {}).get("title", title)
            cluster = _scholar_id_of(pub)
            if cluster:
                # One plain request per page. ``scholarly.citedby`` would walk
                # the citations year by year for papers cited over 1000 times.
                citing = scholarly.search_citedby(cluster, **paging)
            elif offset > 0:
                citing = iter(())
            else:
                citing = scholarly.citedby(pub)
        papers: list[PaperResult] = []
        for i, cite in enumerate(citing):
            if i >= max_results:
                break
            papers.append(self._pub_to_paper_result(cite))
        if not papers:
            self._raise_if_blocked()
        return cited_title, total, papers

    def get_bibtex(
        self,
        title: str | None = None,
        *,
        scholar_id: str | None = None,
    ) -> str:
        """Get the BibTeX entry of a paper.

        Args:
            title (str | None): Paper title (best search hit is used).
            scholar_id (str | None): Scholar cluster id from a search result.

        Returns:
            str: BibTeX entry.

        Raises:
            ScholarInvalidArgumentError: If no identifier is given.
            ScholarNotFoundError: If nothing matches.
        """
        self._ensure_initialized()
        self._detector.reset()
        pub = self._locate_pub(title, scholar_id, fill=True)
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
        scholar_id = _scholar_id_of(pub)
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
