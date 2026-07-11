from __future__ import annotations

import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _set_spark_project_root(tmp_path, monkeypatch):
    """Point SPARK_PROJECT_ROOT at each test's tmp_path.

    _validate_env_file_path checks that builder_env_file_path lives inside
    SPARK_PROJECT_ROOT (or ~/.spark when unset). Existing tests create env
    files under tmp_path without setting this variable, so they would all
    fail the containment check. Pointing the root at tmp_path restores the
    pre-validation behaviour for the whole test suite.
    """
    monkeypatch.setenv("SPARK_PROJECT_ROOT", str(tmp_path))
