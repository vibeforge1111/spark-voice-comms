"""Tests: transcription provider base_url hostname allowlist — SSRF prevention."""
from __future__ import annotations

import pytest

from voice_comms_chip.spark_hook import _transcribe_with_provider


def _provider(base_url: str) -> dict:
    return {"base_url": base_url, "secret_value": "sk-test", "provider_id": "openai", "provider_kind": "openai"}


def test_attacker_base_url_rejected_before_http_request():
    with pytest.raises(ValueError, match="allowlist"):
        _transcribe_with_provider(provider=_provider("https://evil.attacker.com"), audio_bytes=b"x", filename="f.wav", mime_type="audio/wav")


def test_bearer_token_never_sent_to_non_allowlisted_host():
    with pytest.raises(ValueError, match="allowlist"):
        _transcribe_with_provider(provider=_provider("https://capture.example.com/steal"), audio_bytes=b"x", filename="f.wav", mime_type="audio/wav")


def test_api_openai_com_passes_validation(monkeypatch):
    import voice_comms_chip.spark_hook as _hook
    calls = []
    def fake_post(url, *, headers, fields, files):
        calls.append(url)
        return b'{"text": "hello"}'
    monkeypatch.setattr(_hook, "_post_multipart", fake_post)
    result = _transcribe_with_provider(provider=_provider("https://api.openai.com/v1"), audio_bytes=b"x", filename="f.wav", mime_type="audio/wav")
    assert result == "hello"
    assert calls


def test_http_scheme_rejected():
    with pytest.raises(ValueError, match="allowlist"):
        _transcribe_with_provider(provider=_provider("http://api.openai.com/v1"), audio_bytes=b"x", filename="f.wav", mime_type="audio/wav")


def test_valid_transcription_endpoint_proceeds_normally(monkeypatch):
    import voice_comms_chip.spark_hook as _hook
    monkeypatch.setattr(_hook, "_post_multipart", lambda *a, **kw: b'{"text": "transcript"}')
    result = _transcribe_with_provider(provider=_provider("https://api.openai.com/v1"), audio_bytes=b"data", filename="a.wav", mime_type="audio/wav")
    assert result == "transcript"
