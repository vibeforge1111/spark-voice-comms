from __future__ import annotations

import base64
import io
import json
import sys
import urllib.error
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from voice_comms_chip.spark_hook import (
    _build_speak_coherence,
    _join_url,
    _write_output,
    assertNativeGovernorHarnessAuthority,
    handle_voice_install_hook,
    handle_voice_onboard_hook,
    handle_voice_plan_hook,
    handle_voice_speak_hook,
    handle_voice_status_hook,
    handle_voice_transcribe_hook,
    _read_env_map,
    main,
)

FAKE_OPENAI_KEY = "fake-openai-key-for-tests"
FAKE_ELEVENLABS_KEY = "fake-elevenlabs-key-for-tests"
FAKE_ELEVENLABS_VOICE_ID = "fake-elevenlabs-voice-id"


class _FakeBinaryHttpResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            return self._payload
        result = self._payload[:size]
        self._payload = self._payload[size:]
        return result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _payload(tmp_path, **overrides):
    env_file = tmp_path / ".env"
    env_file.write_text(f"OPENAI_API_KEY={FAKE_OPENAI_KEY}\n", encoding="utf-8")
    payload = {
        "builder_env_file_path": str(env_file),
        "governor_decision": _voice_governor_decision(
            "voice.install",
            "voice.transcribe",
            "voice.speak",
        ),
        "provider": {
            "provider_id": "openai",
            "provider_kind": "openai",
            "auth_method": "api_key_env",
            "base_url": "https://api.openai.com/v1",
            "secret_env_ref": "OPENAI_API_KEY",
        },
    }
    payload.update(overrides)
    return payload


def test_read_env_map_strips_matching_outer_quotes(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                'DOUBLE_QUOTED="double-value"',
                "SINGLE_QUOTED='single-value'",
                "UNQUOTED=plain-value",
                'UNMATCHED="keep-leading-quote',
                'INNER_QUOTES=prefix"inner"suffix',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert _read_env_map(env_file_path=str(env_file)) == {
        "DOUBLE_QUOTED": "double-value",
        "SINGLE_QUOTED": "single-value",
        "UNQUOTED": "plain-value",
        "UNMATCHED": '"keep-leading-quote',
        "INNER_QUOTES": 'prefix"inner"suffix',
    }


def _voice_governor_decision(*hooks: str) -> dict[str, object]:
    actions = []
    authorizations = []
    ledgers = []
    for hook in hooks:
        action_id = f"action:{hook}"
        authorization = {
            "schema_version": "authorization-decision-v1",
            "decision_id": f"auth:{hook}",
            "verdict": "allow",
            "action_id": action_id,
            "capability_id": hook,
            "turn_id": "turn:voice-test",
        }
        actions.append(
            {
                "action_id": action_id,
                "capability_id": hook,
                "tool_name": hook,
                "action_type": "local_install_or_network_voice",
            }
        )
        authorizations.append(authorization)
        ledgers.append(
            {
                "schema_version": "tool-call-ledger-v1",
                "ledger_id": f"ledger:{hook}",
                "tool_name": hook,
                "capability_id": hook,
                "action_id": action_id,
                "turn_id": "turn:voice-test",
                "authorization": authorization,
                "result": {"status": "not_started"},
            }
        )
    return {
        "schema_version": "governor-decision-v1",
        "decision_id": "governor:voice-test",
        "turn_id": "turn:voice-test",
        "outcome": "execute",
        "envelope": {
            "schema_version": "turn-intent-envelope-vnext",
            "turn_id": "turn:voice-test",
            "proposed_actions": actions,
        },
        "authorizations": authorizations,
        "tool_ledgers": ledgers,
    }


def _authorized_voice_payload(hook: str, payload: dict[str, object]) -> dict[str, object]:
    return {**payload, "governor_decision": _voice_governor_decision(hook)}


def test_voice_status_default_requires_local_faster_whisper(tmp_path):
    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=False):
        result = handle_voice_status_hook(_payload(tmp_path))
    assert result["returncode"] == 0
    assert result["result"]["ready"] is False
    assert result["result"]["provider_id"] == "local_faster_whisper"
    assert "local faster-whisper transcription is the default Telegram voice path" in result["result"]["reason"]
    assert "Voice chip is not ready yet." in result["result"]["reply_text"]


def test_voice_status_marks_custom_provider_as_unverified(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("CUSTOM_API_KEY=custom-test-key\n", encoding="utf-8")
    with patch.dict("os.environ", {"VOICE_TRANSCRIBE_PROVIDER": "builder"}, clear=False), patch(
        "voice_comms_chip.spark_hook._local_faster_whisper_available",
        return_value=False,
    ):
        result = handle_voice_status_hook(
            {
                "builder_env_file_path": str(env_file),
                "provider": {
                    "provider_id": "custom",
                    "provider_kind": "custom",
                    "auth_method": "api_key_env",
                    "execution_transport": "direct_http",
                    "base_url": "https://api.example.com/v1",
                    "secret_env_ref": "CUSTOM_API_KEY",
                },
            }
        )
    assert result["returncode"] == 0
    assert result["result"]["ready"] is False
    assert "custom provider transcription compatibility is not verified" in result["result"]["reason"] or "is not in the allowlist" in result["result"]["reason"]


def test_voice_status_reports_local_ready_before_custom_provider_warning(tmp_path):
    model_path = tmp_path / "kokoro-v1.0.onnx"
    voices_path = tmp_path / "voices-v1.0.bin"
    model_path.write_bytes(b"model")
    voices_path.write_bytes(b"voices")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "CUSTOM_API_KEY=custom-test-key",
                "VOICE_TTS_PROVIDER=kokoro",
                f"VOICE_TTS_KOKORO_MODEL_PATH={model_path}",
                f"VOICE_TTS_KOKORO_VOICES_PATH={voices_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True), patch(
        "voice_comms_chip.spark_hook._local_kokoro_package_available",
        return_value=True,
    ):
        result = handle_voice_status_hook(
            {
                "builder_env_file_path": str(env_file),
                "provider": {
                    "provider_id": "custom",
                    "provider_kind": "custom",
                    "auth_method": "api_key_env",
                    "execution_transport": "direct_http",
                    "base_url": "https://api.example.com/v1",
                    "secret_env_ref": "CUSTOM_API_KEY",
                },
            }
        )

    assert result["returncode"] == 0
    assert result["result"]["ready"] is True
    assert result["result"]["local_ready"] is True
    assert "Local voice is ready." in result["result"]["reply_text"]
    assert "Custom provider transcription compatibility is not verified yet" in result["result"]["reply_text"]
    assert "ask me to say something with Kokoro" in result["result"]["reply_text"]
    assert "Voice chip is not ready yet" not in result["result"]["reply_text"]


def test_voice_status_prefers_local_transcription_when_available_even_with_openai_key(tmp_path):
    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True):
        result = handle_voice_status_hook(_payload(tmp_path))

    assert result["returncode"] == 0
    assert result["result"]["ready"] is True
    assert result["result"]["local_ready"] is True
    assert result["result"]["provider_id"] == "local_faster_whisper"
    assert result["result"]["model"] == "tiny"
    assert "Local transcription is ready." in result["result"]["reply_text"]
    assert "I will listen with faster-whisper from this machine." in result["result"]["reply_text"]
    assert "transcription is configured via openai" not in result["result"]["reply_text"]


