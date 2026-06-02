"""Regression tests for the voice.speak provider_id actionable-error message.

_resolve_tts_request rejects any provider_id that isn't one of the registered
TTS backends (kokoro family, local family, openai-realtime family, elevenlabs).
The error previously named only the bad value; this test pins the new message
shape (failed value quoted, supported set named inline) and keeps the pure-hit
dispatch path intact.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from voice_comms_chip.spark_hook import _resolve_tts_request


def _payload(tmp_path: Path, provider_id: str) -> dict:
    env_file = tmp_path / ".env"
    env_file.write_text("ELEVENLABS_API_KEY=fake\n", encoding="utf-8")
    return {
        "builder_env_file_path": str(env_file),
        "tts": {"provider_id": provider_id},
        "text": "hello",
    }


def test_unsupported_provider_id_lists_supported_providers(tmp_path) -> None:
    payload = _payload(tmp_path, "google-cloud-tts")
    with pytest.raises(ValueError) as excinfo:
        _resolve_tts_request(payload, profile={})
    message = str(excinfo.value)
    assert "'google-cloud-tts'" in message
    for supported in (
        "elevenlabs",
        "kokoro",
        "kokoro-onnx",
        "local-kokoro",
        "pyttsx3",
        "local",
        "openai-realtime",
    ):
        assert supported in message


def test_elevenlabs_pure_hit_path_unchanged(tmp_path) -> None:
    payload = _payload(tmp_path, "elevenlabs")
    result = _resolve_tts_request(payload, profile={})
    assert result["provider_id"] == "elevenlabs"
