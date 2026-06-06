import pytest


VOICE_ENV_KEYS = {
    "OPENAI_API_KEY",
    "ELEVENLABS_API_KEY",
    "VOICE_TRANSCRIBE_PROVIDER",
    "VOICE_TRANSCRIBE_BASE_URL",
    "VOICE_TRANSCRIBE_SECRET_ENV_REF",
    "VOICE_TTS_PROVIDER",
    "VOICE_TTS_ELEVENLABS_BASE_URL",
    "VOICE_TTS_ELEVENLABS_MODEL_ID",
    "VOICE_TTS_ELEVENLABS_VOICE_ID",
    "VOICE_TTS_ELEVENLABS_VOICE_NAME",
    "VOICE_TTS_OPENAI_REALTIME_SECRET_ENV_REF",
}


def resolve_secret(secret_env_ref: str, env_map: dict, allowlist: set) -> str:
    """Simulates the fixed secret_env_ref resolution with allowlist guard."""
    if not secret_env_ref:
        raise ValueError("missing voice secret")
    if secret_env_ref not in allowlist:
        raise ValueError(
            f"voice.speak secret_env_ref '{secret_env_ref}' is not in the permitted env-var allowlist."
        )
    value = env_map.get(secret_env_ref)
    if not value:
        raise ValueError("missing voice secret")
    return value


class TestSecretEnvRefAllowlist:
    def test_valid_elevenlabs_key_resolves(self):
        result = resolve_secret("ELEVENLABS_API_KEY", {"ELEVENLABS_API_KEY": "sk-test"}, VOICE_ENV_KEYS)
        assert result == "sk-test"

    def test_valid_openai_key_resolves(self):
        result = resolve_secret("OPENAI_API_KEY", {"OPENAI_API_KEY": "sk-openai"}, VOICE_ENV_KEYS)
        assert result == "sk-openai"

    def test_arbitrary_env_var_rejected(self):
        with pytest.raises(ValueError, match="not in the permitted env-var allowlist"):
            resolve_secret("AWS_SECRET_ACCESS_KEY", {"AWS_SECRET_ACCESS_KEY": "secret"}, VOICE_ENV_KEYS)

    def test_ssh_private_key_env_var_rejected(self):
        with pytest.raises(ValueError, match="not in the permitted env-var allowlist"):
            resolve_secret("SSH_PRIVATE_KEY", {"SSH_PRIVATE_KEY": "-----BEGIN RSA"}, VOICE_ENV_KEYS)

    def test_path_traversal_style_ref_rejected(self):
        with pytest.raises(ValueError, match="not in the permitted env-var allowlist"):
            resolve_secret("../../etc/passwd", {}, VOICE_ENV_KEYS)

    def test_empty_ref_raises_missing_secret(self):
        with pytest.raises(ValueError, match="missing voice secret"):
            resolve_secret("", {}, VOICE_ENV_KEYS)

    def test_database_password_var_rejected(self):
        with pytest.raises(ValueError, match="not in the permitted env-var allowlist"):
            resolve_secret("DATABASE_PASSWORD", {"DATABASE_PASSWORD": "secret"}, VOICE_ENV_KEYS)