def test_voice_status_prefers_dedicated_openai_transcription_env_over_custom_provider(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"OPENAI_API_KEY={FAKE_OPENAI_KEY}",
                "VOICE_TRANSCRIBE_PROVIDER=openai",
                "VOICE_TRANSCRIBE_SECRET_ENV_REF=OPENAI_API_KEY",
                "VOICE_TRANSCRIBE_BASE_URL=https://api.openai.com/v1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result = handle_voice_status_hook(
        {
            "builder_env_file_path": str(env_file),
            "provider": {
                "provider_id": "custom",
                "provider_kind": "custom",
                "auth_method": "api_key_env",
                "execution_transport": "direct_http",
                "base_url": "https://api.example.com/v1",
                "secret_env_ref": "CUSTOM_API_KEY",
            },
        }
    )

    assert result["returncode"] == 0
    assert result["result"]["ready"] is True
    assert result["result"]["provider_id"] == "openai"
    assert result["result"]["runtime_state"]["schema_version"] == "spark.voice_runtime_state.v1"
    assert result["result"]["runtime_state"]["stt"]["provider_id"] == "openai"
    assert result["result"]["runtime_state"]["claim_levels"]["delivery_ready"] is False


def test_voice_plan_returns_modular_steps():
    result = handle_voice_plan_hook({})
    assert result["returncode"] == 0
    assert "spark-voice-comms" in result["result"]["reply_text"]


def test_voice_authority_requires_matching_tool_ledger():
    payload = {"governor_decision": _voice_governor_decision("voice.speak")}

    authority = assertNativeGovernorHarnessAuthority(payload, hook="voice.speak")

    assert authority["decision_id"] == "governor:voice-test"


def test_voice_authority_rejects_missing_governor_decision():
    with pytest.raises(ValueError, match="requires Harness Core Governor authority"):
        assertNativeGovernorHarnessAuthority({}, hook="voice.speak")


def test_voice_authority_rejects_tampered_tool_ledger():
    decision = _voice_governor_decision("voice.speak")
    decision["tool_ledgers"][0]["action_id"] = "action:other"

    with pytest.raises(ValueError, match="matching Harness Core authorization and tool ledger"):
        assertNativeGovernorHarnessAuthority({"governor_decision": decision}, hook="voice.speak")


def test_voice_onboard_guides_local_free_path():
    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True), patch(
        "voice_comms_chip.spark_hook._local_pyttsx3_available",
        return_value=True,
    ), patch(
        "voice_comms_chip.spark_hook._local_kokoro_package_available",
        return_value=False,
    ):
        result = handle_voice_onboard_hook({"route": "local"})

    assert result["returncode"] == 0
    assert result["result"]["recommended_path"] == "local_free"
    assert result["metrics"]["local_ready"] == 1
    assert "local voice is ready" in result["result"]["reply_text"]
    assert "one short voice reply" in result["result"]["reply_text"]
    assert "What I can see right now" not in result["result"]["reply_text"]


def test_voice_onboard_prefers_ready_kokoro_for_local_tts():
    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True), patch(
        "voice_comms_chip.spark_hook._local_kokoro_ready",
        return_value=True,
    ), patch(
        "voice_comms_chip.spark_hook._local_kokoro_package_available",
        return_value=True,
    ), patch(
        "voice_comms_chip.spark_hook._local_pyttsx3_available",
        return_value=False,
    ):
        result = handle_voice_onboard_hook({"route": "local"})

    assert result["returncode"] == 0
    assert result["metrics"]["local_ready"] == 1
    assert result["result"]["snapshot"]["local_tts"]["provider"] == "kokoro"
    assert "Kokoro for replies" in result["result"]["reply_text"]
    assert "currently running through" not in result["result"]["reply_text"]


def test_voice_onboard_reads_kokoro_from_process_env_when_builder_env_lacks_voice_keys(tmp_path):
    builder_env = tmp_path / ".env"
    builder_env.write_text("SPARK_BUILDER_HOME=C:/fake/builder\n", encoding="utf-8")
    model_path = tmp_path / "kokoro-v1.0.onnx"
    voices_path = tmp_path / "voices-v1.0.bin"
    model_path.write_bytes(b"model")
    voices_path.write_bytes(b"voices")

    with patch.dict(
        "os.environ",
        {
            "VOICE_TTS_PROVIDER": "kokoro",
            "VOICE_TTS_KOKORO_MODEL_PATH": "kokoro-v1.0.onnx",
            "VOICE_TTS_KOKORO_VOICES_PATH": "voices-v1.0.bin",
        },
        clear=False,
    ), patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True), patch(
        "voice_comms_chip.spark_hook._local_kokoro_package_available",
        return_value=True,
    ), patch(
        "voice_comms_chip.spark_hook._local_pyttsx3_available",
        return_value=False,
    ):
        result = handle_voice_onboard_hook({"route": "local", "builder_env_file_path": str(builder_env)})

    assert result["returncode"] == 0
    assert result["metrics"]["local_ready"] == 1
    assert result["result"]["snapshot"]["local_tts"]["provider"] == "kokoro"
    assert "Kokoro for replies" in result["result"]["reply_text"]


def test_voice_onboard_uses_source_labeled_local_preference():
    result = handle_voice_onboard_hook(
        {
            "advisor_context": {
                "preferences": [
                    {
                        "value": "User prefers local/private tooling when quality is good enough.",
                        "source": "governed_current_state_memory",
                    }
                ]
            }
        }
    )

    assert result["returncode"] == 0
    assert result["result"]["preference_note"]["preference"] == "local"
    assert "saved preference signal" in result["result"]["reply_text"]


def test_voice_install_kokoro_runs_local_pip_when_missing():
    calls: list[list[str]] = []

    def fake_run(command, *, capture_output: bool, text: bool, timeout: int, check: bool):
        calls.append(command)
        assert capture_output is True
        assert text is True
        assert timeout == 300
        assert check is False
        return SimpleNamespace(returncode=0, stdout="installed ok\n", stderr="")

    with patch("voice_comms_chip.spark_hook._kokoro_python_unsupported_message", return_value=None), patch(
        "voice_comms_chip.spark_hook._local_kokoro_package_available",
        side_effect=[False, True, True],
    ), patch("voice_comms_chip.spark_hook.subprocess.run", side_effect=fake_run):
        result = handle_voice_install_hook(_authorized_voice_payload("voice.install", {"target": "kokoro"}))

    assert result["returncode"] == 0
    assert result["result"]["installed"] is True
    assert result["result"]["already_installed"] is False
    assert calls
    assert calls[0][1:4] == ["-m", "pip", "install"]
    assert "kokoro-onnx>=0.5.0" in calls[0]
    assert "soundfile>=0.12" in calls[0]
    assert "Kokoro is installed" in result["result"]["reply_text"]
    assert "local setup step" in result["result"]["reply_text"]
    assert "VOICE_TTS_KOKORO_MODEL_PATH" not in result["result"]["reply_text"]
    assert "Python:" not in result["result"]["reply_text"]


