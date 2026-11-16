"""``google-scholar-mcp doctor``: check whether Google Scholar answers this client."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import httpx

from ..block_detector import BlockDetector, classify
from ..config import Config
from ..session_identity import (
    current_cookie_names,
    default_cookie_file,
    login_cookie_names,
    parse_cookies,
    set_identity,
    split_identity,
)

PAPERS_URL = "https://scholar.google.com/scholar?hl=en&q=attention+is+all+you+need"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

OK, BLOCKED, ERROR = 0, 1, 2


@dataclass(frozen=True)
class Probe:
    """Outcome of one request.

    Attributes:
        label (str): Which part of Scholar was asked.
        status (int): :data:`OK`, :data:`BLOCKED` or :data:`ERROR`.
        detail (str): One-line explanation.
    """

    label: str
    status: int
    detail: str


def describe_cookie_source() -> tuple[str, bool]:
    """Say where cookies are expected from and whether that source is usable.

    Only sizes and counts are reported, never contents.

    Returns:
        tuple[str, bool]: A one-line description, and ``True`` when the source
        exists and holds at least one cookie.
    """
    path = os.getenv("GS_COOKIES_FILE")
    if path:
        file = Path(path).expanduser()
        if not file.is_file():
            return f"GS_COOKIES_FILE={path} -> file not found", False
        return _describe_file(f"GS_COOKIES_FILE={path}", file)
    if os.getenv("GS_COOKIES"):
        found = len(parse_cookies(os.getenv("GS_COOKIES")))
        return f"GS_COOKIES ({found} cookies parsed)", found > 0
    default = default_cookie_file()
    if default.is_file():
        return _describe_file(str(default), default)
    return (
        "neither GS_COOKIES_FILE nor GS_COOKIES is set in this shell, and "
        f"{default} does not exist (run: google-scholar-mcp set-cookies)",
        False,
    )


def _describe_file(label: str, file: Path) -> tuple[str, bool]:
    """Describe a cookie file by size and counts, never by contents.

    Args:
        label (str): How to name the file in the report.
        file (Path): Existing cookie file.

    Returns:
        tuple[str, bool]: Description, and whether it holds any cookie.
    """
    text = file.read_text(encoding="utf-8", errors="replace")
    cookies, agent = split_identity(text)
    found = len(parse_cookies(cookies))
    extra = ", with User-Agent" if agent else ""
    return f"{label} ({len(text)} characters, {found} cookies parsed{extra})", found > 0


def probe(http: httpx.Client, url: str, label: str, results_marker: str) -> Probe:
    """Request one Scholar page and classify the answer.

    Args:
        http (httpx.Client): Client to use.
        url (str): Page to request.
        label (str): Name of the part of Scholar, for the report.
        results_marker (str): Text that only a genuine results page contains.

    Returns:
        Probe: What happened.
    """
    try:
        response = http.get(url)
    except httpx.HTTPError as e:
        return Probe(label, ERROR, f"could not reach Scholar ({type(e).__name__})")
    reason = classify(response)
    if reason is not None:
        return Probe(label, BLOCKED, reason)
    if response.status_code != 200:
        return Probe(label, ERROR, f"unexpected HTTP {response.status_code}")
    if results_marker not in response.text:
        return Probe(label, ERROR, "HTTP 200 but not a recognisable results page")
    return Probe(label, OK, "returned a results page")


def run(
    config: Config | None = None,
    *,
    client: httpx.Client | None = None,
    out: TextIO | None = None,
) -> int:
    """Check that Google Scholar answers with a results page (one request).

    Cookie values are never printed, only their names and count.

    Args:
        config (Config | None): Settings; defaults to the environment.
        client (httpx.Client | None): HTTP client, for tests.
        out (TextIO | None): Where to print; defaults to stdout.

    Returns:
        int: ``0`` both parts answer, ``1`` at least one is blocking this
        client, ``2`` something else went wrong.
    """
    out = out or sys.stdout
    config = config or Config.from_env()

    def say(line: str = "") -> None:
        print(line, file=out)

    BlockDetector(config.block_cooldown_seconds)  # installs the identity hook
    set_identity(config.cookies, config.user_agent)
    names = current_cookie_names()
    say("Google Scholar check")
    say(
        f"  cookies configured : {len(names)}"
        + (f" ({', '.join(names)})" if names else "")
    )
    say(f"  user agent         : {'custom' if config.user_agent else 'default'}")
    source, usable = describe_cookie_source()
    say(f"  cookie source      : {source}")
    if not usable:
        say("\n  No usable cookies. Easiest: run `google-scholar-mcp set-cookies`.")
        say("  If you set them by hand, check that:")
        say("   - the variable is exported in THIS shell (run: echo $GS_COOKIES_FILE)")
        say(
            "   - the file holds one line like  NID=...; GSP=...  (the `cookie` request header)"
        )
        say(
            "   - if the server runs inside Claude Desktop/Code, the variable is set in its"
        )
        say("     MCP server `env` config, not only in your terminal")
    risky = login_cookie_names(parse_cookies(config.cookies))
    if risky:
        say(f"  WARNING: login cookies present ({', '.join(risky)}).")
        say("           Use cookies from a private window where you are NOT logged in.")

    owns_client = client is None
    http = client or httpx.Client(
        headers={"User-Agent": DEFAULT_USER_AGENT},
        follow_redirects=True,
        timeout=config.timeout_seconds,
    )
    say("\nRequesting one results page from Google Scholar ...")
    try:
        result = probe(http, PAPERS_URL, "paper search", "gs_ri")
    finally:
        if owns_client:
            http.close()

    say()
    tag = {OK: "OK     ", BLOCKED: "BLOCKED", ERROR: "ERROR  "}[result.status]
    say(f"  {tag} {result.label:<14} {result.detail}")

    if result.status == OK:
        say("\nOK: Google Scholar answers.")
        if names:
            say(
                "  Your cookies work. They expire; re-run this if searches start failing."
            )
        return OK

    if result.status == BLOCKED:
        say("\nBLOCKED: Scholar refuses this client.")
        if names:
            say("  Your cookies did not get past it. They may be expired, or tied to a")
            say(
                "  different IP address / User-Agent than this machine uses. Re-copy them"
            )
            say("  from a fresh private window on THIS network, with its User-Agent.")
        else:
            say("  Scholar wants a real browser. Run `google-scholar-mcp set-cookies`")
            say(
                "  (or set cookies by hand, see the README), a JavaScript-capable proxy"
            )
            say("  (GS_PROXY_TYPE=scraperapi) or another network.")
        return BLOCKED
    return ERROR
