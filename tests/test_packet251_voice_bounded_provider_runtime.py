from __future__ import annotations

import base64
import io
import json
import logging
import socket
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from voice_comms_chip import profile, spark_hook


def _realtime_request() -> dict[str, object]:
    return {
        "base_url": "wss://api.openai.com/v1/realtime",
        "model_id": "gpt-realtime-2",
        "secret_value": "test-secret",
        "text": "hello",
        "timeout_seconds": 1,
    }


def test_realtime_receive_timeout_is_bounded() -> None:
    websocket = SimpleNamespace(
        send=Mock(),
        recv=Mock(side_effect=socket.timeout()),
        settimeout=Mock(),
        close=Mock(),
    )
    module = SimpleNamespace(create_connection=lambda *args, **kwargs: websocket)

    with patch.dict(sys.modules, {"websocket": module}):
        with pytest.raises(RuntimeError, match="timed out"):
            spark_hook._synthesize_with_openai_realtime(request=_realtime_request())

    websocket.settimeout.assert_called()
    websocket.close.assert_called_once()


def test_realtime_total_audio_is_bounded() -> None:
    events = iter(
        [
            json.dumps(
                {
                    "type": "response.output_audio.delta",
                    "delta": base64.b64encode(b"four").decode("ascii"),
                }
            ),
            json.dumps({"type": "response.done"}),
        ]
    )
    websocket = SimpleNamespace(
        send=Mock(),
        recv=lambda: next(events),
        settimeout=Mock(),
        close=Mock(),
    )
    module = SimpleNamespace(create_connection=lambda *args, **kwargs: websocket)

    with (
        patch.dict(sys.modules, {"websocket": module}),
        patch.object(spark_hook, "MAX_REALTIME_AUDIO_BYTES", 3),
        pytest.raises(RuntimeError, match="audio response limit"),
    ):
        spark_hook._synthesize_with_openai_realtime(request=_realtime_request())

    websocket.close.assert_called_once()


def test_tts_text_limit_counts_encoded_bytes() -> None:
    with (
        patch.object(spark_hook, "MAX_TTS_TEXT_BYTES", 3),
        pytest.raises(ValueError, match="3-byte limit"),
    ):
        spark_hook._resolve_tts_request(
            {"text": "éé"},
            profile=profile.load_voice_profile(),
        )


def test_provider_http_error_body_is_bounded_and_not_exposed() -> None:
    secret = b"sk-packet251-secret-value-that-must-not-escape"
    error = urllib.error.HTTPError(
        "https://api.openai.com/v1/audio/transcriptions",
        401,
        "Unauthorized",
        {},
        io.BytesIO(secret),
    )
    with (
        patch.object(spark_hook, "_open_provider_request", side_effect=error),
        pytest.raises(RuntimeError, match=r"rejected its credential") as raised,
    ):
        spark_hook._post_multipart(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": "Bearer test"},
            fields={"model": "test"},
            files=[
                {
                    "field_name": "file",
                    "filename": "voice.ogg",
                    "mime_type": "audio/ogg",
                    "content": b"audio",
                }
            ],
        )

    assert secret.decode() not in str(raised.value)


def test_install_results_expose_runtime_label_not_executable_path() -> None:
    with patch.object(spark_hook, "_local_faster_whisper_available", return_value=True):
        result = spark_hook._install_faster_whisper()

    assert result["result"]["python"].startswith("python ")
    assert "/" not in result["result"]["python"]
    assert "\\" not in result["result"]["python"]


def test_invalid_numeric_setting_is_named_without_echoing_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        assert spark_hook._resolve_optional_float(
            "packet251-secret-value",
            setting_name=spark_hook.ENV_KOKORO_SPEED,
        ) is None

    assert spark_hook.ENV_KOKORO_SPEED in caplog.text
    assert "packet251-secret-value" not in caplog.text


def test_directory_asset_error_is_actionable_without_echoing_path(tmp_path: Path) -> None:
    asset_dir = tmp_path / "private-model-directory"
    asset_dir.mkdir()

    with pytest.raises(ValueError, match="regular file") as raised:
        spark_hook._resolve_voice_local_file(
            str(asset_dir),
            roots=(tmp_path,),
            boundary_label="approved test roots",
        )

    assert "private-model-directory" not in str(raised.value)


def test_onboarding_playbook_separates_voice_proofs() -> None:
    playbook = Path("docs/AGENT_ONBOARDING_PLAYBOOK.md").read_text(encoding="utf-8")

    assert "`/voice status`" in playbook
    assert "`/voice speak Voice setup smoke test.`" in playbook
    assert "readiness, synthesis, and delivery as separate proofs" in playbook
