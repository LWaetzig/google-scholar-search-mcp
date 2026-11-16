import pytest

from google_scholar_search_mcp.throttle import throttle


@pytest.fixture(autouse=True)
def _no_request_spacing():
    """Importing the server configures real 5-15 s spacing; unit tests want none."""
    throttle.configure(0.0, 0.0)
    throttle.reset()
    yield
    throttle.configure(0.0, 0.0)
    throttle.reset()


@pytest.fixture(autouse=True)
def _no_real_cookie_file(monkeypatch: pytest.MonkeyPatch, tmp_path_factory):
    """Never read or write the developer's real default cookie file."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path_factory.mktemp("xdg")))
