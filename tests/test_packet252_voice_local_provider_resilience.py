from __future__ import annotations

import base64
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from voice_comms_chip import profile, spark_hook


def test_local_status_falls_back_when_kokoro_needs_assets() -> None:
    with (
        patch.object(spark_hook, "_local_kokoro_ready", return_value=False),
        patch.object(spark_hook, "_local_kokoro_package_available", return_value=True),
        patch.object(spark_hook, "_local_pyttsx3_available", return_value=True),
    ):
        status = spark_hook._local_tts_status(env_map={})

    assert status["ready"] is True
    assert status["provider"] == spark_hook.LOCAL_TTS_PROVIDER
    assert "Kokoro is installed" in status["status"]


def test_pyttsx3_run_wait_has_a_deadline() -> None:
    release = threading.Event()
    engine = SimpleNamespace(
        init=lambda: None,
        setProperty=Mock(),
        getProperty=lambda name: [],
        save_to_file=Mock(),
        runAndWait=lambda: release.wait(timeout=1),
        stop=Mock(),
    )
    module = SimpleNamespace(init=lambda: engine)

    try:
        with (
            patch.object(spark_hook.importlib, "import_module", return_value=module),
            patch.object(spark_hook, "PYTTSX3_RUNANDWAIT_TIMEOUT_SECONDS", 0),
            pytest.raises(RuntimeError, match="0-second limit"),
        ):
            spark_hook._synthesize_with_pyttsx3(request={"text": "hello"})
    finally:
        release.set()

    engine.stop.assert_called_once()


def test_pyttsx3_uses_a_private_temp_output_directory() -> None:
    saved: dict[str, Path] = {}

    class Engine:
        def setProperty(self, name, value):
            return None

        def getProperty(self, name):
            return []

        def save_to_file(self, text, path):
            saved["path"] = Path(path)

        def runAndWait(self):
            saved["path"].write_bytes(b"RIFF-packet252")

    with patch.object(
        spark_hook.importlib,
        "import_module",
        return_value=SimpleNamespace(init=Engine),
    ):
        audio, _voice = spark_hook._synthesize_with_pyttsx3(request={"text": "hello"})

    assert audio == b"RIFF-packet252"
    assert saved["path"].name == "output.wav"
    assert saved["path"].parent.name.startswith("spark-tts-")
    assert not saved["path"].exists()


def test_kokoro_missing_package_is_named_precisely() -> None:
    with (
        patch.object(spark_hook.importlib, "import_module", side_effect=ImportError("missing")),
        pytest.raises(RuntimeError, match="`kokoro-onnx`"),
    ):
        spark_hook._synthesize_with_kokoro(request={"text": "hello"})


def test_whisper_models_are_reused_with_a_bounded_cache() -> None:
    constructor = Mock(return_value=object())
    module = SimpleNamespace(WhisperModel=constructor)
    spark_hook._load_local_whisper_model.cache_clear()
    try:
        with patch.dict(sys.modules, {"faster_whisper": module}):
            first = spark_hook._load_local_whisper_model("tiny")
            second = spark_hook._load_local_whisper_model("tiny")
    finally:
        spark_hook._load_local_whisper_model.cache_clear()

    assert first is second
    constructor.assert_called_once_with("tiny", device="cpu", compute_type="int8")
    assert spark_hook._load_local_whisper_model.cache_info().maxsize == 2


def test_elevenlabs_voice_id_is_validated_before_network_use() -> None:
    with pytest.raises(ValueError, match="letters, numbers, and hyphens"):
        spark_hook._synthesize_with_elevenlabs(
            request={
                "voice_id": "../private",
                "base_url": "https://api.elevenlabs.io/v1",
            }
        )


def test_elevenlabs_voice_settings_are_numeric_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "packet252-test-key")
    request = spark_hook._resolve_tts_request(
        {
            "text": "hello",
            "tts": {
                "provider_id": "elevenlabs",
                "voice_id": "Voice123",
                "voice_settings": {
                    "stability": "2.5",
                    "similarity_boost": "-1",
                    "style": "bad",
                    "speed": "3",
                },
            },
        },
        profile=profile.load_voice_profile(),
    )

    assert request["voice_settings"]["stability"] == 1.0
    assert request["voice_settings"]["similarity_boost"] == 0.0
    assert request["voice_settings"]["style"] == 0.03
    assert request["voice_settings"]["speed"] == 2.0


def test_deterministic_mode_stays_off_network_when_local_stt_is_missing() -> None:
    payload = {
        "audio_base64": base64.b64encode(b"packet252-audio").decode("ascii"),
        "filename": "voice.ogg",
        "mime_type": "audio/ogg",
        "fallback_mode": "deterministic",
    }
    with (
        patch.object(spark_hook, "assertNativeGovernorHarnessAuthority"),
        patch.object(spark_hook, "_transcription_provider_mode", return_value="auto"),
        patch.object(spark_hook, "_local_faster_whisper_available", return_value=False),
        patch.object(
            spark_hook,
            "_transcribe_with_provider",
            side_effect=AssertionError("must remain off network"),
        ),
    ):
        result = spark_hook.handle_voice_transcribe_hook(payload)

    assert result["returncode"] == 1
    assert result["result"]["usable_transcript"] is False
    assert result["result"]["provider_id"] == "deterministic_fallback"


@pytest.mark.parametrize(
    ("code", "message"),
    [
        (404, "endpoint was not found"),
        (401, "rejected its credential"),
        (429, "rate-limited"),
        (500, "failed with HTTP 500"),
    ],
)
def test_provider_http_guidance_is_status_specific(code: int, message: str) -> None:
    assert message in spark_hook._provider_http_error_message(code)
