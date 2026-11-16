"""Browser cookies / User-Agent for Scholar requests, and the diagnostics around them."""

from __future__ import annotations

import dataclasses
import io
import logging
from pathlib import Path

import httpx
import pytest

from google_scholar_search_mcp.block_detector import BlockDetector
from google_scholar_search_mcp.cli import doctor
from google_scholar_search_mcp.config import Config
from google_scholar_search_mcp.scholar import ScholarClient
from google_scholar_search_mcp.session_identity import (
    apply_identity,
    current_cookie_names,
    login_cookie_names,
    parse_cookies,
    set_identity,
)

from .test_scholar import _make_config

SECRET = "s3cr3t-cookie-value-DO-NOT-LEAK"


@pytest.fixture(autouse=True)
def _reset_identity():
    yield
    set_identity(None, None)


# --- parsing -----------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "GSP=A=1; NID=abc",
        "Cookie: GSP=A=1; NID=abc",
        "cookie:  GSP=A=1;\n  NID=abc ;",
        "GSP=A=1;NID=abc",
    ],
)
def test_parse_accepts_a_copied_header_in_its_usual_shapes(text: str) -> None:
    assert parse_cookies(text) == {"GSP": "A=1", "NID": "abc"}


def test_parse_ignores_junk_and_blank_input() -> None:
    assert parse_cookies(None) == {}
    assert parse_cookies("   ") == {}
    assert parse_cookies("novalue; =x; ok=1") == {"ok": "1"}


def test_login_cookies_are_recognised_by_name_only() -> None:
    cookies = parse_cookies(f"NID=1; SAPISID={SECRET}; __Secure-1PSID=x")

    assert login_cookie_names(cookies) == ["SAPISID", "__Secure-1PSID"]
    assert login_cookie_names(parse_cookies("NID=1; GSP=2")) == []


# --- applying ----------------------------------------------------------------


def _request(url: str, **headers: str) -> httpx.Request:
    return httpx.Request("GET", url, headers=headers)


def test_cookies_and_user_agent_are_added_to_scholar_requests() -> None:
    set_identity("GSP=1; NID=2", "My Browser/1.0")
    request = _request(
        "https://scholar.google.com/scholar?q=x", **{"User-Agent": "scholarly"}
    )

    apply_identity(request)

    assert parse_cookies(request.headers["cookie"]) == {"GSP": "1", "NID": "2"}
    assert request.headers["user-agent"] == "My Browser/1.0"


def test_other_hosts_never_receive_the_identity() -> None:
    set_identity(f"NID={SECRET}", "My Browser/1.0")
    request = _request("https://example.com/works")

    apply_identity(request)

    assert "cookie" not in request.headers
    assert request.headers.get("user-agent") != "My Browser/1.0"


def test_cookies_the_client_already_holds_win_over_configured_ones() -> None:
    set_identity("NID=old; GSP=1", None)
    request = _request("https://scholar.google.com/", cookie="NID=fresh; other=3")

    apply_identity(request)

    assert parse_cookies(request.headers["cookie"]) == {
        "NID": "fresh",
        "GSP": "1",
        "other": "3",
    }


def test_nothing_changes_without_configuration() -> None:
    request = _request("https://scholar.google.com/", **{"User-Agent": "scholarly"})

    apply_identity(request)

    assert "cookie" not in request.headers
    assert request.headers["user-agent"] == "scholarly"


def test_identity_is_applied_to_real_client_traffic_via_the_hook() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="ok")

    BlockDetector()  # installs the httpx hook
    set_identity("NID=abc", "My Browser/1.0")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        client.get("https://scholar.google.com/scholar?q=x")
        client.get("https://example.com/")

    assert seen[0].headers["cookie"] == "NID=abc"
    assert seen[0].headers["user-agent"] == "My Browser/1.0"
    assert "cookie" not in seen[1].headers


def test_the_scholar_client_configures_the_identity_from_its_config() -> None:
    config = dataclasses.replace(_make_config(), cookies="NID=abc", user_agent="UA/1")

    ScholarClient(config)

    assert current_cookie_names() == ["NID"]


# --- secrets stay secret ------------------------------------------------------


def test_config_repr_hides_every_secret() -> None:
    config = dataclasses.replace(
        _make_config(),
        cookies=f"NID={SECRET}",
        scraperapi_key=SECRET,
    )

    assert SECRET not in repr(config)
    assert SECRET not in str(config)


def test_login_cookies_trigger_a_warning_that_names_but_never_shows_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = dataclasses.replace(_make_config(), cookies=f"NID=1; SAPISID={SECRET}")

    with caplog.at_level(logging.WARNING):
        ScholarClient(config)

    assert "SAPISID" in caplog.text
    assert SECRET not in caplog.text


# --- config ------------------------------------------------------------------


