"""Shared pytest configuration.

Everything under ``tests/integration`` is marked ``integration`` automatically,
so ``-m "not integration"`` (CI) skips it and ``-m integration`` runs only it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_INTEGRATION_DIR = Path(__file__).parent / "integration"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Add the ``integration`` marker to every test below ``tests/integration``.

    Args:
        items (list[pytest.Item]): Collected test items.
    """
    for item in items:
        if _INTEGRATION_DIR in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.integration)
