from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from voice_comms_chip.spark_hook import (
    _PublicHookInputError,
    _build_deterministic_fallback_transcript,
    _deterministic_transcribe_response,
    _load_hook_payload,
    _post_multipart,
)


def test_deterministic_fallback_does_not_publish_provider_or_path_details():
    secret_reason = "POST https://provider.invalid failed: Bearer not-a-real-secret"
    private_filename = "/Users/private/recordings/family-message.ogg"

    response = _deterministic_transcribe_response(
        audio_bytes=b"voice bytes",
        filename=private_filename,
        reason=secret_reason,
    )
    encoded = json.dumps(response)

    assert "provider.invalid" not in encoded
    assert "not-a-real-secret" not in encoded
    assert "/Users/private" not in encoded
    assert "family-message.ogg" not in encoded
    assert response["returncode"] == 1
    assert response["stdout"] == ""
    assert response["result"]["transcript_text"] == ""
    assert response["result"]["usable_transcript"] is False
    assert response["stderr"] == (
        "I couldn't transcribe that voice note because voice transcription is unavailable. "
        "Please try again once voice is ready."
    )
    assert response["result"]["fallback_reason"] == "Transcription provider unavailable."


def test_fallback_transcript_keeps_helpful_generic_reason():
    transcript = _build_deterministic_fallback_transcript(
        audio_bytes=b"voice bytes",
        filename="private-message.ogg",
        reason="filesystem and provider details",
    )

    assert transcript == (
        "I couldn't transcribe that voice note because voice transcription is unavailable. "
        "Please try again once voice is ready."
    )
    assert "private-message.ogg" not in transcript
    assert "filesystem and provider details" not in transcript
    assert "Deterministic fallback transcript" not in transcript


@pytest.mark.parametrize(
    ("fields", "files", "label"),
    [
        ({'bad"name': "value"}, [], "multipart field name"),
        ({}, [{"field_name": 'bad"name', "filename": "voice.ogg", "mime_type": "audio/ogg", "content": b"x"}], "multipart file field name"),
        ({}, [{"field_name": "file", "filename": 'bad"name.ogg', "mime_type": "audio/ogg", "content": b"x"}], "multipart filename"),
        ({}, [{"field_name": "file", "filename": "voice.ogg", "mime_type": 'audio/ogg";x=y', "content": b"x"}], "multipart content type"),
    ],
)
def test_multipart_rejects_quotes_in_header_tokens(fields, files, label):
    with pytest.raises(ValueError, match=label):
        _post_multipart("https://api.openai.com/v1/audio/transcriptions", headers={}, fields=fields, files=files)


def test_multipart_allows_quotes_in_field_body_values():
    captured: dict[str, bytes] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size=-1):
            return b"{}" if "read" not in captured else b""

    def open_request(request, *, timeout):
        captured["body"] = bytes(request.data)
        captured["read"] = b"1"
        return Response()

    with patch("voice_comms_chip.spark_hook._open_provider_request", side_effect=open_request):
        _post_multipart(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={},
            fields={"prompt": 'say "hello"'},
            files=[],
        )

    assert b'say "hello"' in captured["body"]


def test_hook_loader_normalizes_malformed_json_to_public_input_error(tmp_path):
    payload_path = Path(tmp_path) / "payload.json"
    payload_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(_PublicHookInputError) as exc_info:
        _load_hook_payload(payload_path, hook="voice.status")

    assert exc_info.value.error_code == "voice_hook_invalid_json"
    assert str(exc_info.value) == "Voice hook input must be valid JSON."
