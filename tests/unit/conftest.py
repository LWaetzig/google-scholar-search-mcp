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
