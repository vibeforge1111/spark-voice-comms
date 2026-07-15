from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from voice_comms_chip.spark_hook import (
    _openai_realtime_ws_url,
    _synthesize_with_openai_realtime,
    _transcribe_with_provider,
    _validate_elevenlabs_base_url,
)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://127.0.0.1:8080",
        "wss://localhost/realtime",
        "wss://169.254.169.254/latest/meta-data",
        "wss://api.openai.com.evil.example/realtime",
        "wss://user:secret@api.openai.com/realtime",
    ],
)
def test_openai_realtime_rejects_untrusted_base_url_before_websocket(base_url: str) -> None:
    with pytest.raises(ValueError, match="OpenAI Realtime base_url"):
        _openai_realtime_ws_url(base_url, model_id="gpt-realtime-2")


def test_openai_realtime_accepts_only_secure_official_endpoint() -> None:
    assert _openai_realtime_ws_url(
        "https://api.openai.com/v1",
        model_id="gpt-realtime-2",
    ) == "wss://api.openai.com/v1/realtime?model=gpt-realtime-2"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.elevenlabs.io/v1",
        "https://user:secret@api.elevenlabs.io/v1",
        "https://api.elevenlabs.io:8443/v1",
        "https://api.elevenlabs.io.evil.example/v1",
    ],
)
def test_elevenlabs_rejects_noncanonical_credential_endpoint(base_url: str) -> None:
    with pytest.raises(ValueError, match="ElevenLabs base_url"):
        _validate_elevenlabs_base_url(base_url)


@pytest.mark.parametrize(
    ("provider_kind", "base_url"),
    [
        ("openai", "https://127.0.0.1/v1"),
        ("openai", "https://api.openai.com.evil.example/v1"),
        ("openai", "http://api.openai.com/v1"),
        ("custom", "https://voice.example.test/v1"),
    ],
)
def test_transcription_rejects_untrusted_endpoint_before_bearer_request(
    provider_kind: str,
    base_url: str,
) -> None:
    provider = {
        "provider_id": provider_kind,
        "provider_kind": provider_kind,
        "base_url": base_url,
        "secret_value": "fake-provider-key-for-tests",
    }
    with patch("voice_comms_chip.spark_hook._post_multipart") as post:
        with pytest.raises(ValueError, match="transcription provider"):
            _transcribe_with_provider(
                provider=provider,
                audio_bytes=b"fake-audio",
                filename="voice.ogg",
                mime_type="audio/ogg",
            )
    post.assert_not_called()


def test_openai_realtime_disables_credential_forwarding_redirects() -> None:
    captured: dict[str, object] = {}

    def fake_create_connection(_url: str, **kwargs: object) -> object:
        captured.update(kwargs)
        raise RuntimeError("stop after websocket options are captured")

    with patch.dict(
        sys.modules,
        {"websocket": SimpleNamespace(create_connection=fake_create_connection)},
    ):
        with pytest.raises(RuntimeError, match="options are captured"):
            _synthesize_with_openai_realtime(
                request={
                    "base_url": "wss://api.openai.com/v1/realtime",
                    "model_id": "gpt-realtime-2",
                    "secret_value": "fake-openai-key-for-tests",
                    "text": "hello",
                }
            )

    assert captured["redirect_limit"] == 0
