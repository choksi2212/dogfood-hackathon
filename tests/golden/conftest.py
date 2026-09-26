"""Pytest configuration for the golden suite.

The golden tests are pure-Python: they call `apps.normalization.fit.
normalize()` and `apps.pairwise.fit.bradley_terry()` with synthetic
inputs, then compare the output against a stored canonical JSON
fixture. None of them need a database, a running server, or the
HTTP fixtures in the root tests/conftest.py.

The root tests/conftest.py has an autouse `_enable_db(db)` fixture
that triggers pytest-django's DB setup for every test in the
session. We override it here with a no-op so the golden suite runs
without a Postgres roundtrip.

This file is local to the golden suite — it does not touch the root
tests/conftest.py or pytest.ini.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _enable_db():
    """Override the root conftest's `_enable_db` with a no-op.

    The root tests/conftest.py has `def _enable_db(db): pass`, which
    transitively depends on pytest-django's `db` fixture and forces
    a CREATE DATABASE roundtrip. We redefine it here without the
    `db` dependency so the golden suite can run without Postgres.
    """
    # No-op for the golden suite: tests don't touch the DB.
    return None