def test_voice_install_kokoro_skips_pip_when_already_installed():
    with patch("voice_comms_chip.spark_hook._kokoro_python_unsupported_message", return_value=None), patch(
        "voice_comms_chip.spark_hook._local_kokoro_package_available",
        return_value=True,
    ), patch(
        "voice_comms_chip.spark_hook.subprocess.run",
    ) as run:
        result = handle_voice_install_hook(_authorized_voice_payload("voice.install", {"target": "kokoro"}))

    assert result["returncode"] == 0
    assert result["stdout"] == "already_installed"
    assert result["result"]["installed"] is True
    assert result["result"]["already_installed"] is True
    run.assert_not_called()


def test_voice_install_kokoro_sees_model_assets_from_process_env(tmp_path):
    model_path = tmp_path / "kokoro-v1.0.onnx"
    voices_path = tmp_path / "voices-v1.0.bin"
    model_path.write_bytes(b"model")
    voices_path.write_bytes(b"voices")

    with patch.dict(
        "os.environ",
        {
            "VOICE_TTS_KOKORO_MODEL_PATH": "kokoro-v1.0.onnx",
            "VOICE_TTS_KOKORO_VOICES_PATH": "voices-v1.0.bin",
        },
        clear=False,
    ), patch("voice_comms_chip.spark_hook._kokoro_python_unsupported_message", return_value=None), patch(
        "voice_comms_chip.spark_hook._local_kokoro_package_available",
        return_value=True,
    ), patch(
        "voice_comms_chip.spark_hook.subprocess.run",
    ) as run:
        result = handle_voice_install_hook(_authorized_voice_payload("voice.install", {"target": "kokoro"}))

    assert result["returncode"] == 0
    assert result["result"]["kokoro_ready"] is True
    assert "local voice files" in result["result"]["reply_text"]
    assert "local setup step" not in result["result"]["reply_text"]
    assert "\n\n" in result["result"]["reply_text"]
    run.assert_not_called()


def test_voice_install_faster_whisper_runs_local_pip_when_missing():
    calls: list[list[str]] = []

    def fake_run(command, *, capture_output: bool, text: bool, timeout: int, check: bool):
        calls.append(command)
        assert capture_output is True
        assert text is True
        assert timeout == 300
        assert check is False
        return SimpleNamespace(returncode=0, stdout="installed ok\n", stderr="")

    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", side_effect=[False, True]), patch(
        "voice_comms_chip.spark_hook.subprocess.run",
        side_effect=fake_run,
    ):
        result = handle_voice_install_hook(_authorized_voice_payload("voice.install", {"target": "faster-whisper"}))

    assert result["returncode"] == 0
    assert result["result"]["installed"] is True
    assert result["result"]["stt_ready"] is True
    assert calls
    assert calls[0][1:4] == ["-m", "pip", "install"]
    assert "faster-whisper>=1.0" in calls[0]
    assert "send one short Telegram voice note" in result["result"]["reply_text"]


def test_voice_install_kokoro_reports_unsupported_python_runtime():
    message = "kokoro-onnx failed from /tmp/private-runtime with sk-live-secret and traceback detail."

    with patch("voice_comms_chip.spark_hook._kokoro_python_unsupported_message", return_value=message), patch(
        "voice_comms_chip.spark_hook.subprocess.run",
    ) as run:
        result = handle_voice_install_hook(_authorized_voice_payload("voice.install", {"target": "kokoro"}))

    encoded = json.dumps(result)
    assert result["returncode"] == 1
    assert result["stdout"] == ""
    assert result["stderr"] == "Kokoro install is not supported in this Python runtime."
    assert result["error"] == result["stderr"]
    assert result["error_code"] == "voice_install_unsupported_runtime"
    assert result["metrics"]["installed"] == 0
    assert result["result"]["error_code"] == "voice_install_unsupported_runtime"
    assert result["result"]["installed"] is False
    assert result["result"]["kokoro_ready"] is False
    assert "cannot run in this Python runtime" in result["result"]["reply_text"]
    assert "Python 3.10-3.13" in result["result"]["reply_text"]
    assert message not in encoded
    assert "/tmp/private-runtime" not in encoded
    assert "sk-live-secret" not in encoded
    assert "traceback" not in encoded.lower()
    run.assert_not_called()


def test_voice_install_local_stack_installs_stt_and_kokoro_packages():
    calls: list[list[str]] = []

    def fake_run(command, *, capture_output: bool, text: bool, timeout: int, check: bool):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="installed ok\n", stderr="")

    with patch("voice_comms_chip.spark_hook._kokoro_python_unsupported_message", return_value=None), patch(
        "voice_comms_chip.spark_hook._local_faster_whisper_available",
        side_effect=[False, True],
    ), patch(
        "voice_comms_chip.spark_hook._local_kokoro_package_available",
        side_effect=[False, True, True],
    ), patch("voice_comms_chip.spark_hook._local_kokoro_ready", return_value=False), patch(
        "voice_comms_chip.spark_hook.subprocess.run",
        side_effect=fake_run,
    ):
        result = handle_voice_install_hook(_authorized_voice_payload("voice.install", {"target": "local"}))

    assert result["returncode"] == 0
    assert result["result"]["installed"] is True
    assert result["result"]["stt_ready"] is True
    assert result["result"]["kokoro_installed"] is True
    assert len(calls) == 2
    assert "faster-whisper>=1.0" in calls[0]
    assert "kokoro-onnx>=0.5.0" in calls[1]
    assert "`/voice onboard local`" in result["result"]["reply_text"]


def test_voice_onboard_reports_paid_provider_readiness(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"OPENAI_API_KEY={FAKE_OPENAI_KEY}",
                f"ELEVENLABS_API_KEY={FAKE_ELEVENLABS_KEY}",
                f"VOICE_TTS_ELEVENLABS_VOICE_ID={FAKE_ELEVENLABS_VOICE_ID}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = handle_voice_onboard_hook({"route": "paid", "builder_env_file_path": str(env_file)})

    assert result["returncode"] == 0
    assert result["result"]["recommended_path"] == "paid_provider"
    assert result["metrics"]["paid_ready"] == 1
    assert result["result"]["snapshot"]["paid_tts"]["ready"] is True


def test_voice_onboard_reads_openai_realtime_from_utf8_sig_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"OPENAI_API_KEY={FAKE_OPENAI_KEY}",
                "VOICE_TTS_PROVIDER=openai-realtime",
                "VOICE_TTS_OPENAI_REALTIME_MODEL_ID=gpt-realtime-2",
            ]
        )
        + "\n",
        encoding="utf-8-sig",
    )

    result = handle_voice_onboard_hook({"route": "paid", "builder_env_file_path": str(env_file)})

    assert result["returncode"] == 0
    assert result["result"]["snapshot"]["paid_tts"]["ready"] is True
    assert result["result"]["snapshot"]["paid_tts"]["provider"] == "openai-realtime"
    assert "GPT Realtime 2" in result["result"]["reply_text"]


