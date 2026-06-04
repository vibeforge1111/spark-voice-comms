"""Test that _resolve_local_faster_whisper_model handles unreadable env files."""

from __future__ import annotations

from unittest.mock import patch

from voice_comms_chip.spark_hook import _resolve_local_faster_whisper_model


def test_resolve_model_returns_tiny_on_unreadable_env() -> None:
    """When env file is unreadable, function returns default 'tiny' instead of crashing."""
    payload = {"builder_env_file_path": "/nonexistent/env/file"}
    with patch("voice_comms_chip.spark_hook._runtime_env_map", side_effect=ValueError("env file corrupted")):
        result = _resolve_local_faster_whisper_model(payload)
    assert result == "tiny"


def test_resolve_model_returns_tiny_on_os_error() -> None:
    """When env file raises OSError, function returns default 'tiny' instead of crashing."""
    payload = {"builder_env_file_path": "/nonexistent/env/file"}
    with patch("voice_comms_chip.spark_hook._runtime_env_map", side_effect=OSError("permission denied")):
        result = _resolve_local_faster_whisper_model(payload)
    assert result == "tiny"


def test_resolve_model_returns_configured_value_when_env_readable() -> None:
    """When env file is readable and has model configured, returns configured value."""
    payload = {"builder_env_file_path": "/some/env/file"}
    with patch("voice_comms_chip.spark_hook._runtime_env_map", return_value={"VOICE_TRANSCRIBE_LOCAL_MODEL": "small"}):
        result = _resolve_local_faster_whisper_model(payload)
    assert result == "small"
