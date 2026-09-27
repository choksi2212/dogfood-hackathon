"""Local pytest configuration for the security suite.

Registers the ``security`` marker so ``@pytest.mark.security`` works under
``--strict-markers`` (the project's pytest.ini enables it). Also adds a
``--no-rate-limit`` CLI flag the brute-force / write-rate tests respect
so the suite can run inside a tighter local loop without tripping the
in-process limiter on follow-up runs.

This file is the only thing added alongside tests/security/test_attacks.py.
Per the security agent's scope it lives inside tests/security/ and never
edits any existing file in the project.
"""

from __future__ import annotations


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "security: attack-surface probes — SQLi, XSS, path traversal, "
        "brute force, CSRF, rate limit, cookie hygiene, token entropy, "
        "secret leakage.",
    )


def pytest_addoption(parser):
    parser.addoption(
        "--no-rate-limit",
        action="store_true",
        default=False,
        help="Skip brute-force / write-rate-limit probes (default: hit the limiter).",
    )
