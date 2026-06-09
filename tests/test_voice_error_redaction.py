from __future__ import annotations

import pytest

from voice_comms_chip.spark_hook import _redact_provider_error_body


# --- _redact_provider_error_body unit tests ---

def test_elevenlabs_xi_key_redacted():
    body = '{"detail": "Invalid api_key xi-abcdefghijklmnopqrstuvwxyz01234"}'
    result = _redact_provider_error_body(body)
    assert "xi-abcdefghijklmnopqrstuvwxyz01234" not in result
    assert "[REDACTED]" in result


def test_elevenlabs_xi_key_redacted_short_prefix():
    body = '{"detail": "Unauthorized: xi-AAABBBCCCDDDEEEFFFGGG"}'
    result = _redact_provider_error_body(body)
    assert "xi-AAABBBCCCDDDEEEFFFGGG" not in result
    assert "[REDACTED]" in result


def test_openai_sk_key_redacted():
    body = '{"error": {"message": "Invalid API key sk-abcdefghijklmnopqrstuvwxyz01234"}}'
    result = _redact_provider_error_body(body)
    assert "sk-abcdefghijklmnopqrstuvwxyz01234" not in result
    assert "[REDACTED]" in result


def test_bearer_token_redacted():
    body = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
    result = _redact_provider_error_body(body)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig" not in result
    assert "Bearer [REDACTED]" in result


def test_non_sensitive_error_passes_through():
    body = "voice_not_found: the specified voice id does not exist"
    result = _redact_provider_error_body(body)
    assert result == body


def test_http_status_code_preserved():
    body = '{"status": 403, "message": "xi-AAABBBCCCDDDEEEFFFGGG forbidden"}'
    result = _redact_provider_error_body(body)
    assert "403" in result
    assert "forbidden" in result
    assert "xi-AAABBBCCCDDDEEEFFFGGG" not in result


def test_error_type_preserved_after_redaction():
    body = '{"error": "authentication_failed", "detail": "xi-AAABBBCCCDDDEEEFFFGGG is invalid"}'
    result = _redact_provider_error_body(body)
    assert "authentication_failed" in result
    assert "xi-AAABBBCCCDDDEEEFFFGGG" not in result


def test_empty_body_unchanged():
    assert _redact_provider_error_body("") == ""


def test_body_with_no_secrets_unchanged():
    body = '{"error": "rate_limit_exceeded", "retry_after": 60}'
    assert _redact_provider_error_body(body) == body
