from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from voice_comms_chip.spark_hook import (
    _synthesize_with_kokoro,
    _synthesize_with_openai_realtime,
    _synthesize_with_pyttsx3,
    handle_voice_speak_hook,
    handle_voice_status_hook,
)


def _voice_governor_decision(hook: str) -> dict[str, object]:
    action_id = f"action:{hook}"
    authorization = {
        "schema_version": "authorization-decision-v1",
        "decision_id": f"auth:{hook}",
        "verdict": "allow",
        "action_id": action_id,
        "capability_id": hook,
        "turn_id": "turn:voice-test",
    }
    return {
        "schema_version": "governor-decision-v1",
        "decision_id": "governor:voice-test",
        "turn_id": "turn:voice-test",
        "outcome": "execute",
        "envelope": {
            "schema_version": "turn-intent-envelope-vnext",
            "turn_id": "turn:voice-test",
            "proposed_actions": [
                {
                    "action_id": action_id,
                    "capability_id": hook,
                    "tool_name": hook,
                    "action_type": "local_install_or_network_voice",
                }
            ],
        },
        "authorizations": [authorization],
        "tool_ledgers": [
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
        ],
    }


def test_voice_status_local_branch_surfaces_resolve_provider_programmer_error(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=fake-openai-key-for-tests\n", encoding="utf-8")

    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True), patch(
        "voice_comms_chip.spark_hook._resolve_provider",
        side_effect=AttributeError("simulated provider resolver bug"),
    ):
        with pytest.raises(AttributeError, match="simulated provider resolver bug"):
            handle_voice_status_hook({"builder_env_file_path": str(env_file), "governor_decision": _voice_governor_decision("voice.status")})


def test_voice_status_local_branch_keeps_value_error_as_provider_note(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=fake-openai-key-for-tests\n", encoding="utf-8")

    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True), patch(
        "voice_comms_chip.spark_hook._resolve_provider",
        side_effect=ValueError("Active provider has no base URL configured."),
    ):
        result = handle_voice_status_hook({"builder_env_file_path": str(env_file), "governor_decision": _voice_governor_decision("voice.status")})

    assert result["returncode"] == 0
    assert "no base URL configured" in result["result"]["provider_note"]


def test_voice_status_hosted_branch_surfaces_resolve_provider_programmer_error(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=fake-openai-key-for-tests",
                "VOICE_TRANSCRIBE_PROVIDER=openai",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=False), patch(
        "voice_comms_chip.spark_hook._resolve_provider",
        side_effect=AttributeError("simulated hosted provider resolver bug"),
    ):
        with pytest.raises(AttributeError, match="simulated hosted provider resolver bug"):
            handle_voice_status_hook({"builder_env_file_path": str(env_file), "governor_decision": _voice_governor_decision("voice.status")})


def test_voice_speak_rejects_unexpected_resolved_provider_without_elevenlabs_fallback() -> None:
    with patch("voice_comms_chip.spark_hook._resolve_tts_request", return_value={"provider_id": "surprise"}), patch(
        "voice_comms_chip.spark_hook._synthesize_with_elevenlabs",
        side_effect=AssertionError("unexpected provider must not fall back to ElevenLabs"),
    ):
        with pytest.raises(RuntimeError, match="internal routing bug"):
            handle_voice_speak_hook({"text": "hello", "governor_decision": _voice_governor_decision("voice.speak")})


def test_synthesize_with_pyttsx3_wraps_import_error_as_install_hint() -> None:
    with patch("voice_comms_chip.spark_hook.importlib.import_module", side_effect=ImportError("missing pyttsx3")):
        with pytest.raises(RuntimeError, match="optional package `pyttsx3`"):
            _synthesize_with_pyttsx3(request={"text": "hello"})


def test_synthesize_with_pyttsx3_surfaces_non_import_error() -> None:
    with patch(
        "voice_comms_chip.spark_hook.importlib.import_module",
        side_effect=RuntimeError("simulated pyttsx3 import hook fault"),
    ):
        with pytest.raises(RuntimeError, match="simulated pyttsx3 import hook fault"):
            _synthesize_with_pyttsx3(request={"text": "hello"})


def test_synthesize_with_kokoro_surfaces_non_import_error() -> None:
    with patch(
        "voice_comms_chip.spark_hook.importlib.import_module",
        side_effect=RuntimeError("simulated kokoro import hook fault"),
    ):
        with pytest.raises(RuntimeError, match="simulated kokoro import hook fault"):
            _synthesize_with_kokoro(request={"text": "hello"})


def test_synthesize_with_openai_realtime_surfaces_non_import_error() -> None:
    with patch(
        "voice_comms_chip.spark_hook.importlib.import_module",
        side_effect=RuntimeError("simulated websocket import hook fault"),
    ):
        with pytest.raises(RuntimeError, match="simulated websocket import hook fault"):
            _synthesize_with_openai_realtime(
                request={
                    "base_url": "wss://api.openai.com/v1/realtime",
                    "model_id": "gpt-realtime-2",
                    "secret_value": "fake-openai-key-for-tests",
                    "text": "hello",
                }
            )


def test_synthesize_with_kokoro_rejects_empty_paths_before_model_construction() -> None:
    class FakeKokoro:
        def __init__(self, model_path: str, voices_path: str) -> None:
            raise AssertionError("empty paths should be rejected before Kokoro construction")

    with patch.dict(
        sys.modules,
        {
            "kokoro_onnx": SimpleNamespace(Kokoro=FakeKokoro),
            "soundfile": SimpleNamespace(write=lambda *args, **kwargs: None),
        },
    ):
        with pytest.raises(RuntimeError, match="model_path is empty"):
            _synthesize_with_kokoro(request={"text": "hello", "model_path": "", "voices_path": "voices.bin"})
        with pytest.raises(RuntimeError, match="voices_path is empty"):
            _synthesize_with_kokoro(request={"text": "hello", "model_path": "model.onnx", "voices_path": ""})