def test_cli_main_accepts_utf8_sig_payload(tmp_path):
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text('{"route":"local"}', encoding="utf-8-sig")

    with patch.object(
        sys,
        "argv",
        [
            "spark_hook",
            "voice.onboard",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    ):
        exit_code = main()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["result"]["recommended_path"] == "local_free"


def test_cli_main_writes_structured_error_for_invalid_json(tmp_path):
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    hostile_payload = "{bad json with /tmp/private-builder.env and sk-live-secret"
    input_path.write_text(hostile_payload, encoding="utf-8")

    with patch.object(
        sys,
        "argv",
        [
            "spark_hook",
            "voice.status",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    ):
        exit_code = main()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    encoded = json.dumps(payload)
    assert exit_code == 1
    assert payload["returncode"] == 1
    assert payload["error_code"] == "voice_hook_invalid_json"
    assert payload["error"] == "Voice hook input must be valid JSON."
    assert payload["stderr"] == payload["error"]
    assert payload["result"] == {}
    assert hostile_payload not in encoded
    assert "/tmp/private-builder.env" not in encoded
    assert "sk-live-secret" not in encoded


def test_cli_main_rejects_non_object_payload_before_hook_execution(tmp_path):
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text("[]", encoding="utf-8")

    with patch.object(
        sys,
        "argv",
        [
            "spark_hook",
            "voice.status",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    ), patch(
        "voice_comms_chip.spark_hook.handle_voice_status_hook",
        side_effect=AssertionError("non-object input should not execute hook logic"),
    ):
        exit_code = main()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["returncode"] == 1
    assert payload["error_code"] == "voice_hook_input_not_object"
    assert payload["error"] == "Voice hook input must be a JSON object."
    assert payload["stderr"] == payload["error"]
    assert payload["result"] == {}


def test_cli_main_rejects_oversized_hook_input_before_execution(tmp_path):
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text('{"padding":"xxxxxxxx"}', encoding="utf-8")

    with patch.object(
        sys,
        "argv",
        [
            "spark_hook",
            "voice.status",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    ), patch("voice_comms_chip.spark_hook.MAX_HOOK_INPUT_BYTES", 8), patch(
        "voice_comms_chip.spark_hook.handle_voice_status_hook",
        side_effect=AssertionError("oversized input should not execute hook logic"),
    ):
        exit_code = main()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["returncode"] == 1
    assert payload["error_code"] == "voice_hook_input_too_large"
    assert payload["error"] == "Voice hook input is too large."
    assert payload["result"] == {}


def test_cli_main_exports_sanitized_runtime_state(tmp_path):
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    runtime_state_path = tmp_path / "voice-runtime-state.json"
    input_path.write_text('{"surface":"attachments_cli"}', encoding="utf-8")

    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True), patch.object(
        sys,
        "argv",
        [
            "spark_hook",
            "voice.status",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    ), patch.dict(
        "os.environ",
        {"SPARK_VOICE_RUNTIME_STATE_PATH": str(runtime_state_path)},
        clear=False,
    ):
        exit_code = main()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    exported = json.loads(runtime_state_path.read_text(encoding="utf-8"))
    encoded = json.dumps(exported)
    assert exit_code == 0
    assert payload["result"]["runtime_state"]["schema_version"] == "spark.voice_runtime_state.v1"
    assert exported["schema_version"] == "spark.voice_runtime_state.v1"
    assert exported["stt"]["ready"] is True
    assert exported["telegram_delivery"]["ready"] is False
    assert "transcript_text" not in encoded
    assert "audio_base64" not in encoded
    assert FAKE_OPENAI_KEY not in encoded


def test_join_url_accepts_http_urls_and_trims_edges():
    assert _join_url(" https://voice.example.test/api/ ", " /v1/speak ") == "https://voice.example.test/api/v1/speak"


def test_join_url_rejects_non_http_provider_urls_without_echoing_value():
    unsafe = "file:///tmp/private-token-path"

    with pytest.raises(ValueError) as exc_info:
        _join_url(unsafe, "voices")

    message = str(exc_info.value)
    assert "http or https" in message
    assert unsafe not in message
    assert "private-token-path" not in message


@pytest.mark.parametrize("base_url", ["", "example.test/api", "mailto:voice@example.test", "https:///missing-host"])
def test_join_url_requires_http_url_with_host(base_url):
    with pytest.raises(ValueError, match="http or https URL with a host|non-empty string"):
        _join_url(base_url, "voices")


def test_voice_transcribe_posts_openai_compatible_multipart_request(tmp_path):
    captured = {}
    payload = _payload(
        tmp_path,
        audio_base64=base64.b64encode(b"fake-ogg-bytes").decode("ascii"),
        filename="telegram-voice.ogg",
        mime_type="audio/ogg",
    )
    Path(payload["builder_env_file_path"]).write_text(
        f"OPENAI_API_KEY={FAKE_OPENAI_KEY}\nVOICE_TRANSCRIBE_PROVIDER=openai\n",
        encoding="utf-8",
    )

    def fake_urlopen(request, timeout: int = 30):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = request.data
        return _FakeBinaryHttpResponse(json.dumps({"text": "/voice plan"}).encode("utf-8"))

    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=False), patch(
        "voice_comms_chip.spark_hook.urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        result = handle_voice_transcribe_hook(payload)

    headers = {str(key).lower(): value for key, value in captured["headers"].items()}
    assert result["returncode"] == 0
    assert result["result"]["transcript_text"] == "/voice plan"
    assert result["result"]["mode"] == "provider"
    assert captured["url"] == "https://api.openai.com/v1/audio/transcriptions"
    assert headers["authorization"] == f"Bearer {FAKE_OPENAI_KEY}"
    assert "multipart/form-data; boundary=" in headers["content-type"]
    assert b'filename="telegram-voice.ogg"' in captured["body"]
    assert b"fake-ogg-bytes" in captured["body"]


def test_voice_transcribe_auto_requires_local_faster_whisper_when_local_is_unavailable(tmp_path):
    payload = _payload(
        tmp_path,
        audio_base64=base64.b64encode(b"fake-ogg-bytes").decode("ascii"),
        filename="telegram-voice.ogg",
        mime_type="audio/ogg",
    )
    Path(payload["builder_env_file_path"]).write_text(
        "\n".join(
            [
                f"OPENAI_API_KEY={FAKE_OPENAI_KEY}",
                "VOICE_TRANSCRIBE_PROVIDER=auto",
                "VOICE_TRANSCRIBE_SECRET_ENV_REF=OPENAI_API_KEY",
                "VOICE_TRANSCRIBE_BASE_URL=https://api.openai.com/v1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=False), patch(
        "voice_comms_chip.spark_hook.urllib.request.urlopen",
        side_effect=AssertionError("hosted transcription should require explicit provider opt-in"),
    ):
        with pytest.raises(ValueError, match="Local faster-whisper transcription is the default"):
            handle_voice_transcribe_hook(payload)


def test_voice_transcribe_rejects_malformed_audio_base64_before_provider_checks(tmp_path):
    raw_payload = "!!!!/tmp/private-audio.ogg/sk-live-secret"
    payload = _payload(
        tmp_path,
        audio_base64=raw_payload,
        filename="telegram-voice.ogg",
        mime_type="audio/ogg",
    )

    with patch(
        "voice_comms_chip.spark_hook._local_faster_whisper_available",
        side_effect=AssertionError("audio validation should run before provider readiness checks"),
    ):
        with pytest.raises(ValueError, match="audio_base64 must be valid base64"):
            handle_voice_transcribe_hook(payload)


def test_cli_main_returns_bounded_error_for_malformed_audio_base64(tmp_path):
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    raw_payload = "!!!!/tmp/private-audio.ogg/sk-live-secret"
    input_path.write_text(
        json.dumps(
            _authorized_voice_payload(
                "voice.transcribe",
                {"audio_base64": raw_payload, "filename": "telegram-voice.ogg", "mime_type": "audio/ogg"},
            )
        ),
        encoding="utf-8",
    )

    with patch.object(
        sys,
        "argv",
        [
            "spark_hook",
            "voice.transcribe",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    ), patch(
        "voice_comms_chip.spark_hook._local_faster_whisper_available",
        side_effect=AssertionError("audio validation should run before provider readiness checks"),
    ):
        exit_code = main()

    result = json.loads(output_path.read_text(encoding="utf-8"))
    encoded = json.dumps(result)
    assert exit_code == 1
    assert result["returncode"] == 1
    assert result["error_code"] == "voice_transcribe_audio_invalid_base64"
    assert result["error"] == "voice.transcribe audio_base64 must be valid base64 audio bytes."
    assert result["stderr"] == result["error"]
    assert result["stdout"] == ""
    assert result["result"] == {}
    assert raw_payload not in encoded
    assert "/tmp/private-audio.ogg" not in encoded
    assert "sk-live-secret" not in encoded


def test_voice_transcribe_rejects_oversized_audio_before_provider_checks(tmp_path):
    payload = _payload(
        tmp_path,
        audio_base64=base64.b64encode(b"fake-ogg-bytes").decode("ascii"),
        filename="telegram-voice.ogg",
        mime_type="audio/ogg",
    )

    with patch("voice_comms_chip.spark_hook.MAX_TRANSCRIBE_AUDIO_BYTES", 4), patch(
        "voice_comms_chip.spark_hook._local_faster_whisper_available",
        side_effect=AssertionError("audio validation should run before provider readiness checks"),
    ):
        with pytest.raises(ValueError, match="too large"):
            handle_voice_transcribe_hook(payload)


def test_cli_main_returns_bounded_error_for_oversized_audio(tmp_path):
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    audio_base64 = base64.b64encode(b"fake-ogg-bytes").decode("ascii")
    input_path.write_text(
        json.dumps(
            _authorized_voice_payload(
                "voice.transcribe",
                {"audio_base64": audio_base64, "filename": "telegram-voice.ogg", "mime_type": "audio/ogg"},
            )
        ),
        encoding="utf-8",
    )

    with patch.object(
        sys,
        "argv",
        [
            "spark_hook",
            "voice.transcribe",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    ), patch("voice_comms_chip.spark_hook.MAX_TRANSCRIBE_AUDIO_BYTES", 4), patch(
        "voice_comms_chip.spark_hook._local_faster_whisper_available",
        side_effect=AssertionError("audio validation should run before provider readiness checks"),
    ):
        exit_code = main()

    result = json.loads(output_path.read_text(encoding="utf-8"))
    encoded = json.dumps(result)
    assert exit_code == 1
    assert result["returncode"] == 1
    assert result["error_code"] == "voice_transcribe_audio_too_large"
    assert result["error"] == "voice.transcribe audio_base64 is too large."
    assert result["stderr"] == result["error"]
    assert result["stdout"] == ""
    assert result["result"] == {}
    assert audio_base64 not in encoded



def test_voice_transcribe_prefers_local_faster_whisper_without_openai_call_when_available(tmp_path):
    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True), patch(
        "voice_comms_chip.spark_hook._transcribe_with_local_faster_whisper",
        return_value="Local first transcript",
    ), patch(
        "voice_comms_chip.spark_hook.urllib.request.urlopen",
        side_effect=AssertionError("hosted transcription should not be called"),
    ):
        result = handle_voice_transcribe_hook(
            _payload(
                tmp_path,
                audio_base64=base64.b64encode(b"fake-ogg-bytes").decode("ascii"),
                filename="telegram-voice.ogg",
                mime_type="audio/ogg",
            )
        )

    assert result["returncode"] == 0
    assert result["result"]["mode"] == "local_faster_whisper"
    assert result["result"]["provider_id"] == "local_faster_whisper"
    assert result["result"]["transcript_text"] == "Local first transcript"
    assert result["metrics"]["local_first"] == 1


def test_voice_transcribe_can_return_deterministic_fallback_when_requested(tmp_path):
    payload = _payload(
        tmp_path,
        audio_base64=base64.b64encode(b"fake-ogg-bytes").decode("ascii"),
        filename="telegram-voice.ogg",
        mime_type="audio/ogg",
        fallback_mode="deterministic",
    )
    Path(payload["builder_env_file_path"]).write_text(
        f"OPENAI_API_KEY={FAKE_OPENAI_KEY}\nVOICE_TRANSCRIBE_PROVIDER=openai\n",
        encoding="utf-8",
    )
    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=False), patch(
        "voice_comms_chip.spark_hook.urllib.request.urlopen",
        side_effect=RuntimeError("simulated provider outage"),
    ):
        result = handle_voice_transcribe_hook(payload)

    assert result["returncode"] == 0
    assert result["result"]["mode"] == "deterministic_fallback"
    assert "Deterministic fallback transcript" in result["result"]["transcript_text"]
    assert "simulated provider outage" in result["result"]["fallback_reason"]


def test_voice_transcribe_can_fallback_to_local_faster_whisper_when_provider_fails(tmp_path):
    payload = _payload(
        tmp_path,
        audio_base64=base64.b64encode(b"fake-ogg-bytes").decode("ascii"),
        filename="telegram-voice.ogg",
        mime_type="audio/ogg",
    )
    Path(payload["builder_env_file_path"]).write_text(
        f"OPENAI_API_KEY={FAKE_OPENAI_KEY}\nVOICE_TRANSCRIBE_PROVIDER=openai\n",
        encoding="utf-8",
    )
    with patch(
        "voice_comms_chip.spark_hook.urllib.request.urlopen",
        side_effect=RuntimeError("simulated provider outage"),
    ), patch(
        "voice_comms_chip.spark_hook._local_faster_whisper_available",
        return_value=True,
    ), patch(
        "voice_comms_chip.spark_hook._transcribe_with_local_faster_whisper",
        return_value="Local fallback transcript",
    ):
        result = handle_voice_transcribe_hook(
            payload
        )

    assert result["returncode"] == 0
    assert result["result"]["mode"] == "local_faster_whisper"
    assert result["result"]["provider_id"] == "local_faster_whisper"
    assert result["result"]["transcript_text"] == "Local fallback transcript"
    assert "simulated provider outage" in result["result"]["fallback_reason"]


def test_local_faster_whisper_uses_configured_quality_settings(tmp_path):
    payload = _payload(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"OPENAI_API_KEY={FAKE_OPENAI_KEY}",
                "VOICE_TRANSCRIBE_LOCAL_MODEL=base.en",
                "VOICE_TRANSCRIBE_LOCAL_LANGUAGE=en",
                "VOICE_TRANSCRIBE_LOCAL_VAD_FILTER=true",
                "VOICE_TRANSCRIBE_LOCAL_BEAM_SIZE=7",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    payload["builder_env_file_path"] = str(env_file)
    captured: dict[str, object] = {}

    class FakeWhisperModel:
        def __init__(self, model_name: str, *, device: str, compute_type: str) -> None:
            captured["model_name"] = model_name
            captured["device"] = device
            captured["compute_type"] = compute_type

        def transcribe(self, temp_path: str, **kwargs):
            captured["temp_path"] = temp_path
            captured["kwargs"] = kwargs
            return [SimpleNamespace(text="hello there")], {"language": "en"}

    with patch.dict(sys.modules, {"faster_whisper": SimpleNamespace(WhisperModel=FakeWhisperModel)}):
        from voice_comms_chip import spark_hook as spark_hook_module

        transcript = spark_hook_module._transcribe_with_local_faster_whisper(
            payload=payload,
            audio_bytes=b"fake-audio-bytes",
            filename="telegram-voice.ogg",
        )

    assert transcript == "hello there"
    assert captured["model_name"] == "base.en"
    assert captured["device"] == "cpu"
    assert captured["compute_type"] == "int8"
    assert captured["kwargs"] == {
        "beam_size": 7,
        "condition_on_previous_text": False,
        "vad_filter": True,
        "language": "en",
    }


def test_voice_transcribe_prefers_dedicated_openai_transcription_env_over_custom_provider(tmp_path):
    captured = {}
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"OPENAI_API_KEY={FAKE_OPENAI_KEY}",
                "VOICE_TRANSCRIBE_PROVIDER=openai",
                "VOICE_TRANSCRIBE_SECRET_ENV_REF=OPENAI_API_KEY",
                "VOICE_TRANSCRIBE_BASE_URL=https://api.openai.com/v1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_urlopen(request, timeout: int = 30):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        return _FakeBinaryHttpResponse(json.dumps({"text": "Voice via dedicated provider"}).encode("utf-8"))

    with patch("voice_comms_chip.spark_hook.urllib.request.urlopen", side_effect=fake_urlopen):
        result = handle_voice_transcribe_hook(
            _authorized_voice_payload("voice.transcribe", {
                "builder_env_file_path": str(env_file),
                "provider": {
                    "provider_id": "custom",
                    "provider_kind": "custom",
                    "auth_method": "api_key_env",
                    "execution_transport": "direct_http",
                    "base_url": "https://api.example.com/v1",
                    "secret_env_ref": "CUSTOM_API_KEY",
                },
                "audio_base64": base64.b64encode(b"fake-ogg-bytes").decode("ascii"),
                "filename": "telegram-voice.ogg",
                "mime_type": "audio/ogg",
            })
        )

    headers = {str(key).lower(): value for key, value in captured["headers"].items()}
    assert result["returncode"] == 0
    assert result["result"]["transcript_text"] == "Voice via dedicated provider"
    assert result["metrics"]["transcribe_ms"] >= 0
    assert result["result"]["runtime_state"]["stt"]["provider_id"] == "openai"
    assert result["result"]["runtime_state"]["latency"]["transcribe_ms"] >= 0
    assert result["result"]["runtime_state"]["transcript"]["audio_bytes"] == len(b"fake-ogg-bytes")
    assert result["result"]["runtime_state"]["claim_levels"]["delivery_ready"] is False
    assert captured["url"] == "https://api.openai.com/v1/audio/transcriptions"
    assert headers["authorization"] == f"Bearer {FAKE_OPENAI_KEY}"


def test_voice_speak_uses_profile_default_elevenlabs_voice(tmp_path):
    captured = {}

    def fake_urlopen(request, timeout: int = 30):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeBinaryHttpResponse(b"fake-mpeg-bytes")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"ELEVENLABS_API_KEY={FAKE_ELEVENLABS_KEY}",
                f"VOICE_TTS_ELEVENLABS_VOICE_ID={FAKE_ELEVENLABS_VOICE_ID}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with patch("voice_comms_chip.spark_hook.urllib.request.urlopen", side_effect=fake_urlopen):
        result = handle_voice_speak_hook(
            _authorized_voice_payload("voice.speak", {
                "builder_env_file_path": str(env_file),
                "text": "Operator status update.",
            })
        )

    headers = {str(key).lower(): value for key, value in captured["headers"].items()}
    assert result["returncode"] == 0
    assert result["result"]["provider_id"] == "elevenlabs"
    assert result["result"]["voice_id"] == FAKE_ELEVENLABS_VOICE_ID
    assert result["result"]["model_id"] == "eleven_turbo_v2_5"
    assert base64.b64decode(result["result"]["audio_base64"].encode("ascii")) == b"fake-mpeg-bytes"
    assert result["result"]["delivery_trace"]["synthesis_status"] == "success"
    assert result["result"]["delivery_trace"]["telegram_delivery_status"] == "unknown"
    assert result["result"]["delivery_trace"]["failure_stage"] == "not_attempted_by_chip"
    assert result["result"]["delivery_trace"]["voice_id_masked"] == "fake...e-id"
    assert result["result"]["coherence"]["mode"] == "exact"
    assert result["result"]["coherence"]["spoken_text_characters"] == len("Operator status update.")
    assert result["result"]["runtime_state"]["claim_levels"]["synthesis_ready"] is True
    assert result["result"]["runtime_state"]["claim_levels"]["delivery_ready"] is False
    assert headers["xi-api-key"] == FAKE_ELEVENLABS_KEY
    assert headers["accept"] == "audio/mpeg"
    assert captured["url"].startswith(f"https://api.elevenlabs.io/v1/text-to-speech/{FAKE_ELEVENLABS_VOICE_ID}")
    assert captured["body"]["text"] == "Operator status update."


def test_voice_speak_uses_telegram_compatible_opus_for_telegram_surface(tmp_path):
    captured = {}

    def fake_urlopen(request, timeout: int = 30):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeBinaryHttpResponse(b"fake-opus-bytes")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"ELEVENLABS_API_KEY={FAKE_ELEVENLABS_KEY}",
                f"VOICE_TTS_ELEVENLABS_VOICE_ID={FAKE_ELEVENLABS_VOICE_ID}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with patch("voice_comms_chip.spark_hook.urllib.request.urlopen", side_effect=fake_urlopen):
        result = handle_voice_speak_hook(
            _authorized_voice_payload("voice.speak", {
                "builder_env_file_path": str(env_file),
                "surface": "telegram",
                "text": "Telegram voice note reply.",
                "caption_text": "Telegram voice note reply.",
                "telegram_delivery": {
                    "status": "success",
                    "telegram_message_id": 12345,
                },
            })
        )

    headers = {str(key).lower(): value for key, value in captured["headers"].items()}
    assert result["returncode"] == 0
    assert result["result"]["mime_type"] == "audio/ogg"
    assert result["result"]["voice_compatible"] is True
    assert str(result["result"]["filename"]).endswith(".ogg")
    assert base64.b64decode(result["result"]["audio_base64"].encode("ascii")) == b"fake-opus-bytes"
    assert result["result"]["delivery_trace"]["telegram_delivery_status"] == "success"
    assert result["result"]["delivery_trace"]["telegram_delivery_ready"] is True
    assert result["result"]["delivery_trace"]["failure_stage"] == ""
    assert result["result"]["coherence"]["caption_matches_spoken"] is True
    assert result["result"]["runtime_state"]["telegram_delivery"]["telegram_message_id_present"] is True
    assert result["result"]["runtime_state"]["claim_levels"]["delivery_ready"] is True
    assert headers["accept"] == "audio/mpeg"
    assert "output_format=opus_48000_64" in captured["url"]
    assert captured["body"]["text"] == "Telegram voice note reply."


def test_voice_speak_coherence_fails_on_exact_caption_mismatch():
    result = _build_speak_coherence(
        request={"text": "Approved spoken answer."},
        payload={"caption_text": "Different caption.", "coherence_mode": "exact"},
    )

    assert result["check"] == "failed"
    assert result["caption_matches_spoken"] is False


def test_write_output_replaces_temp_file(tmp_path):
    output_path = tmp_path / "voice-output.json"

    _write_output(output_path, {"ok": True})

    assert output_path.read_text(encoding="utf-8") == '{\n  "ok": true\n}'
    assert not (tmp_path / "voice-output.json.tmp").exists()


def test_voice_speak_supports_local_pyttsx3_tts(tmp_path):
    captured: dict[str, object] = {}

    class FakeEngine:
        def setProperty(self, name: str, value: object) -> None:
            captured.setdefault("properties", {})[name] = value

        def getProperty(self, name: str):
            if name == "voices":
                return [SimpleNamespace(name="Test Voice", id="test-voice-id")]
            return None

        def save_to_file(self, text: str, path: str) -> None:
            captured["text"] = text
            captured["path"] = path

        def runAndWait(self) -> None:
            Path(str(captured["path"])).write_bytes(b"fake-local-wav")

    with patch.dict(sys.modules, {"pyttsx3": SimpleNamespace(init=lambda: FakeEngine())}):
        result = handle_voice_speak_hook(
            _authorized_voice_payload("voice.speak", {
                "text": "Local free voice.",
                "tts": {
                    "provider_id": "pyttsx3",
                    "voice_name": "test",
                    "rate": 175,
                    "volume": 0.8,
                },
            })
        )

    assert result["returncode"] == 0
    assert result["result"]["provider_id"] == "pyttsx3"
    assert result["result"]["mime_type"] == "audio/wav"
    assert result["result"]["voice_compatible"] is False
    assert base64.b64decode(result["result"]["audio_base64"].encode("ascii")) == b"fake-local-wav"
    assert captured["properties"] == {"rate": 175, "volume": 0.8, "voice": "test-voice-id"}
    assert captured["text"] == "Local free voice."


def test_voice_speak_supports_local_kokoro_tts(tmp_path):
    captured: dict[str, object] = {}
    model_path = tmp_path / "kokoro-v1.0.onnx"
    voices_path = tmp_path / "voices-v1.0.bin"
    model_path.write_bytes(b"fake-model")
    voices_path.write_bytes(b"fake-voices")

    class FakeKokoro:
        def __init__(self, model_path_arg: str, voices_path_arg: str) -> None:
            captured["model_path"] = model_path_arg
            captured["voices_path"] = voices_path_arg

        def create(self, text: str, *, voice: str, speed: float, lang: str):
            captured["create"] = {"text": text, "voice": voice, "speed": speed, "lang": lang}
            return [0.0, 0.1, -0.1], 24000

    def fake_write(buffer, samples, sample_rate: int, *, format: str) -> None:
        captured["write"] = {"samples": samples, "sample_rate": sample_rate, "format": format}
        buffer.write(b"fake-kokoro-wav")

    with patch.dict(
        sys.modules,
        {
            "kokoro_onnx": SimpleNamespace(Kokoro=FakeKokoro),
            "soundfile": SimpleNamespace(write=fake_write),
        },
    ):
        result = handle_voice_speak_hook(
            _authorized_voice_payload("voice.speak", {
                "text": "Kokoro local voice.",
                "tts": {
                    "provider_id": "kokoro",
                    "model_path": "kokoro-v1.0.onnx",
                    "voices_path": "voices-v1.0.bin",
                    "voice": "af_sarah",
                    "speed": 1.1,
                    "lang": "en-us",
                },
            })
        )

    assert result["returncode"] == 0
    assert result["result"]["provider_id"] == "kokoro"
    assert result["result"]["mime_type"] == "audio/wav"
    assert result["result"]["voice_compatible"] is False
    assert base64.b64decode(result["result"]["audio_base64"].encode("ascii")) == b"fake-kokoro-wav"
    assert "kokoro-v1.0" in captured["model_path"]
    assert "voices-v1.0" in captured["voices_path"]
    assert captured["create"] == {"text": "Kokoro local voice.", "voice": "af_sarah", "speed": 1.1, "lang": "en-us"}
    assert captured["write"] == {"samples": [0.0, 0.1, -0.1], "sample_rate": 24000, "format": "WAV"}


def test_voice_speak_uses_env_default_tts_provider_for_kokoro(tmp_path):
    captured: dict[str, object] = {}
    model_path = tmp_path / "kokoro-v1.0.int8.onnx"
    voices_path = tmp_path / "voices-v1.0.bin"
    model_path.write_bytes(b"fake-model")
    voices_path.write_bytes(b"fake-voices")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "VOICE_TTS_PROVIDER=kokoro",
                f"VOICE_TTS_KOKORO_MODEL_PATH={model_path}",
                f"VOICE_TTS_KOKORO_VOICES_PATH={voices_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    class FakeKokoro:
        def __init__(self, model_path_arg: str, voices_path_arg: str) -> None:
            captured["model_path"] = model_path_arg
            captured["voices_path"] = voices_path_arg

        def create(self, text: str, *, voice: str, speed: float, lang: str):
            captured["create"] = {"text": text, "voice": voice, "speed": speed, "lang": lang}
            return [0.0], 24000

    with patch.dict(
        sys.modules,
        {
            "kokoro_onnx": SimpleNamespace(Kokoro=FakeKokoro),
            "soundfile": SimpleNamespace(write=lambda buffer, samples, sample_rate, *, format: buffer.write(b"env-kokoro-wav")),
        },
    ):
        result = handle_voice_speak_hook(
            _authorized_voice_payload("voice.speak", {
                "builder_env_file_path": str(env_file),
                "text": "Env Kokoro voice.",
            })
        )

    assert result["returncode"] == 0
    assert result["result"]["provider_id"] == "kokoro"
    assert base64.b64decode(result["result"]["audio_base64"].encode("ascii")) == b"env-kokoro-wav"
    assert "kokoro-v1.0" in captured["model_path"]
    assert "voices-v1.0" in captured["voices_path"]


def test_voice_speak_supports_openai_gpt_realtime_2(tmp_path):
    sent_messages: list[dict[str, object]] = []
    pcm_delta = base64.b64encode(b"\x00\x00\x01\x00").decode("ascii")

    class FakeRealtimeSocket:
        def __init__(self) -> None:
            self._events = iter(
                [
                    json.dumps({"type": "session.created"}),
                    json.dumps({"type": "response.output_audio.delta", "delta": pcm_delta}),
                    json.dumps({"type": "response.done"}),
                ]
            )

        def send(self, message: str) -> None:
            sent_messages.append(json.loads(message))

        def recv(self) -> str:
            return next(self._events)

        def close(self) -> None:
            return None

    captured: dict[str, object] = {}

    def fake_create_connection(url: str, *, header: list[str], timeout: float, **kwargs):
        captured["url"] = url
        captured["header"] = header
        captured["timeout"] = timeout
        captured["max_size"] = kwargs.get("max_size")
        return FakeRealtimeSocket()

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"OPENAI_API_KEY={FAKE_OPENAI_KEY}",
                "VOICE_TTS_PROVIDER=openai-realtime",
                "VOICE_TTS_OPENAI_REALTIME_MODEL_ID=gpt-realtime-2",
                "VOICE_TTS_OPENAI_REALTIME_VOICE=coral",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with patch.dict(
        sys.modules,
        {"websocket": SimpleNamespace(create_connection=fake_create_connection)},
    ):
        result = handle_voice_speak_hook(
            _authorized_voice_payload("voice.speak", {
                "builder_env_file_path": str(env_file),
                "surface": "telegram",
                "text": "Use the new realtime voice.",
            })
        )

    audio_bytes = base64.b64decode(result["result"]["audio_base64"].encode("ascii"))
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
        assert wav_file.getframerate() == 24000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.readframes(2) == b"\x00\x00\x01\x00"
    assert result["returncode"] == 0
    assert result["result"]["provider_id"] == "openai-realtime"
    assert result["result"]["model_id"] == "gpt-realtime-2"
    assert result["result"]["voice_id"] == "coral"
    assert result["result"]["mime_type"] == "audio/wav"
    assert result["result"]["voice_compatible"] is False
    assert captured["url"] == "wss://api.openai.com/v1/realtime?model=gpt-realtime-2"
    assert "Authorization: Bearer " + FAKE_OPENAI_KEY in captured["header"]
    assert sent_messages[0]["type"] == "session.update"
    assert "verbatim" in sent_messages[0]["session"]["instructions"]
    assert sent_messages[1]["type"] == "response.create"
    assert sent_messages[1]["response"]["instructions"] == sent_messages[0]["session"]["instructions"]
    assert sent_messages[1]["response"]["input"][0]["content"][0]["text"] == "Use the new realtime voice."


def test_voice_speak_reports_malformed_openai_realtime_websocket_message(tmp_path):
    sent_messages: list[dict[str, object]] = []
    raw_payload = '{"type":"response.output_audio.delta","delta":"secret-token'

    class FakeRealtimeSocket:
        def send(self, message: str) -> None:
            sent_messages.append(json.loads(message))

        def recv(self) -> str:
            return raw_payload

        def close(self) -> None:
            return None

    def fake_create_connection(url: str, *, header: list[str], timeout: float, **kwargs):
        return FakeRealtimeSocket()

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"OPENAI_API_KEY={FAKE_OPENAI_KEY}",
                "VOICE_TTS_PROVIDER=openai-realtime",
                "VOICE_TTS_OPENAI_REALTIME_MODEL_ID=gpt-realtime-2",
                "VOICE_TTS_OPENAI_REALTIME_VOICE=coral",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with patch.dict(
        sys.modules,
        {"websocket": SimpleNamespace(create_connection=fake_create_connection)},
    ):
        with pytest.raises(RuntimeError) as exc_info:
            handle_voice_speak_hook(
                _authorized_voice_payload("voice.speak", {
                    "builder_env_file_path": str(env_file),
                    "surface": "telegram",
                    "text": "Use the new realtime voice.",
                })
            )

    message = str(exc_info.value)
    assert "OpenAI Realtime TTS received malformed websocket message" in message
    assert "secret-token" not in message
    assert sent_messages[0]["type"] == "session.update"
    assert sent_messages[1]["type"] == "response.create"


def test_voice_speak_retries_with_fallback_voice_when_primary_voice_is_missing(tmp_path):
    calls: list[str] = []

    def fake_urlopen(request, timeout: int = 30):
        calls.append(request.full_url)
        if f"/text-to-speech/{FAKE_ELEVENLABS_VOICE_ID}" in request.full_url:
            raise urllib.error.HTTPError(
                request.full_url,
                404,
                "not found",
                hdrs=None,
                fp=io.BytesIO(b'{"detail":"voice_not_found"}'),
            )
        if request.full_url.endswith("/voices"):
            return _FakeBinaryHttpResponse(
                json.dumps(
                    {
                        "voices": [
                            {"voice_id": "fallback-voice-id", "name": "Elise - Warm, Natural and Engaging"},
                            {"voice_id": "other-voice-id", "name": "Other"},
                        ]
                    }
                ).encode("utf-8")
            )
        if "/text-to-speech/fallback-voice-id" in request.full_url:
            return _FakeBinaryHttpResponse(b"fallback-mpeg-bytes")
        raise AssertionError(f"Unexpected request URL: {request.full_url}")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"ELEVENLABS_API_KEY={FAKE_ELEVENLABS_KEY}",
                f"VOICE_TTS_ELEVENLABS_VOICE_ID={FAKE_ELEVENLABS_VOICE_ID}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with patch("voice_comms_chip.spark_hook.urllib.request.urlopen", side_effect=fake_urlopen):
        result = handle_voice_speak_hook(
            _authorized_voice_payload("voice.speak", {
                "builder_env_file_path": str(env_file),
                "text": "Retry the fallback voice.",
            })
        )

    assert result["returncode"] == 0
    assert result["result"]["voice_id"] == "fallback-voice-id"
    assert base64.b64decode(result["result"]["audio_base64"].encode("ascii")) == b"fallback-mpeg-bytes"
    assert any(url.endswith("/voices") for url in calls)


# --- HTTP response size limit tests ---

from voice_comms_chip.spark_hook import (
    _read_response_bounded,
    MAX_PROVIDER_AUDIO_RESPONSE_BYTES,
    MAX_PROVIDER_JSON_RESPONSE_BYTES,
    MAX_PROVIDER_ERROR_RESPONSE_BYTES,
)


class _FakeResponseWithLimit:
    """Fake response that produces data up to max_chunks before empty."""

    def __init__(self, chunk: bytes, total_chunks: int) -> None:
        self._chunk = chunk
        self._remaining = total_chunks

    def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        if size < 0:
            data = self._chunk * self._remaining
            self._remaining = 0
            return data
        chunk = self._chunk[:size]
        self._remaining -= 1
        return chunk


def test_read_response_bounded_normal():
    """Normal response under the limit is read completely."""
    data = b"hello world"
    resp = _FakeResponseWithLimit(data, total_chunks=1)
    result = _read_response_bounded(resp, max_bytes=1024)
    assert result == data


def test_read_response_bounded_exact_limit():
    """Response exactly at the limit is read completely."""
    data = b"x" * 1024
    resp = _FakeResponseWithLimit(b"x", total_chunks=1024)
    result = _read_response_bounded(resp, max_bytes=1024)
    assert result == data


def test_read_response_bounded_exceeds_limit():
    """Response exceeding the limit raises RuntimeError."""
    resp = _FakeResponseWithLimit(b"x" * 65536, total_chunks=1000)
    try:
        _read_response_bounded(resp, max_bytes=1024)
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "exceeded maximum allowed size" in str(exc)


def test_read_response_bounded_zero_length():
    """Empty response returns empty bytes."""
    resp = _FakeResponseWithLimit(b"", total_chunks=0)
    result = _read_response_bounded(resp, max_bytes=1024)
    assert result == b""


def test_constants_are_reasonable():
    """Verify the size limit constants are sane."""
    assert MAX_PROVIDER_AUDIO_RESPONSE_BYTES == 50 * 1024 * 1024
    assert MAX_PROVIDER_JSON_RESPONSE_BYTES == 1 * 1024 * 1024
    assert MAX_PROVIDER_ERROR_RESPONSE_BYTES == 64 * 1024
