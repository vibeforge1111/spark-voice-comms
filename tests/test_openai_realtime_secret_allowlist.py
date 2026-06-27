"""Tests: OpenAI Realtime secret_env_ref allowlist — prevents arbitrary env var resolution."""
from __future__ import annotations

import pytest

import voice_comms_chip.spark_hook as _hook
from voice_comms_chip.spark_hook import VOICE_ENV_KEYS, _resolve_openai_realtime_tts_request


def _tts(secret_env_ref: str) -> dict:
    return {"secret_env_ref": secret_env_ref, "provider_id": "openai-realtime"}


def _env_map(secret_env_ref: str, value: str = "test-secret") -> dict:
    return {secret_env_ref: value, "OPENAI_API_KEY": "sk-test-openai"}


def test_aws_secret_access_key_rejected():
    with pytest.raises(ValueError, match="allowlist"):
        _resolve_openai_realtime_tts_request(tts=_tts("AWS_SECRET_ACCESS_KEY"), env_map=_env_map("AWS_SECRET_ACCESS_KEY"), text="hi", surface="")


def test_database_url_rejected():
    with pytest.raises(ValueError, match="allowlist"):
        _resolve_openai_realtime_tts_request(tts=_tts("DATABASE_URL"), env_map=_env_map("DATABASE_URL"), text="hi", surface="")


def test_ssh_private_key_rejected():
    with pytest.raises(ValueError, match="allowlist"):
        _resolve_openai_realtime_tts_request(tts=_tts("SSH_PRIVATE_KEY"), env_map=_env_map("SSH_PRIVATE_KEY"), text="hi", surface="")


def test_allowed_voice_env_key_accepted():
    result = _resolve_openai_realtime_tts_request(
        tts=_tts("OPENAI_API_KEY"),
        env_map={"OPENAI_API_KEY": "sk-test-openai"},
        text="hello world",
        surface="",
    )
    assert result["secret_value"] == "sk-test-openai"


def test_error_raised_before_env_map_lookup_for_disallowed_refs():
    seen = []
    class _TrackingDict(dict):
        def get(self, key, default=None):
            seen.append(key)
            return super().get(key, default)
    env = _TrackingDict({"AWS_SECRET_ACCESS_KEY": "real-secret", "OPENAI_API_KEY": "sk-ok"})
    with pytest.raises(ValueError, match="allowlist"):
        _resolve_openai_realtime_tts_request(tts=_tts("AWS_SECRET_ACCESS_KEY"), env_map=env, text="hi", surface="")
    assert "AWS_SECRET_ACCESS_KEY" not in seen
