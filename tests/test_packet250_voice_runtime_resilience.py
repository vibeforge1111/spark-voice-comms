from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

from voice_comms_chip import profile, spark_hook


def test_profile_loader_accepts_utf8_bom_and_reports_json_location() -> None:
    bom_path = profile.DEFAULT_PROFILE_PATH.parent / "_packet250_bom.voice_profile.json"
    broken_path = profile.DEFAULT_PROFILE_PATH.parent / "_packet250_broken.voice_profile.json"
    bom_path.write_text('{"profile_name":"packet250"}', encoding="utf-8-sig")
    broken_path.write_text('{\n  "profile_name":\n}', encoding="utf-8")
    try:
        assert profile.load_voice_profile(str(bom_path))["profile_name"] == "packet250"
        with pytest.raises(RuntimeError, match=r"line 3, column 1"):
            profile.load_voice_profile(str(broken_path))
    finally:
        bom_path.unlink(missing_ok=True)
        broken_path.unlink(missing_ok=True)


def test_provider_secret_can_come_from_approved_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "packet250-test-key")
    resolved = spark_hook._resolve_provider(
        {
            "provider": {
                "provider_id": "openai",
                "provider_kind": "openai",
                "execution_transport": "direct_http",
                "base_url": "https://api.openai.com/v1/audio/transcriptions",
                "secret_env_ref": "OPENAI_API_KEY",
            }
        }
    )

    assert resolved["secret_value"] == "packet250-test-key"


def test_local_transcription_settings_use_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VOICE_TRANSCRIBE_LOCAL_MODEL", "small")
    monkeypatch.setenv("VOICE_TRANSCRIBE_LOCAL_LANGUAGE", "en")
    monkeypatch.setenv("VOICE_TRANSCRIBE_LOCAL_VAD_FILTER", "false")
    monkeypatch.setenv("VOICE_TRANSCRIBE_LOCAL_BEAM_SIZE", "3")

    assert spark_hook._resolve_local_faster_whisper_model({}) == "small"
    assert spark_hook._resolve_local_faster_whisper_language({}) == "en"
    assert spark_hook._resolve_local_faster_whisper_vad_filter({}) is False
    assert spark_hook._resolve_local_faster_whisper_beam_size({}) == 3


def test_main_preserves_hook_output_when_runtime_state_export_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text("{}", encoding="utf-8")
    result = {
        "returncode": 1,
        "stdout": "",
        "stderr": "not ready",
        "result": {"ready": False},
    }
    monkeypatch.setattr(spark_hook, "handle_voice_status_hook", lambda payload: result)
    monkeypatch.setattr(
        spark_hook,
        "_export_runtime_state_if_configured",
        lambda payload: (_ for _ in ()).throw(OSError("read-only target")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "voice-hook",
            "voice.status",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    with caplog.at_level(logging.WARNING):
        assert spark_hook.main() == 1

    assert json.loads(output_path.read_text(encoding="utf-8")) == result
    assert "preserving hook output" in caplog.text
    assert "read-only target" in caplog.text


def test_readme_uses_current_builder_run_hook_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "attachments run-hook voice.status --chip-key spark-voice-comms" in readme
    assert "attachments run-hook spark-voice-comms voice.status" not in readme
    assert "- `voice.onboard`" in readme
    assert "- `voice.install`" in readme
