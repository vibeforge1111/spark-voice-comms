
from __future__ import annotations

import os
from unittest.mock import patch

from voice_comms_chip.spark_hook import (
    _safe_builder_env_map,
    _transcription_provider_mode,
    _build_voice_status,
    _is_allowed_env_file_path,
)


# ── _safe_builder_env_map ──────────────────────────────────────────

def test_safe_builder_env_map_oserror_falls_back():
    with patch("voice_comms_chip.spark_hook._runtime_env_map", side_effect=OSError("disk full")), \
         patch("voice_comms_chip.spark_hook._is_allowed_env_file_path", return_value=True), \
         patch("voice_comms_chip.spark_hook._process_voice_env_map", return_value={"FALLBACK": "yes"}):
        result = _safe_builder_env_map({"builder_env_file_path": "/bad/path/.env"})
    assert result == {"FALLBACK": "yes"}


def test_safe_builder_env_map_valueerror_falls_back():
    with patch("voice_comms_chip.spark_hook._runtime_env_map", side_effect=ValueError("bad encoding")), \
         patch("voice_comms_chip.spark_hook._is_allowed_env_file_path", return_value=True), \
         patch("voice_comms_chip.spark_hook._process_voice_env_map", return_value={"PROCESS": "env"}):
        result = _safe_builder_env_map({"builder_env_file_path": "/bad/.env"})
    assert result == {"PROCESS": "env"}


def test_safe_builder_env_map_keyboardinterrupt_propagates():
    with patch("voice_comms_chip.spark_hook._runtime_env_map", side_effect=KeyboardInterrupt), \
         patch("voice_comms_chip.spark_hook._is_allowed_env_file_path", return_value=True):
        try:
            _safe_builder_env_map({"builder_env_file_path": "/some/.env"})
            assert False, "KeyboardInterrupt should have propagated"
        except KeyboardInterrupt:
            pass


# ── _transcription_provider_mode ───────────────────────────────────

def test_transcription_provider_mode_oserror_falls_back():
    with patch("voice_comms_chip.spark_hook._runtime_env_map", side_effect=OSError("disk full")), \
         patch.dict(os.environ, {}, clear=True):
        result = _transcription_provider_mode({"builder_env_file_path": "/bad/.env"})
    assert result == "auto"


def test_transcription_provider_mode_valueerror_falls_back():
    with patch("voice_comms_chip.spark_hook._runtime_env_map", side_effect=ValueError("bad line")), \
         patch.dict(os.environ, {}, clear=True):
        result = _transcription_provider_mode({"builder_env_file_path": "/bad/.env"})
    assert result == "auto"


def test_transcription_provider_mode_keyboardinterrupt_propagates():
    with patch("voice_comms_chip.spark_hook._runtime_env_map", side_effect=KeyboardInterrupt):
        try:
            _transcription_provider_mode({"builder_env_file_path": "/some/.env"})
            assert False, "KeyboardInterrupt should have propagated"
        except KeyboardInterrupt:
            pass


# ── _build_voice_status env-file merge guard ───────────────────────

def test_build_voice_status_env_merge_oserror_guarded(tmp_path):
    """OSError from _read_env_map in the guarded block is caught silently."""
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=fake-key\n", encoding="utf-8")

    with patch("voice_comms_chip.spark_hook._read_env_map", side_effect=OSError("disk error")), \
         patch("voice_comms_chip.spark_hook._resolve_provider", return_value={
             "provider_id": "openai", "provider_kind": "openai",
         }), \
         patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True), \
         patch("voice_comms_chip.spark_hook._resolve_local_faster_whisper_model", return_value="tiny"), \
         patch("voice_comms_chip.spark_hook._transcription_provider_mode", return_value="local"), \
         patch("voice_comms_chip.spark_hook._local_kokoro_ready", return_value=False), \
         patch("voice_comms_chip.spark_hook._local_pyttsx3_available", return_value=False), \
         patch("voice_comms_chip.spark_hook._active_tts_status", return_value={
             "ready": False, "provider": "none", "status": "unavailable"}), \
         patch("voice_comms_chip.spark_hook._local_tts_status", return_value={
             "ready": False, "provider": "none", "status": "unavailable"}):
        result = _build_voice_status({
            "builder_env_file_path": str(env_file),
            "provider": {"provider_id": "openai", "provider_kind": "openai"},
        })

    assert result.get("ready") is True  # local is ready
    assert result.get("local_ready") is True


def test_build_voice_status_env_merge_valueerror_guarded(tmp_path):
    """ValueError from _read_env_map in the guarded block is caught silently."""
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=fake-key\n", encoding="utf-8")

    with patch("voice_comms_chip.spark_hook._read_env_map", side_effect=ValueError("bad encoding")), \
         patch("voice_comms_chip.spark_hook._resolve_provider", return_value={
             "provider_id": "openai", "provider_kind": "openai",
         }), \
         patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True), \
         patch("voice_comms_chip.spark_hook._resolve_local_faster_whisper_model", return_value="tiny"), \
         patch("voice_comms_chip.spark_hook._transcription_provider_mode", return_value="local"), \
         patch("voice_comms_chip.spark_hook._local_kokoro_ready", return_value=False), \
         patch("voice_comms_chip.spark_hook._local_pyttsx3_available", return_value=False), \
         patch("voice_comms_chip.spark_hook._active_tts_status", return_value={
             "ready": False, "provider": "none", "status": "unavailable"}), \
         patch("voice_comms_chip.spark_hook._local_tts_status", return_value={
             "ready": False, "provider": "none", "status": "unavailable"}):
        result = _build_voice_status({
            "builder_env_file_path": str(env_file),
            "provider": {"provider_id": "openai", "provider_kind": "openai"},
        })

    assert result.get("ready") is True
    assert result.get("local_ready") is True


# ── _is_allowed_env_file_path ─────────────────────────────────────

def test_allowed_env_file_path_rejects_etc_passwd():
    assert _is_allowed_env_file_path("/etc/passwd") is False


def test_allowed_env_file_path_rejects_etc_shadow():
    assert _is_allowed_env_file_path("/etc/shadow") is False


def test_allowed_env_file_path_rejects_absolute_outside_roots():
    assert _is_allowed_env_file_path("/tmp/secrets.env") is False


def test_allowed_env_file_path_rejects_dot_dot_traversal():
    assert _is_allowed_env_file_path("~/.spark/../../etc/passwd") is False
