"""Browser identity (cookies, User-Agent) sent with Google Scholar requests.

Scholar answers plain HTTP clients with a JavaScript bot check. A real browser
passes it once and keeps the resulting cookies. Passing those cookies (and the
matching User-Agent) from the user's own browser lets ``scholarly`` reuse that
verified session. This is experimental: the cookies expire and are typically
tied to the IP address and User-Agent they were issued for.

Cookie values are credentials. They are never logged or printed here, and
``Config`` hides them from ``repr``. Only cookie *names* are ever shown.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

import httpx

SCHOLAR_HOST = "scholar.google.com"

# Cookies that identify a logged-in Google account. They must not be used here.
LOGIN_COOKIE_NAMES = frozenset(
    {
        "SID",
        "HSID",
        "SSID",
        "APISID",
        "SAPISID",
        "LSID",
        "OSID",
        "__Secure-1PSID",
        "__Secure-3PSID",
        "__Secure-1PAPISID",
        "__Secure-3PAPISID",
        "__Secure-1PSIDTS",
        "__Secure-3PSIDTS",
        "__Secure-1PSIDCC",
        "__Secure-3PSIDCC",
        "SIDCC",
    }
)


def parse_cookies(text: str | None) -> dict[str, str]:
    """Parse copied cookies into a name -> value mapping.

    Accepts a ``Cookie`` header (``a=1; b=2``, optional leading ``Cookie:``,
    possibly wrapped over several lines) or the tab-separated table copied from
    the browser's Application/Storage tab (one cookie per line, name first,
    value second).

    Args:
        text (str | None): Cookie text as copied from the browser.

    Returns:
        dict[str, str]: Cookies in order; empty for blank input. Parts without
        a name or value separator are ignored.
    """
    if not text or not text.strip():
        return {}
    if "\t" in text:
        table: dict[str, str] = {}
        for line in text.splitlines():
            columns = line.split("\t")
            if (
                len(columns) >= 2
                and columns[0].strip()
                and columns[0].strip() != "Name"
            ):
                table[columns[0].strip()] = columns[1].strip()
        if table:
            return table
    cleaned = " ".join(text.split())
    if cleaned.lower().startswith("cookie:"):
        cleaned = cleaned[len("cookie:") :]
    cookies: dict[str, str] = {}
    for part in cleaned.split(";"):
        name, sep, value = part.strip().partition("=")
        if sep and name.strip():
            cookies[name.strip()] = value.strip()
    return cookies


def default_cookie_file() -> Path:
    """Where ``set-cookies`` saves the identity and the server looks for it.

    Returns:
        Path: ``$XDG_CONFIG_HOME/google-scholar-mcp/cookies`` (``~/.config``
        when the variable is unset). The file need not exist.
    """
    base = os.getenv("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base).expanduser() / "google-scholar-mcp" / "cookies"


def split_identity(text: str | None) -> tuple[str | None, str | None]:
    """Split the contents of a cookie file into cookies and User-Agent.

    A cookie file may carry the browser's User-Agent on a line of its own
    (``User-Agent: Mozilla/5.0 ...``), as ``set-cookies`` writes it, so one
    file describes the whole identity.

    Args:
        text (str | None): File contents.

    Returns:
        tuple[str | None, str | None]: Cookie text (everything else) and the
        User-Agent, each ``None`` when absent.
    """
    if not text or not text.strip():
        return None, None
    user_agent: str | None = None
    rest: list[str] = []
    for line in text.splitlines():
        if line.strip().lower().startswith("user-agent:"):
            user_agent = line.split(":", 1)[1].strip() or None
        else:
            rest.append(line)
    cookies = "\n".join(rest).strip()
    return cookies or None, user_agent


def write_identity_file(path: Path, cookies: dict[str, str], user_agent: str) -> None:
    """Save cookies and User-Agent to a file only the owner can read.

    Args:
        path (Path): Destination; parent directories are created.
        cookies (dict[str, str]): Cookie names and values.
        user_agent (str): The browser's User-Agent.
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    header = "; ".join(f"{name}={value}" for name, value in cookies.items())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(f"User-Agent: {user_agent}\nCookie: {header}\n")
    os.chmod(path, 0o600)


def login_cookie_names(cookies: dict[str, str]) -> list[str]:
    """Return the names of any Google *login* cookies in a cookie set.

    Args:
        cookies (dict[str, str]): Parsed cookies.

    Returns:
        list[str]: Offending cookie names (never values), sorted.
    """
    return sorted(name for name in cookies if name in LOGIN_COOKIE_NAMES)


@dataclass
class _Identity:
    """Process-wide identity applied to Scholar requests."""

    cookies: dict[str, str] = field(default_factory=dict)
    user_agent: str | None = None


_identity = _Identity()
_lock = threading.Lock()


def set_identity(cookies: str | None, user_agent: str | None) -> None:
    """Configure the identity used for all following Scholar requests.

    Args:
        cookies (str | None): ``Cookie`` header text, or ``None`` for none.
        user_agent (str | None): User-Agent to send, or ``None`` to keep
            ``scholarly``'s own.
    """
    with _lock:
        _identity.cookies = parse_cookies(cookies)
        _identity.user_agent = user_agent.strip() if user_agent else None


def current_cookie_names() -> list[str]:
    """Names of the configured cookies (for diagnostics; never the values).

    Returns:
        list[str]: Cookie names in configured order.
    """
    with _lock:
        return list(_identity.cookies)


def apply_identity(request: httpx.Request) -> None:
    """Add the configured cookies and User-Agent to a Scholar request.

    Cookies already on the request (from the client's own jar, e.g. refreshed
    by Scholar's ``Set-Cookie``) win over the configured ones of the same name.
    Requests to other hosts are left alone.

    Args:
        request (httpx.Request): Request about to be sent; modified in place.
    """
    if request.url.host != SCHOLAR_HOST:
        return
    with _lock:
        configured = dict(_identity.cookies)
        user_agent = _identity.user_agent
    if configured:
        merged = {**configured, **parse_cookies(request.headers.get("cookie"))}
        request.headers["cookie"] = "; ".join(f"{k}={v}" for k, v in merged.items())
    if user_agent:
        request.headers["user-agent"] = user_agent
