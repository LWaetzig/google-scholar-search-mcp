"""``google-scholar-mcp set-cookies``: save a browser identity copied from dev tools.

Google Scholar only answers a client that passed its bot check, and that check
(often a CAPTCHA) needs a person in an ordinary browser. This command takes
what the browser's developer tools copy for a Scholar request, either
"Copy request headers" or "Copy as cURL", pulls out the cookies and the
User-Agent, saves them where the server finds them, and runs ``doctor``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from ..session_identity import (
    default_cookie_file,
    login_cookie_names,
    parse_cookies,
    write_identity_file,
)
from . import doctor

_CLIPBOARD_COMMANDS = (
    ("pbpaste",),
    ("wl-paste", "--no-newline"),
    ("xclip", "-selection", "clipboard", "-o"),
    ("xsel", "--clipboard", "--output"),
    ("powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"),
)
_CURL_HEADER = re.compile(r"""-H\s+(?:\$?'([^']*)'|"([^"]*)")""")
_CURL_COOKIE = re.compile(r"""(?:-b|--cookie)\s+(?:\$?'([^']*)'|"([^"]*)")""")


def read_clipboard() -> str | None:
    """Read text from the system clipboard.

    Returns:
        str | None: Clipboard text, or ``None`` when no clipboard tool is
        available or it failed.
    """
    for command in _CLIPBOARD_COMMANDS:
        if shutil.which(command[0]) is None:
            continue
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if done.returncode == 0:
            return done.stdout
    return None


def extract_identity(text: str) -> tuple[dict[str, str], str | None]:
    """Pull cookies and User-Agent out of text copied from developer tools.

    Understands "Copy as cURL", "Copy request headers" (``name: value`` lines,
    in Chrome's and Firefox's spelling) and a bare ``Cookie`` header value.

    Args:
        text (str): Copied text.

    Returns:
        tuple[dict[str, str], str | None]: Cookies (empty if none found) and
        the User-Agent, if the text contained one.
    """
    headers: dict[str, str] = {}
    curl_cookie: str | None = None
    if re.search(r"(^|\s)curl\s", text):
        for match in _CURL_HEADER.finditer(text):
            name, sep, value = (match.group(1) or match.group(2) or "").partition(":")
            if sep:
                headers[name.strip().lower()] = value.strip()
        found = _CURL_COOKIE.search(text)
        if found:
            curl_cookie = found.group(1) or found.group(2)
    else:
        for line in text.splitlines():
            name, sep, value = line.strip().partition(":")
            if sep and name.strip().lower() in ("cookie", "user-agent"):
                headers[name.strip().lower()] = value.strip()
    cookie_text = headers.get("cookie") or curl_cookie
    if cookie_text is None and "user-agent" not in headers:
        cookie_text = text  # a bare cookie header value
    return parse_cookies(cookie_text), headers.get("user-agent") or None


def target_file() -> Path:
    """Where the identity is saved: ``GS_COOKIES_FILE`` or the default file.

    Returns:
        Path: Destination file.
    """
    configured = os.getenv("GS_COOKIES_FILE")
    return Path(configured).expanduser() if configured else default_cookie_file()


def run(
    *,
    from_stdin: bool = False,
    user_agent: str | None = None,
    out: TextIO | None = None,
    source: Callable[[], str | None] | None = None,
    verify: Callable[[], int] | None = None,
) -> int:
    """Save cookies and User-Agent copied from the browser, then check them.

    Cookie values are never printed.

    Args:
        from_stdin (bool): Read the copied text from stdin, not the clipboard.
        user_agent (str | None): User-Agent to use when the copied text has none.
        out (TextIO | None): Where to print; defaults to stdout.
        source (Callable[[], str | None] | None): Supplies the copied text
            (replaced in tests).
        verify (Callable[[], int] | None): Checks the saved identity; defaults
            to ``doctor``.

    Returns:
        int: ``0`` saved and accepted by Scholar, ``1`` saved but Scholar
        still blocks, ``2`` nothing was saved.
    """
    out = out or sys.stdout

    def say(line: str = "") -> None:
        print(line, file=out)

    if source is None:
        source = sys.stdin.read if from_stdin else read_clipboard
    text = source()
    if text is None:
        say("No clipboard tool found. Pipe the copied text in instead:")
        say("  google-scholar-mcp set-cookies --stdin < copied.txt")
        return doctor.ERROR
    cookies, copied_agent = extract_identity(text)
    agent = user_agent or copied_agent or os.getenv("GS_USER_AGENT")
    if not cookies:
        say("No cookies found in the copied text. In the browser's developer tools,")
        say("Network tab, right-click the `scholar?...` request and choose")
        say("Copy > Copy as cURL (or Copy request headers), then run this again.")
        return doctor.ERROR
    risky = login_cookie_names(cookies)
    if risky:
        say(f"These are cookies of a signed-in Google account ({', '.join(risky)}).")
        say("Account cookies are never saved. Use a private window where you are NOT")
        say("signed in, and copy from there.")
        return doctor.ERROR
    if not agent:
        say("The copied text has no User-Agent, and Scholar ties cookies to it.")
        say("Copy with 'Copy as cURL' / 'Copy request headers', or pass --user-agent.")
        return doctor.ERROR

    path = target_file()
    write_identity_file(path, cookies, agent)
    say(f"Saved {len(cookies)} cookies ({', '.join(cookies)}) and the User-Agent to")
    say(f"  {path}")
    if not os.getenv("GS_COOKIES_FILE"):
        if os.getenv("GS_COOKIES"):
            say(
                "NOTE: GS_COOKIES is set and takes precedence over this file. Unset it."
            )
        else:
            say("The server reads this file automatically; no variables needed.")
    if os.getenv("GS_USER_AGENT") and os.getenv("GS_USER_AGENT") != agent:
        say("NOTE: GS_USER_AGENT is set and overrides the saved User-Agent. Unset it.")
    say("Restart the MCP server (Claude Desktop / Claude Code) to use them.\n")
    return (verify or doctor.run)()
