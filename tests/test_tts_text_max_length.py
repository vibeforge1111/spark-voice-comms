from __future__ import annotations

import pytest

from voice_comms_chip.spark_hook import MAX_TTS_TEXT_BYTES, _resolve_tts_request


def test_resolve_tts_request_rejects_text_exceeding_max_bytes():
    """_resolve_tts_request raises ValueError when text exceeds MAX_TTS_TEXT_BYTES."""
    oversized_text = "a" * (MAX_TTS_TEXT_BYTES + 1)
    profile: dict = {}
    payload = {"text": oversized_text}

    with pytest.raises(ValueError, match="exceeds maximum length"):
        _resolve_tts_request(payload, profile=profile)


def test_resolve_tts_request_accepts_text_at_max_bytes():
    """_resolve_tts_request does not raise for text exactly at the byte limit."""
    max_text = "a" * MAX_TTS_TEXT_BYTES
    profile: dict = {}
    payload = {"text": max_text}

    # Will raise for a different reason (missing env/provider), but NOT for max length
    with pytest.raises(ValueError, match="(?i)env file path|builder"):
        _resolve_tts_request(payload, profile=profile)


def test_max_tts_text_bytes_constant_value():
    assert MAX_TTS_TEXT_BYTES == 100_000
