"""Shared fixtures.

Throttling stays switched on in tests, because a rate limit that is disabled in
the only place it is exercised is a rate limit nobody has ever seen work. The
cost is that one test's requests would otherwise count against the next one's
budget, which this clears.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _clear_throttle_history() -> Iterator[None]:
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
