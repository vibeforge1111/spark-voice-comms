"""Tests: _read_env_map path containment — path traversal prevention."""
from __future__ import annotations

import pytest

import voice_comms_chip.spark_hook as _hook
from voice_comms_chip.spark_hook import _read_env_map


def test_etc_passwd_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(_hook, "_VOICE_ENV_FILE_ALLOWED_BASE", tmp_path)
    with pytest.raises(ValueError, match="outside the permitted runtime root"):
        _read_env_map(env_file_path="/etc/passwd")


def test_proc_self_environ_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(_hook, "_VOICE_ENV_FILE_ALLOWED_BASE", tmp_path)
    with pytest.raises(ValueError, match="outside the permitted runtime root"):
        _read_env_map(env_file_path="/proc/self/environ")


def test_relative_traversal_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(_hook, "_VOICE_ENV_FILE_ALLOWED_BASE", tmp_path)
    traversal = str(tmp_path / "subdir" / ".." / ".." / ".env")
    with pytest.raises(ValueError, match="outside the permitted runtime root"):
        _read_env_map(env_file_path=traversal)


def test_valid_path_inside_runtime_root_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(_hook, "_VOICE_ENV_FILE_ALLOWED_BASE", tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=testkey\n", encoding="utf-8")
    result = _read_env_map(env_file_path=str(env_file))
    assert result["OPENAI_API_KEY"] == "testkey"


def test_read_env_map_never_opens_files_outside_approved_base(tmp_path, monkeypatch):
    monkeypatch.setattr(_hook, "_VOICE_ENV_FILE_ALLOWED_BASE", tmp_path)
    with pytest.raises(ValueError, match="outside the permitted runtime root"):
        _read_env_map(env_file_path="/etc/shadow")
