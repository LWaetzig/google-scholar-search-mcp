from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .session_identity import default_cookie_file, split_identity


DEFAULT_SKILL_URL = (
    "https://raw.githubusercontent.com/LWaetzig/google-scholar-mcp/main/"
    "src/google_scholar_search_mcp/skills/google-scholar-mcp/SKILL.md"
)


def _read_identity() -> tuple[str | None, str | None]:
    """Read the browser cookies and User-Agent.

    Sources, first match wins: ``GS_COOKIES_FILE``, ``GS_COOKIES``, then the
    default file written by ``google-scholar-mcp set-cookies``. A file is
    preferred: it keeps credentials out of client config files and shell
    history, and can carry the User-Agent too. ``GS_USER_AGENT`` overrides a
    User-Agent found in the file.

    Returns:
        tuple[str | None, str | None]: ``Cookie`` header text and User-Agent,
        each ``None`` if not configured.

    Raises:
        ValueError: If ``GS_COOKIES_FILE`` cannot be read (the message names the
            path, never the contents).
    """
    env_agent = os.getenv("GS_USER_AGENT") or None
    path = os.getenv("GS_COOKIES_FILE")
    if path:
        try:
            text = Path(path).expanduser().read_text(encoding="utf-8")
        except OSError as e:
            raise ValueError(
                f"GS_COOKIES_FILE {path!r} cannot be read: {e.strerror}"
            ) from e
        cookies, agent = split_identity(text)
        return cookies, env_agent or agent
    if os.getenv("GS_COOKIES"):
        return os.getenv("GS_COOKIES"), env_agent
    try:
        text = default_cookie_file().read_text(encoding="utf-8")
    except OSError:
        return None, env_agent
    cookies, agent = split_identity(text)
    return cookies, env_agent or agent


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
    scraperapi_key: str | None = field(repr=False)
    timeout_seconds: int
    skill_url: str = DEFAULT_SKILL_URL
    block_cooldown_seconds: float = 900.0
    cache_ttl_seconds: float = 3600.0
    cache_max_entries: int = 256
    cookies: str | None = field(default=None, repr=False)
    user_agent: str | None = None

    @classmethod
    def from_env(cls) -> Config:
        """Build a configuration from ``GS_*`` environment variables.

        Returns:
            Config: Settings read from the environment, with defaults for
            unset variables.

        Raises:
            ValueError: If a numeric variable is not a number,
                ``GS_PROXY_TYPE`` is not one of ``none``, ``free``,
                ``single`` or ``scraperapi``, or ``GS_COOKIES_FILE`` is
                unreadable.
        """
        cookies, user_agent = _read_identity()
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
            block_cooldown_seconds=float(os.getenv("GS_BLOCK_COOLDOWN", "900")),
            cache_ttl_seconds=float(os.getenv("GS_CACHE_TTL", "3600")),
            cache_max_entries=int(os.getenv("GS_CACHE_SIZE", "256")),
            cookies=cookies,
            user_agent=user_agent,
        )
