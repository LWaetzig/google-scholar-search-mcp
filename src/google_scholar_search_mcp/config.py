from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


DEFAULT_SKILL_URL = (
    "https://raw.githubusercontent.com/LWaetzig/google-scholar-mcp/main/"
    "src/google_scholar_search_mcp/skills/google-scholar-mcp/SKILL.md"
)


class ProxyType(str, Enum):
    """Proxy strategy used for Google Scholar requests (``GS_PROXY_TYPE``)."""

    NONE = "none"
    FREE = "free"
    SINGLE = "single"
    SCRAPERAPI = "scraperapi"


@dataclass(frozen=True)
class Config:
    """Immutable server settings, normally built with :meth:`from_env`."""

    min_delay_seconds: float
    max_delay_seconds: float
    max_retries: int
    proxy_type: ProxyType
    proxy_http: str | None
    proxy_https: str | None
    scraperapi_key: str | None
    timeout_seconds: int
    skill_url: str = DEFAULT_SKILL_URL

    @classmethod
    def from_env(cls) -> Config:
        """Build a configuration from ``GS_*`` environment variables.

        Returns:
            Config: Settings read from the environment, with defaults for
            unset variables.

        Raises:
            ValueError: If a numeric variable is not a number or
                ``GS_PROXY_TYPE`` is not one of ``none``, ``free``,
                ``single`` or ``scraperapi``.
        """
        return cls(
            min_delay_seconds=float(os.getenv("GS_MIN_DELAY", "5.0")),
            max_delay_seconds=float(os.getenv("GS_MAX_DELAY", "15.0")),
            max_retries=int(os.getenv("GS_MAX_RETRIES", "3")),
            proxy_type=ProxyType(os.getenv("GS_PROXY_TYPE", "none").lower()),
            proxy_http=os.getenv("GS_PROXY_HTTP"),
            proxy_https=os.getenv("GS_PROXY_HTTPS"),
            scraperapi_key=os.getenv("GS_SCRAPERAPI_KEY"),
            timeout_seconds=int(os.getenv("GS_TIMEOUT", "30")),
            skill_url=os.getenv("GS_SKILL_URL", DEFAULT_SKILL_URL),
        )
