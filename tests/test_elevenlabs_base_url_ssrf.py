"""Tests: ElevenLabs TTS base_url hostname allowlist — SSRF prevention."""
from __future__ import annotations

import pytest

from voice_comms_chip.spark_hook import _synthesize_with_elevenlabs


def _request(base_url: str) -> dict:
    return {
        "base_url": base_url,
        "secret_value": "test-xi-key",
        "text": "hello",
        "voice_id": "test-voice",
        "model_id": "eleven_turbo_v2_5",
        "output_format": "mp3_44100_128",
        "voice_settings": {"stability": 0.9, "similarity_boost": 0.8, "style": 0.0, "use_speaker_boost": True, "speed": 1.0},
    }


def test_attacker_base_url_rejected():
    with pytest.raises(ValueError, match="allowlist"):
        _synthesize_with_elevenlabs(request=_request("https://evil.attacker.com/capture"))


def test_xi_api_key_never_sent_to_non_allowlisted_host():
    with pytest.raises(ValueError, match="allowlist"):
        _synthesize_with_elevenlabs(request=_request("https://capture.example.com"))


def test_api_elevenlabs_io_accepted(monkeypatch):
    import urllib.request as _ur
    def fake_urlopen(req, timeout=None):
        class _Resp:
            def read(self): return b"\xff\xfb" * 100
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return _Resp()
    monkeypatch.setattr(_ur, "urlopen", fake_urlopen)
    audio, _ = _synthesize_with_elevenlabs(request=_request("https://api.elevenlabs.io/v1"))
    assert audio


def test_non_elevenlabs_domain_rejected():
    with pytest.raises(ValueError, match="allowlist"):
        _synthesize_with_elevenlabs(request=_request("https://openai.com/v1"))


def test_http_scheme_rejected():
    with pytest.raises(ValueError, match="allowlist"):
        _synthesize_with_elevenlabs(request=_request("http://api.elevenlabs.io/v1"))