def test_config_reads_cookies_from_env_and_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GS_COOKIES", "NID=abc")
    monkeypatch.setenv("GS_USER_AGENT", "UA/1")
    monkeypatch.delenv("GS_COOKIES_FILE", raising=False)

    config = Config.from_env()

    assert config.cookies == "NID=abc"
    assert config.user_agent == "UA/1"


def test_cookie_file_wins_over_the_env_var(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("NID=from-file\n")
    monkeypatch.setenv("GS_COOKIES", "NID=from-env")
    monkeypatch.setenv("GS_COOKIES_FILE", str(cookie_file))

    assert Config.from_env().cookies == "NID=from-file"


def test_unreadable_cookie_file_is_a_clear_error_without_contents(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GS_COOKIES_FILE", str(tmp_path / "missing.txt"))

    with pytest.raises(ValueError, match="GS_COOKIES_FILE"):
        Config.from_env()


# --- doctor ------------------------------------------------------------------


def _doctor(handler, config: Config | None = None) -> tuple[int, str]:
    out = io.StringIO()
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    with client:
        code = doctor.run(config or _make_config(), client=client, out=out)
    return code, out.getvalue()


BOTH_PAGES = '<div class="gs_ri">paper</div>'


def _sgsync(request: httpx.Request) -> httpx.Response:
    if request.url.host == "scholar.google.com":
        return httpx.Response(
            302, headers={"location": "https://www.google.com/sgsync?url=x"}
        )
    return httpx.Response(200, text="Verifying...")


def test_doctor_reports_ok_for_a_results_page() -> None:
    code, text = _doctor(lambda r: httpx.Response(200, text=BOTH_PAGES))

    assert code == doctor.OK
    assert "OK" in text


def test_doctor_reports_blocked_with_the_reason_and_advice_without_cookies() -> None:
    code, text = _doctor(_sgsync)

    assert code == doctor.BLOCKED
    assert "sgsync" in text
    assert "GS_COOKIES_FILE" in text


def test_doctor_blames_the_cookies_when_they_were_sent_but_blocked() -> None:
    config = dataclasses.replace(_make_config(), cookies=f"NID={SECRET}")

    code, text = _doctor(_sgsync, config)

    assert code == doctor.BLOCKED
    assert "cookies did not get past" in text
    assert "NID" in text  # the name, to show it was used
    assert SECRET not in text


def test_doctor_warns_about_login_cookies_without_printing_values() -> None:
    config = dataclasses.replace(_make_config(), cookies=f"SAPISID={SECRET}")

    _, text = _doctor(lambda r: httpx.Response(200, text=BOTH_PAGES), config)

    assert "WARNING" in text and "SAPISID" in text
    assert SECRET not in text


def test_doctor_distinguishes_network_errors_and_odd_pages() -> None:
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    assert _doctor(unreachable)[0] == doctor.ERROR
    assert (
        _doctor(lambda r: httpx.Response(200, text="<html>hi</html>"))[0]
        == doctor.ERROR
    )
    assert _doctor(lambda r: httpx.Response(500))[0] == doctor.ERROR


def test_cli_exposes_the_doctor_command(monkeypatch: pytest.MonkeyPatch) -> None:
    from google_scholar_search_mcp import cli

    monkeypatch.setattr("google_scholar_search_mcp.cli.doctor.run", lambda: 7)

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["doctor"])

    assert exit_info.value.code == 7


def test_parse_accepts_the_tab_separated_table_from_the_application_tab() -> None:
    table = "Name\tValue\tDomain\nNID\tabc\t.google.com\nGSP\tA=1\tscholar.google.com\n"

    assert parse_cookies(table) == {"NID": "abc", "GSP": "A=1"}


def test_doctor_explains_when_no_cookie_source_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GS_COOKIES_FILE", raising=False)
    monkeypatch.delenv("GS_COOKIES", raising=False)

    _, text = _doctor(_sgsync)

    assert "neither GS_COOKIES_FILE nor GS_COOKIES is set" in text
    assert "echo $GS_COOKIES_FILE" in text


def test_doctor_reports_an_empty_or_unparsable_cookie_file_without_contents(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    junk = tmp_path / "cookies.txt"
    junk.write_text(f"{SECRET} but no pairs here")
    monkeypatch.setenv("GS_COOKIES_FILE", str(junk))

    _, text = _doctor(_sgsync)

    assert "0 cookies parsed" in text
    assert SECRET not in text


def test_doctor_reports_a_missing_cookie_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GS_COOKIES_FILE", str(tmp_path / "nope.txt"))

    _, text = _doctor(_sgsync)

    assert "file not found" in text


def test_doctor_counts_cookies_from_a_good_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    good = tmp_path / "cookies.txt"
    good.write_text("NID=abc; GSP=A=1")
    monkeypatch.setenv("GS_COOKIES_FILE", str(good))
    config = dataclasses.replace(_make_config(), cookies="NID=abc; GSP=A=1")

    _, text = _doctor(_sgsync, config)

    assert "2 cookies parsed" in text
    assert "No usable cookies" not in text
