from __future__ import annotations

import base64
import json
import logging
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from voice_comms_chip import profile, spark_hook


def test_manifest_version_matches_package_version() -> None:
    manifest = tomllib.loads(Path("spark.toml").read_text(encoding="utf-8"))
    package = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert manifest["module"]["version"] == package["project"]["version"]


def test_manifest_declares_dedicated_managed_openai_voice_secret() -> None:
    manifest = tomllib.loads(Path("spark.toml").read_text(encoding="utf-8"))

    assert "voice.openai.api_key" in manifest["needs"]["secrets"]
    assert "voice.openai.api_key" in manifest["claims"]["secrets"]
    assert manifest["secrets"]["voice_openai_api_key"] == {
        "prompt": "Optional OpenAI API key for hosted Spark voice STT and Realtime TTS",
        "required": False,
        "storage": "keychain",
        "env_var": "VOICE_OPENAI_API_KEY",
    }


def test_realtime_fallback_audio_emits_debug_evidence(
    caplog,
) -> None:
    pcm = b"\x00\x00\x01\x00"
    events = iter(
        [
            json.dumps(
                {
                    "type": "response.content_part.done",
                    "part": {"audio": base64.b64encode(pcm).decode("ascii")},
                }
            ),
            json.dumps({"type": "response.done"}),
        ]
    )
    socket = SimpleNamespace(
        send=Mock(),
        recv=lambda: next(events),
        close=Mock(),
    )
    module = SimpleNamespace(create_connection=lambda *args, **kwargs: socket)

    with (
        patch.dict(sys.modules, {"websocket": module}),
        caplog.at_level(logging.DEBUG),
    ):
        audio, _voice = spark_hook._synthesize_with_openai_realtime(
            request={
                "base_url": "wss://api.openai.com/v1/realtime",
                "model_id": "gpt-realtime-2",
                "secret_value": "test-secret",
                "text": "hello",
            }
        )

    assert audio.startswith(b"RIFF")
    assert "content_part.done audio" in caplog.text
    assert "test-secret" not in caplog.text


def test_onboarding_hides_env_reader_exception_payload(
    caplog,
) -> None:
    with (
        patch.object(
            spark_hook,
            "_read_env_map",
            side_effect=ValueError("secret local path"),
        ),
        patch.object(spark_hook, "_local_faster_whisper_available", return_value=False),
        patch.object(
            spark_hook,
            "_local_tts_status",
            return_value={"ready": False, "provider": "none", "status": "unavailable"},
        ),
        patch.object(
            spark_hook,
            "_paid_tts_status",
            return_value={"ready": False, "provider": "none", "status": "unavailable"},
        ),
        caplog.at_level(logging.WARNING),
    ):
        snapshot = spark_hook._build_onboarding_snapshot(
            {"builder_env_file_path": "/approved/missing.env"}
        )

    assert snapshot["env"]["status"] == "Builder env file unavailable"
    assert "ValueError" in caplog.text
    assert "secret local path" not in caplog.text


def test_unrecognized_vad_value_logs_named_setting(caplog) -> None:
    with (
        patch.object(
            spark_hook,
            "_runtime_env_map",
            return_value={"VOICE_TRANSCRIBE_LOCAL_VAD_FILTER": "sometimes"},
        ),
        caplog.at_level(logging.WARNING),
    ):
        assert spark_hook._resolve_local_faster_whisper_vad_filter(
            {"builder_env_file_path": "/approved/.env"}
        ) is True

    assert "VOICE_TRANSCRIBE_LOCAL_VAD_FILTER" in caplog.text
    assert "sometimes" not in caplog.text


def test_status_dry_run_does_not_export_runtime_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text("{}", encoding="utf-8")
    exported: list[dict[str, object]] = []
    monkeypatch.setattr(
        spark_hook,
        "_build_voice_status",
        lambda payload: {"ready": True, "reason": "local proof"},
    )
    monkeypatch.setattr(
        spark_hook,
        "_export_runtime_state_if_configured",
        exported.append,
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
            "--dry-run",
        ],
    )

    assert spark_hook.main() == 0
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["result"] == {
        "ready": True,
        "reason": "local proof",
        "dry_run": True,
    }
    assert exported == []


def test_profile_validation_cli_uses_bounded_profile_loader(
    capsys,
    monkeypatch,
) -> None:
    path = profile.DEFAULT_PROFILE_PATH.parent / "_packet249.voice_profile.json"
    path.write_text(
        json.dumps({"profile_name": "packet249"}),
        encoding="utf-8",
    )
    try:
        monkeypatch.setattr(sys, "argv", ["voice-profile", "--validate", str(path)])
        assert profile.main() == 0
        assert "Profile valid: packet249" in capsys.readouterr().out
    finally:
        path.unlink(missing_ok=True)
