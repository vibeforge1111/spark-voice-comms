"""Regression tests for the VOICE_TRANSCRIBE_PROVIDER actionable-error message.

_resolve_dedicated_transcription_provider in spark_hook.py rejects any
VOICE_TRANSCRIBE_PROVIDER value that isn't an alias the dispatcher knows.
The error previously named only the bad value; these tests pin the new
message shape (failed value quoted, supported values named inline) and
keep the alias dispatch paths (openai / auto / local / builder) intact.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import sys

THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from voice_comms_chip.spark_hook import _resolve_dedicated_transcription_provider


def _payload(tmp_path: Path) -> dict:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-fake\n", encoding="utf-8")
    return {"builder_env_file_path": str(env_file)}


def test_unsupported_provider_id_lists_supported_values(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VOICE_TRANSCRIBE_PROVIDER", "google-cloud")
    payload = _payload(tmp_path)
    with pytest.raises(ValueError) as excinfo:
        _resolve_dedicated_transcription_provider(payload)
    message = str(excinfo.value)
    assert "'google-cloud'" in message
    for known_value in (
        "openai",
        "auto",
        "default",
        "local",
        "offline",
        "faster-whisper",
        "local-faster-whisper",
        "builder",
        "provider",
        "configured-provider",
    ):
        assert known_value in message


def test_openai_explicit_pure_hit_path_unchanged(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VOICE_TRANSCRIBE_PROVIDER", "openai")
    payload = _payload(tmp_path)
    result = _resolve_dedicated_transcription_provider(payload)
    assert result is not None
    assert result["provider_id"] == "openai"


def test_auto_alias_returns_none(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VOICE_TRANSCRIBE_PROVIDER", "auto")
    # auto -> provider_id reset; with no base_url / secret_env_ref / OPENAI_API_KEY
    # in env_map, the function returns None to defer to defaults.
    env_file = tmp_path / ".env"
    env_file.write_text("\n", encoding="utf-8")
    payload = {"builder_env_file_path": str(env_file)}
    result = _resolve_dedicated_transcription_provider(payload)
    assert result is None or result["provider_id"] == "openai"


def test_local_alias_returns_none(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VOICE_TRANSCRIBE_PROVIDER", "local")
    payload = _payload(tmp_path)
    result = _resolve_dedicated_transcription_provider(payload)
    assert result is None


def test_builder_alias_returns_none(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VOICE_TRANSCRIBE_PROVIDER", "builder")
    payload = _payload(tmp_path)
    result = _resolve_dedicated_transcription_provider(payload)
    assert result is None
