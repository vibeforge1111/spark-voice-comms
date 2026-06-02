from __future__ import annotations

import pytest

from voice_comms_chip.profile import load_voice_profile
from voice_comms_chip.spark_hook import (
    _resolve_dedicated_transcription_provider,
    _resolve_tts_request,
)


def test_unsupported_transcription_provider_lists_supported_values(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=fake-openai-key-for-tests",
                "VOICE_TRANSCRIBE_PROVIDER=google-cloud",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        _resolve_dedicated_transcription_provider({"builder_env_file_path": str(env_file)})

    message = str(exc_info.value)
    assert "'google-cloud'" in message
    for supported in (
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
        assert supported in message


def test_unsupported_speak_provider_lists_supported_provider_ids(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ELEVENLABS_API_KEY=fake-elevenlabs-key-for-tests\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        _resolve_tts_request(
            {
                "builder_env_file_path": str(env_file),
                "text": "hello",
                "tts": {"provider_id": "google-cloud-tts"},
            },
            profile=load_voice_profile(),
        )

    message = str(exc_info.value)
    assert "'google-cloud-tts'" in message
    for supported in (
        "elevenlabs",
        "kokoro",
        "kokoro-onnx",
        "local-kokoro",
        "pyttsx3",
        "local",
        "openai-realtime",
        "gpt-realtime-2",
        "realtime",
        "openai-realtime-2",
    ):
        assert supported in message


def test_elevenlabs_provider_resolution_still_succeeds(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ELEVENLABS_API_KEY=fake-elevenlabs-key-for-tests\n", encoding="utf-8")

    request = _resolve_tts_request(
        {
            "builder_env_file_path": str(env_file),
            "text": "hello",
            "tts": {"provider_id": "elevenlabs"},
        },
        profile=load_voice_profile(),
    )

    assert request["provider_id"] == "elevenlabs"
