"""Regression: _resolve_provider must default auth_method to 'api_key_env' when absent."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from voice_comms_chip.spark_hook import _resolve_provider

# Patch target: ensures _resolve_dedicated_transcription_provider returns None so tests
# always reach the builder-provided provider section where auth_method is checked.
_PATCH_DEDICATED = "voice_comms_chip.spark_hook._resolve_dedicated_transcription_provider"


def _builder_payload(tmp_path, *, auth_method=None, secret_key_name="MY_VOICE_KEY"):
    env_file = tmp_path / ".env"
    env_file.write_text(f"{secret_key_name}=fake-key-for-test\n", encoding="utf-8")
    provider = {
        "provider_id": "openai",
        "provider_kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "secret_env_ref": secret_key_name,
    }
    if auth_method is not None:
        provider["auth_method"] = auth_method
    return {
        "builder_env_file_path": str(env_file),
        "provider": provider,
    }


# ---------------------------------------------------------------------------
# Auth-method default tests
# ---------------------------------------------------------------------------


def test_absent_auth_method_defaults_to_api_key_env(tmp_path):
    """Provider that omits auth_method must succeed — the fix defaults it to 'api_key_env'."""
    payload = _builder_payload(tmp_path)
    assert "auth_method" not in payload["provider"]
    with patch(_PATCH_DEDICATED, return_value=None):
        result = _resolve_provider(payload)
    assert result["provider_kind"] == "openai"


def test_explicit_api_key_env_preserved(tmp_path):
    """Explicit auth_method='api_key_env' must be accepted and succeed unchanged."""
    payload = _builder_payload(tmp_path, auth_method="api_key_env")
    with patch(_PATCH_DEDICATED, return_value=None):
        result = _resolve_provider(payload)
    assert result["provider_kind"] == "openai"


def test_unsupported_auth_method_still_rejected(tmp_path):
    """Hostile: explicit unsupported auth_method must raise ValueError naming the method."""
    payload = _builder_payload(tmp_path, auth_method="bearer")
    with patch(_PATCH_DEDICATED, return_value=None):
        with pytest.raises(ValueError, match="unsupported auth method"):
            _resolve_provider(payload)


def test_empty_string_auth_method_treated_as_missing(tmp_path):
    """auth_method='' must be treated the same as absent — defaults to 'api_key_env'."""
    payload = _builder_payload(tmp_path, auth_method="")
    with patch(_PATCH_DEDICATED, return_value=None):
        result = _resolve_provider(payload)
    assert result["provider_kind"] == "openai"


def test_whitespace_only_auth_method_treated_as_missing(tmp_path):
    """Hostile: auth_method containing only whitespace must default to 'api_key_env'."""
    payload = _builder_payload(tmp_path, auth_method="   ")
    with patch(_PATCH_DEDICATED, return_value=None):
        result = _resolve_provider(payload)
    assert result["provider_kind"] == "openai"


# ---------------------------------------------------------------------------
# Credential safety tests
# ---------------------------------------------------------------------------


def test_missing_secret_error_names_env_ref_not_value(tmp_path):
    """Hostile: when the env var is absent the error must name the ref, not expose any value."""
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_OTHER_KEY=not-the-secret\n", encoding="utf-8")
    payload = {
        "builder_env_file_path": str(env_file),
        "provider": {
            "provider_id": "openai",
            "provider_kind": "openai",
            "base_url": "https://api.openai.com/v1",
            "secret_env_ref": "MY_MISSING_KEY",
        },
    }
    with patch(_PATCH_DEDICATED, return_value=None):
        with pytest.raises(ValueError) as exc_info:
            _resolve_provider(payload)
    error_msg = str(exc_info.value)
    assert "MY_MISSING_KEY" in error_msg, "error must name the env ref"
    assert "not-the-secret" not in error_msg, "error must not expose other env file values"


def test_result_contains_only_expected_keys(tmp_path):
    """Result dict must have exactly the four expected keys — no raw env dump or extra fields."""
    payload = _builder_payload(tmp_path)
    with patch(_PATCH_DEDICATED, return_value=None):
        result = _resolve_provider(payload)
    assert set(result.keys()) == {"provider_id", "provider_kind", "base_url", "secret_value"}


def test_result_secret_value_comes_from_env_file(tmp_path):
    """secret_value in the result must be the resolved env var — provider dict must not be mutated."""
    payload = _builder_payload(tmp_path, secret_key_name="MY_VOICE_KEY")
    with patch(_PATCH_DEDICATED, return_value=None):
        result = _resolve_provider(payload)
    assert result["secret_value"] == "fake-key-for-test"
    assert "secret_value" not in payload["provider"]
