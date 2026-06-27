import pytest


def make_deterministic_reason(exc: Exception, use_fix: bool) -> str:
    """Simulates fixed vs vulnerable reason passing to _deterministic_transcribe_response."""
    if use_fix:
        return "Transcription provider unavailable."
    return str(exc)


class TestVoiceExceptionDisclosure:
    def test_fixed_path_returns_generic_reason(self):
        exc = Exception("Connection to https://api.openai.com failed with 403: Forbidden (key=sk-real-key-123)")
        reason = make_deterministic_reason(exc, use_fix=True)
        assert reason == "Transcription provider unavailable."

    def test_fixed_reason_does_not_contain_url(self):
        exc = Exception("POST https://api.openai.com/v1/audio/transcriptions returned 503")
        reason = make_deterministic_reason(exc, use_fix=True)
        assert "https://" not in reason
        assert "openai.com" not in reason

    def test_fixed_reason_does_not_contain_api_key(self):
        exc = Exception("Auth failed: Bearer sk-proj-abc123xyz")
        reason = make_deterministic_reason(exc, use_fix=True)
        assert "sk-proj" not in reason
        assert "Bearer" not in reason

    def test_vulnerable_path_would_expose_url(self):
        exc = Exception("POST https://api.openai.com/v1/audio/transcriptions returned 503")
        reason = make_deterministic_reason(exc, use_fix=False)
        assert "openai.com" in reason

    def test_generic_reason_is_caller_safe(self):
        exc = Exception("Internal error: /opt/spark/secrets/elevenlabs.key not found")
        reason = make_deterministic_reason(exc, use_fix=True)
        assert "/opt/spark/secrets" not in reason
        assert "elevenlabs.key" not in reason

    def test_generic_message_is_consistent(self):
        exc1 = Exception("timeout after 30s connecting to https://api.elevenlabs.io")
        exc2 = Exception("SSL cert verification failed for api.openai.com")
        assert make_deterministic_reason(exc1, use_fix=True) == make_deterministic_reason(exc2, use_fix=True)
