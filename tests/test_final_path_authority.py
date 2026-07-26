from __future__ import annotations

from pathlib import Path

import pytest

import voice_comms_chip.profile as profile_module
from voice_comms_chip.profile import load_voice_profile
from voice_comms_chip.runtime_state import json_safe
from voice_comms_chip.spark_hook import (
    _read_env_map,
    _resolve_kokoro_tts_request,
)


def test_builder_env_path_is_contained_without_reflecting_private_path(tmp_path, monkeypatch):
    allowed = tmp_path / "spark-home"
    allowed.mkdir()
    monkeypatch.setenv("SPARK_VOICE_ENV_ROOT", str(allowed))

    outside = tmp_path / "private" / "credentials.env"
    outside.parent.mkdir()
    outside.write_text("OPENAI_API_KEY=not-a-real-secret\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        _read_env_map(env_file_path=str(outside))

    message = str(exc_info.value)
    assert "outside" not in message
    assert "credentials.env" not in message
    assert "approved voice configuration roots" in message


def test_builder_env_path_rejects_symlink_escape(tmp_path, monkeypatch):
    allowed = tmp_path / "spark-home"
    allowed.mkdir()
    outside = tmp_path / "outside.env"
    outside.write_text("OPENAI_API_KEY=not-a-real-secret\n", encoding="utf-8")
    link = allowed / ".env"
    link.symlink_to(outside)
    monkeypatch.setenv("SPARK_VOICE_ENV_ROOT", str(allowed))

    with pytest.raises(ValueError, match="approved voice configuration roots"):
        _read_env_map(env_file_path=str(link))


def test_builder_env_parser_supports_export_and_quotes(tmp_path, monkeypatch):
    allowed = tmp_path / "spark-home"
    allowed.mkdir()
    env_file = allowed / ".env"
    env_file.write_text(
        "export OPENAI_API_KEY='not-a-real-secret'\nELEVENLABS_API_KEY=\"also-not-real\"\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SPARK_VOICE_ENV_ROOT", str(allowed))

    assert _read_env_map(env_file_path=str(env_file)) == {
        "OPENAI_API_KEY": "not-a-real-secret",
        "ELEVENLABS_API_KEY": "also-not-real",
    }


def test_kokoro_assets_are_contained_in_explicit_asset_root(tmp_path, monkeypatch):
    allowed = tmp_path / "voice-assets"
    allowed.mkdir()
    model = allowed / "model.onnx"
    voices = allowed / "voices.bin"
    model.write_bytes(b"model")
    voices.write_bytes(b"voices")
    monkeypatch.setenv("SPARK_VOICE_ASSET_ROOT", str(allowed))

    request = _resolve_kokoro_tts_request(
        tts={"model_path": str(model), "voices_path": str(voices)},
        env_map={},
        text="hello",
        surface="telegram",
    )

    assert request["model_path"] == str(model.resolve())
    assert request["voices_path"] == str(voices.resolve())


def test_kokoro_asset_rejects_symlink_escape(tmp_path, monkeypatch):
    allowed = tmp_path / "voice-assets"
    allowed.mkdir()
    outside = tmp_path / "private-model.onnx"
    outside.write_bytes(b"model")
    model = allowed / "model.onnx"
    model.symlink_to(outside)
    voices = allowed / "voices.bin"
    voices.write_bytes(b"voices")
    monkeypatch.setenv("SPARK_VOICE_ASSET_ROOT", str(allowed))

    with pytest.raises(ValueError, match="approved voice asset roots"):
        _resolve_kokoro_tts_request(
            tts={"model_path": str(model), "voices_path": str(voices)},
            env_map={},
            text="hello",
            surface="telegram",
        )


def test_profile_loader_uses_validated_resolved_path(tmp_path, monkeypatch):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    target = profiles / "voice.json"
    target.write_text('{"name":"safe"}', encoding="utf-8")
    link = profiles / "selected.json"
    link.symlink_to(target)
    monkeypatch.setattr(profile_module, "ALLOWED_DIRECTORIES", [profiles])

    assert load_voice_profile(str(link)) == {"name": "safe"}


def test_json_safe_stops_deep_recursive_values():
    value: object = "leaf"
    for _ in range(2000):
        value = [value]

    rendered = json_safe(value)

    assert "[depth limit]" in rendered
    assert len(rendered) < 256
