from __future__ import annotations

import base64
import io
import json
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from voice_comms_chip.spark_hook import (
    handle_voice_onboard_hook,
    handle_voice_plan_hook,
    handle_voice_speak_hook,
    handle_voice_status_hook,
    handle_voice_transcribe_hook,
    main,
)

FAKE_OPENAI_KEY = "fake-openai-key-for-tests"
FAKE_ELEVENLABS_KEY = "fake-elevenlabs-key-for-tests"
FAKE_ELEVENLABS_VOICE_ID = "fake-elevenlabs-voice-id"


class _FakeBinaryHttpResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _payload(tmp_path, **overrides):
    env_file = tmp_path / ".env"
    env_file.write_text(f"OPENAI_API_KEY={FAKE_OPENAI_KEY}\n", encoding="utf-8")
    payload = {
        "builder_env_file_path": str(env_file),
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


def test_voice_status_reports_ready_when_provider_is_usable(tmp_path):
    result = handle_voice_status_hook(_payload(tmp_path))
    assert result["returncode"] == 0
    assert result["result"]["ready"] is True
    assert "Voice chip is ready." in result["result"]["reply_text"]


def test_voice_status_marks_custom_provider_as_unverified(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("CUSTOM_API_KEY=custom-test-key\n", encoding="utf-8")
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
    assert "custom provider transcription compatibility is not verified yet" in result["result"]["reason"]


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


def test_voice_plan_returns_modular_steps():
    result = handle_voice_plan_hook({})
    assert result["returncode"] == 0
    assert "spark-voice-comms" in result["result"]["reply_text"]


def test_voice_onboard_guides_local_free_path():
    with patch("voice_comms_chip.spark_hook._local_faster_whisper_available", return_value=True), patch(
        "voice_comms_chip.spark_hook._local_pyttsx3_available",
        return_value=True,
    ):
        result = handle_voice_onboard_hook({"route": "local"})

    assert result["returncode"] == 0
    assert result["result"]["recommended_path"] == "local_free"
    assert result["metrics"]["local_ready"] == 1
    assert "private/free path" in result["result"]["reply_text"]
    assert "local voice smoke" in result["result"]["reply_text"]


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
    assert "preference context leans local/private" in result["result"]["reply_text"]


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


def test_voice_transcribe_posts_openai_compatible_multipart_request(tmp_path):
    captured = {}

    def fake_urlopen(request, timeout: int = 30):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = request.data
        return _FakeBinaryHttpResponse(json.dumps({"text": "/voice plan"}).encode("utf-8"))

    with patch("voice_comms_chip.spark_hook.urllib.request.urlopen", side_effect=fake_urlopen):
        result = handle_voice_transcribe_hook(
            _payload(
                tmp_path,
                audio_base64=base64.b64encode(b"fake-ogg-bytes").decode("ascii"),
                filename="telegram-voice.ogg",
                mime_type="audio/ogg",
            )
        )

    headers = {str(key).lower(): value for key, value in captured["headers"].items()}
    assert result["returncode"] == 0
    assert result["result"]["transcript_text"] == "/voice plan"
    assert result["result"]["mode"] == "provider"
    assert captured["url"] == "https://api.openai.com/v1/audio/transcriptions"
    assert headers["authorization"] == f"Bearer {FAKE_OPENAI_KEY}"
    assert "multipart/form-data; boundary=" in headers["content-type"]
    assert b'filename="telegram-voice.ogg"' in captured["body"]
    assert b"fake-ogg-bytes" in captured["body"]


def test_voice_transcribe_can_return_deterministic_fallback_when_requested(tmp_path):
    with patch(
        "voice_comms_chip.spark_hook.urllib.request.urlopen",
        side_effect=RuntimeError("simulated provider outage"),
    ):
        result = handle_voice_transcribe_hook(
            _payload(
                tmp_path,
                audio_base64=base64.b64encode(b"fake-ogg-bytes").decode("ascii"),
                filename="telegram-voice.ogg",
                mime_type="audio/ogg",
                fallback_mode="deterministic",
            )
        )

    assert result["returncode"] == 0
    assert result["result"]["mode"] == "deterministic_fallback"
    assert "Deterministic fallback transcript" in result["result"]["transcript_text"]
    assert "simulated provider outage" in result["result"]["fallback_reason"]


def test_voice_transcribe_can_fallback_to_local_faster_whisper_when_provider_fails(tmp_path):
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
                "audio_base64": base64.b64encode(b"fake-ogg-bytes").decode("ascii"),
                "filename": "telegram-voice.ogg",
                "mime_type": "audio/ogg",
            }
        )

    headers = {str(key).lower(): value for key, value in captured["headers"].items()}
    assert result["returncode"] == 0
    assert result["result"]["transcript_text"] == "Voice via dedicated provider"
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
            {
                "builder_env_file_path": str(env_file),
                "text": "Operator status update.",
            }
        )

    headers = {str(key).lower(): value for key, value in captured["headers"].items()}
    assert result["returncode"] == 0
    assert result["result"]["provider_id"] == "elevenlabs"
    assert result["result"]["voice_id"] == FAKE_ELEVENLABS_VOICE_ID
    assert result["result"]["model_id"] == "eleven_turbo_v2_5"
    assert base64.b64decode(result["result"]["audio_base64"].encode("ascii")) == b"fake-mpeg-bytes"
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
            {
                "builder_env_file_path": str(env_file),
                "surface": "telegram",
                "text": "Telegram voice note reply.",
            }
        )

    headers = {str(key).lower(): value for key, value in captured["headers"].items()}
    assert result["returncode"] == 0
    assert result["result"]["mime_type"] == "audio/ogg"
    assert result["result"]["voice_compatible"] is True
    assert str(result["result"]["filename"]).endswith(".ogg")
    assert base64.b64decode(result["result"]["audio_base64"].encode("ascii")) == b"fake-opus-bytes"
    assert headers["accept"] == "audio/mpeg"
    assert "output_format=opus_48000_64" in captured["url"]
    assert captured["body"]["text"] == "Telegram voice note reply."


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
            {
                "text": "Local free voice.",
                "tts": {
                    "provider_id": "pyttsx3",
                    "voice_name": "test",
                    "rate": 175,
                    "volume": 0.8,
                },
            }
        )

    assert result["returncode"] == 0
    assert result["result"]["provider_id"] == "pyttsx3"
    assert result["result"]["mime_type"] == "audio/wav"
    assert result["result"]["voice_compatible"] is False
    assert base64.b64decode(result["result"]["audio_base64"].encode("ascii")) == b"fake-local-wav"
    assert captured["properties"] == {"rate": 175, "volume": 0.8, "voice": "test-voice-id"}
    assert captured["text"] == "Local free voice."


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
            {
                "builder_env_file_path": str(env_file),
                "text": "Retry the fallback voice.",
            }
        )

    assert result["returncode"] == 0
    assert result["result"]["voice_id"] == "fallback-voice-id"
    assert base64.b64decode(result["result"]["audio_base64"].encode("ascii")) == b"fallback-mpeg-bytes"
    assert any(url.endswith("/voices") for url in calls)
