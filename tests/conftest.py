from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _voice_test_local_roots(tmp_path, monkeypatch):
    """Make each test's temporary files an explicit trusted local root."""
    monkeypatch.setenv("SPARK_VOICE_ENV_ROOT", str(tmp_path))
    monkeypatch.setenv("SPARK_VOICE_ASSET_ROOT", str(tmp_path))
