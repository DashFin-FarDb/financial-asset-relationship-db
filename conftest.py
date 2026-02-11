"""Pytest configuration helpers for the repository.

This module removes optional coverage-related command line arguments when the
``pytest-cov`` plugin is not installed. Some environments (for example, local
developer shells or CI configurations) may inject coverage options via
``PYTEST_ADDOPTS``. Without ``pytest-cov`` those options cause pytest to fail
before executing any tests. By trimming the coverage options when the plugin is
missing we allow the default test command to succeed while still preserving
coverage reporting where the dependency is available.
"""

from __future__ import annotations

import importlib.util
from typing import List


def pytest_load_initial_conftests(
    args: List[str],
) -> None:  # pragma: no cover - exercised via pytest
    """
    Remove pytest-cov command-line options from args when the pytest-cov plugin is not installed.

    If the plugin is unavailable, strips standalone `--cov` / `--cov-report` and inline
    forms starting with `--cov=` or `--cov-report=`. Modifies the input list in place.

    Parameters:
        args (List[str]): Mutable list of command-line arguments to filter.
    """

    if _cov_plugin_available():
        return

    filtered_args: List[str] = []
    skip_next = False

    for arg in args:
        if skip_next:
            skip_next = False
            continue

        if arg in {"--cov", "--cov-report"}:
            skip_next = True
            continue

        if arg.startswith(("--cov=", "--cov-report=")):
            continue

        filtered_args.append(arg)

    args[:] = filtered_args


def _cov_plugin_available() -> bool:  # pragma: no cover
    """
    Detects whether the pytest-cov plugin is available.

    Returns:
        True if the pytest-cov plugin is available, False otherwise.
    """
    return importlib.util.find_spec("pytest_cov") is not None
