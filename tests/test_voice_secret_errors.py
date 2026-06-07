from __future__ import annotations

import pytest

from voice_comms_chip.profile import load_voice_profile
from voice_comms_chip.spark_hook import (
    _resolve_dedicated_transcription_provider,
    _resolve_openai_realtime_tts_request,
    _resolve_provider,
    _resolve_tts_request,
)

SECRET_ENV_MARKERS = ("OPENAI_API_KEY", "ELEVENLABS_API_KEY", "CUSTOM_VOICE_SECRET")


def _assert_no_secret_env_leak(message: str) -> None:
    lowered = message.lower()
    for marker in SECRET_ENV_MARKERS:
        assert marker.lower() not in lowered
    assert "env ref" not in lowered
    assert "secret_env_ref" not in lowered


def test_resolve_provider_missing_secret_does_not_leak_env_ref(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("# no provider keys configured\n", encoding="utf-8")
    payload = {
        "builder_env_file_path": str(env_file),
        "provider": {
            "provider_id": "openai",
            "provider_kind": "openai",
            "auth_method": "api_key_env",
            "base_url": "https://api.openai.com/v1",
            "secret_env_ref": "CUSTOM_VOICE_SECRET",
        },
    }

    with pytest.raises(ValueError) as exc_info:
        _resolve_provider(payload)

    message = str(exc_info.value)
    _assert_no_secret_env_leak(message)
    assert "configured API secret" in message
    assert "builder env file" in message


def test_dedicated_transcription_provider_missing_secret_does_not_leak_default_ref(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("VOICE_TRANSCRIBE_PROVIDER=openai\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError) as exc_info:
        _resolve_dedicated_transcription_provider({"builder_env_file_path": str(env_file)})

    message = str(exc_info.value)
    _assert_no_secret_env_leak(message)
    assert "Voice transcription" in message


def test_resolve_tts_request_elevenlabs_missing_secret_does_not_leak_env_ref(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("VOICE_TTS_PROVIDER=elevenlabs\n", encoding="utf-8")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    profile = load_voice_profile()

    with pytest.raises(ValueError) as exc_info:
        _resolve_tts_request(
            {
                "builder_env_file_path": str(env_file),
                "text": "hello",
                "tts": {"provider_id": "elevenlabs", "secret_env_ref": "CUSTOM_VOICE_SECRET"},
            },
            profile=profile,
        )

    message = str(exc_info.value)
    _assert_no_secret_env_leak(message)
    assert "voice.speak" in message


def test_resolve_openai_realtime_tts_missing_secret_does_not_leak_env_ref(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("VOICE_TTS_PROVIDER=openai-realtime\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError) as exc_info:
        _resolve_openai_realtime_tts_request(
            tts={"secret_env_ref": "CUSTOM_VOICE_SECRET"},
            env_map={"VOICE_TTS_PROVIDER": "openai-realtime"},
            text="hello",
            surface="telegram",
        )

    message = str(exc_info.value)
    _assert_no_secret_env_leak(message)
    assert "OpenAI Realtime" in message


def test_resolve_tts_request_rejects_text_exceeding_max_length():
    """Text over MAX_TTS_TEXT_LENGTH must be rejected before reaching any TTS provider."""
    from voice_comms_chip.spark_hook import MAX_TTS_TEXT_LENGTH

    profile = load_voice_profile()
    oversized_text = "a" * (MAX_TTS_TEXT_LENGTH + 1)

    with pytest.raises(ValueError) as exc_info:
        _resolve_tts_request({"text": oversized_text}, profile=profile)

    message = str(exc_info.value)
    assert f"{MAX_TTS_TEXT_LENGTH:,}" in message
    assert "maximum length" in message.lower()


def test_resolve_tts_request_accepts_text_at_max_length(monkeypatch):
    """Text exactly at MAX_TTS_TEXT_LENGTH should pass the length gate."""
    from voice_comms_chip.spark_hook import MAX_TTS_TEXT_LENGTH

    profile = load_voice_profile()
    max_text = "a" * MAX_TTS_TEXT_LENGTH

    # We don't need the TTS request to fully resolve; just verify it doesn't
    # raise a length ValueError. The missing-secret error means it passed the
    # length gate and reached the provider resolution logic.
    with pytest.raises(ValueError) as exc_info:
        _resolve_tts_request(
            {
                "text": max_text,
                "tts": {"provider_id": "elevenlabs"},
                "builder_env_file_path": "/dev/null",
            },
            profile=profile,
        )

    message = str(exc_info.value)
    assert "maximum length" not in message.lower()
