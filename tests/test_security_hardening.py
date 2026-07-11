"""Tests for builder_env_file_path root restriction in spark_hook._read_env_map.

Security property: _read_env_map must only open files inside ~/.spark or
~/.spark/envs; any other path must raise ValueError before any I/O.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from voice_comms_chip.spark_hook import _read_env_map

_SPARK_ROOT = Path.home() / ".spark"
_SPARK_ENVS = Path.home() / ".spark" / "envs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_env(path: Path, contents: str = "KEY=value\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)
    return path


# ---------------------------------------------------------------------------
# Allowed paths
# ---------------------------------------------------------------------------

def test_file_directly_under_spark_root_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".spark" / "my.env"
    _write_env(env_file, "FOO=bar\n")
    result = _read_env_map(env_file_path=str(env_file))
    assert result == {"FOO": "bar"}


def test_file_under_spark_envs_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / ".spark" / "envs" / "prod.env"
    _write_env(env_file, "SECRET=hello\n")
    result = _read_env_map(env_file_path=str(env_file))
    assert result == {"SECRET": "hello"}


# ---------------------------------------------------------------------------
# Rejected paths
# ---------------------------------------------------------------------------

def test_sibling_of_spark_root_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    env_file = tmp_path / "sibling.env"
    _write_env(env_file)
    with pytest.raises(ValueError, match="outside allowed Spark config roots"):
        _read_env_map(env_file_path=str(env_file))


def test_ssh_key_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ssh_key = tmp_path / ".ssh" / "id_rsa"
    _write_env(ssh_key, "-----BEGIN OPENSSH PRIVATE KEY-----\n")
    with pytest.raises(ValueError, match="outside allowed Spark config roots"):
        _read_env_map(env_file_path=str(ssh_key))


def test_tmp_file_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    tmp_env = Path("/tmp/evil.env")
    if not tmp_env.exists():
        tmp_env.write_text("EVIL=1\n")
    with pytest.raises(ValueError, match="outside allowed Spark config roots"):
        _read_env_map(env_file_path=str(tmp_env))


def test_etc_passwd_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(ValueError, match="outside allowed Spark config roots"):
        _read_env_map(env_file_path="/etc/passwd")


def test_absolute_path_outside_spark_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    outside = tmp_path / "notdotspark" / "env"
    _write_env(outside)
    with pytest.raises(ValueError, match="outside allowed Spark config roots"):
        _read_env_map(env_file_path=str(outside))


# ---------------------------------------------------------------------------
# Symlink inside allowed root resolves to inside root → allowed
# ---------------------------------------------------------------------------

def test_symlink_inside_allowed_root_pointing_inward_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    envs_dir = tmp_path / ".spark" / "envs"
    envs_dir.mkdir(parents=True)
    real_file = envs_dir / "real.env"
    real_file.write_text("LINK=yes\n")
    link = tmp_path / ".spark" / "link.env"
    link.symlink_to(real_file)
    result = _read_env_map(env_file_path=str(link))
    assert result == {"LINK": "yes"}
