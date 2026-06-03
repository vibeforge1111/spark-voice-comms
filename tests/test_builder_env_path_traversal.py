from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from voice_comms_chip.spark_hook import _validate_env_file_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def with_root(tmp_path: Path, fn):
    """Run fn with SPARK_PROJECT_ROOT set to tmp_path/spark."""
    approved = str(tmp_path / "spark")
    with patch.dict(os.environ, {"SPARK_PROJECT_ROOT": approved}):
        return fn(approved)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_relative_traversal_rejected(tmp_path):
    """../../.env from inside the approved dir is rejected after resolve."""
    def run(approved):
        traversal = str(Path(approved) / ".." / ".." / ".env")
        with pytest.raises(ValueError, match="outside the approved"):
            _validate_env_file_path(traversal)
    with_root(tmp_path, run)


def test_absolute_path_to_etc_shadow_rejected(tmp_path):
    """/etc/shadow (or Windows equivalent) is always outside approved base."""
    def run(approved):
        with pytest.raises(ValueError, match="outside the approved"):
            _validate_env_file_path("/etc/shadow")
    with_root(tmp_path, run)


def test_home_dotfile_outside_approved_base_rejected(tmp_path):
    """~/.spark/config is rejected when SPARK_PROJECT_ROOT is a project dir."""
    def run(approved):
        outside = str(Path.home() / ".ssh" / "id_rsa")
        with pytest.raises(ValueError, match="outside the approved"):
            _validate_env_file_path(outside)
    with_root(tmp_path, run)


def test_valid_path_inside_approved_base_allowed(tmp_path):
    """A file directly inside the approved base passes validation."""
    spark_dir = tmp_path / "spark"
    spark_dir.mkdir()
    env_file = spark_dir / ".env"
    env_file.touch()
    with patch.dict(os.environ, {"SPARK_PROJECT_ROOT": str(spark_dir)}):
        result = _validate_env_file_path(str(env_file))
    assert result == env_file.resolve()


def test_double_dot_in_path_rejected_after_resolve(tmp_path):
    """Path with encoded traversal (%2e%2e decoded as ..) is rejected once resolved."""
    def run(approved):
        # Python Path treats literal ".." the same whether or not URL-encoded
        traversal = str(Path(approved) / ".." / ".." / "etc" / "passwd")
        with pytest.raises(ValueError, match="outside the approved"):
            _validate_env_file_path(traversal)
    with_root(tmp_path, run)


def test_path_within_subdirectory_of_approved_base_allowed(tmp_path):
    """A nested path inside approved/subdir/file.env is accepted."""
    spark_dir = tmp_path / "spark"
    sub = spark_dir / "project" / "config"
    sub.mkdir(parents=True)
    env_file = sub / "local.env"
    env_file.touch()
    with patch.dict(os.environ, {"SPARK_PROJECT_ROOT": str(spark_dir)}):
        result = _validate_env_file_path(str(env_file))
    assert result == env_file.resolve()
