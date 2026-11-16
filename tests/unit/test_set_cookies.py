"""``set-cookies``: saving a browser identity copied from developer tools."""

from __future__ import annotations

import io
import stat
from pathlib import Path

import pytest

from google_scholar_search_mcp.cli import cookies as cookies_cmd
from google_scholar_search_mcp.cli import doctor
from google_scholar_search_mcp.config import Config
from google_scholar_search_mcp.session_identity import (
    default_cookie_file,
    parse_cookies,
    split_identity,
    write_identity_file,
)

SECRET = "s3cr3t-cookie-value-DO-NOT-LEAK"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/157.0.0.0 Safari/537.36"

CURL = f"""curl 'https://scholar.google.com/scholar?hl=en&q=x' \\
  -H 'accept: text/html' \\
  -b 'NID={SECRET}; GSP=A=1' \\
  -H 'user-agent: {UA}'"""
CURL_HEADER_COOKIE = f"""curl "https://scholar.google.com/scholar?q=x" -H "Cookie: NID={SECRET}; GSP=A=1" -H "User-Agent: {UA}" """
CHROME_HEADERS = f""":authority: scholar.google.com
:method: GET
accept: text/html
cookie: NID={SECRET}; GSP=A=1
user-agent: {UA}"""
FIREFOX_HEADERS = f"""GET /scholar?q=x HTTP/2
Host: scholar.google.com
User-Agent: {UA}
Cookie: NID={SECRET}; GSP=A=1"""


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GS_COOKIES_FILE", "GS_COOKIES", "GS_USER_AGENT"):
        monkeypatch.delenv(name, raising=False)


def _run(text: str | None, verify=lambda: doctor.OK, **kwargs) -> tuple[int, str]:
    out = io.StringIO()
    code = cookies_cmd.run(out=out, source=lambda: text, verify=verify, **kwargs)
    return code, out.getvalue()


@pytest.mark.parametrize(
    "copied", [CURL, CURL_HEADER_COOKIE, CHROME_HEADERS, FIREFOX_HEADERS]
)
def test_understands_what_browsers_copy(copied: str) -> None:
    found, agent = cookies_cmd.extract_identity(copied)

    assert found == {"NID": SECRET, "GSP": "A=1"}
    assert agent == UA


def test_a_bare_cookie_header_has_cookies_but_no_user_agent() -> None:
    found, agent = cookies_cmd.extract_identity("NID=abc; GSP=A=1")

    assert found == {"NID": "abc", "GSP": "A=1"}
    assert agent is None


def test_saves_the_identity_privately_and_never_prints_values() -> None:
    code, text = _run(CURL)

    path = default_cookie_file()
    saved, agent = split_identity(path.read_text())
    assert code == doctor.OK
    assert parse_cookies(saved) == {"NID": SECRET, "GSP": "A=1"}
    assert agent == UA
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert SECRET not in text
    assert "NID" in text
    assert "reads this file automatically" in text


def test_the_server_config_picks_the_saved_identity_up_without_any_variable() -> None:
    _run(CHROME_HEADERS)

    config = Config.from_env()

    assert parse_cookies(config.cookies) == {"NID": SECRET, "GSP": "A=1"}
    assert config.user_agent == UA


def test_gs_cookies_file_is_the_destination_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "mine.cookies"
    monkeypatch.setenv("GS_COOKIES_FILE", str(target))

    _run(CURL)

    assert target.is_file()
    assert not default_cookie_file().exists()
    assert Config.from_env().user_agent == UA


def test_conflicting_variables_are_pointed_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GS_COOKIES", "NID=from-env")
    monkeypatch.setenv("GS_USER_AGENT", "Old/1")

    _, text = _run(CURL)

    assert "GS_COOKIES is set and takes precedence" in text
    assert "GS_USER_AGENT is set and overrides" in text
    assert Config.from_env().cookies == "NID=from-env"


def test_a_bare_cookie_header_needs_a_user_agent_from_somewhere() -> None:
    code, text = _run("NID=abc")
    assert code == doctor.ERROR
    assert "no User-Agent" in text
    assert not default_cookie_file().exists()

    code, _ = _run("NID=abc", user_agent=UA)
    assert code == doctor.OK
    assert split_identity(default_cookie_file().read_text())[1] == UA


def test_account_cookies_are_never_saved() -> None:
    code, text = _run(f"cookie: NID=1; SAPISID={SECRET}\nuser-agent: {UA}")

    assert code == doctor.ERROR
    assert not default_cookie_file().exists()
    assert "SAPISID" in text and SECRET not in text


@pytest.mark.parametrize("copied", ["", "just some text", "accept: text/html"])
def test_text_without_cookies_saves_nothing_and_explains(copied: str) -> None:
    code, text = _run(copied)

    assert code == doctor.ERROR
    assert "Copy as cURL" in text
    assert not default_cookie_file().exists()


def test_missing_clipboard_tool_points_to_stdin() -> None:
    code, text = _run(None)

    assert code == doctor.ERROR
    assert "--stdin" in text


def test_the_exit_code_reports_whether_scholar_accepts_the_saved_identity() -> None:
    code, _ = _run(CURL, verify=lambda: doctor.BLOCKED)

    assert code == doctor.BLOCKED
    assert default_cookie_file().exists()


def test_a_rewritten_file_stays_private(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "cookies"
    write_identity_file(path, {"NID": "1"}, UA)
    path.chmod(0o644)

    write_identity_file(path, {"NID": "2"}, UA)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "NID=2" in path.read_text()


def test_cli_exposes_set_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    from google_scholar_search_mcp import cli

    seen = {}
    monkeypatch.setattr(
        "google_scholar_search_mcp.cli.cookies.run",
        lambda **kw: seen.update(kw) or 0,
    )

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["set-cookies", "--stdin", "--user-agent", "UA/1"])

    assert exit_info.value.code == 0
    assert seen == {"from_stdin": True, "user_agent": "UA/1"}


def test_doctor_describes_the_default_file_without_contents() -> None:
    write_identity_file(default_cookie_file(), {"NID": SECRET}, UA)

    text, usable = doctor.describe_cookie_source()

    assert usable
    assert "1 cookies parsed, with User-Agent" in text
    assert SECRET not in text
