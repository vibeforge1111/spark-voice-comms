from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from voice_comms_chip import profile, runtime_state, spark_hook


def _realtime_request(**overrides) -> dict[str, object]:
    request: dict[str, object] = {
        "base_url": "wss://api.openai.com/v1/realtime",
        "model_id": "gpt-realtime-2",
        "secret_value": "test-secret",
        "text": "hello",
        "timeout_seconds": 10,
    }
    request.update(overrides)
    return request


def test_realtime_drip_is_bounded_by_message_count() -> None:
    websocket = SimpleNamespace(
        send=Mock(),
        recv=Mock(return_value=""),
        settimeout=Mock(),
        close=Mock(),
    )
    module = SimpleNamespace(create_connection=lambda *args, **kwargs: websocket)

    with (
        patch.dict(sys.modules, {"websocket": module}),
        patch.object(spark_hook, "MAX_REALTIME_MESSAGES", 2),
        pytest.raises(RuntimeError, match="message limit"),
    ):
        spark_hook._synthesize_with_openai_realtime(request=_realtime_request())

    assert websocket.recv.call_count == 2
    websocket.close.assert_called_once()


def test_realtime_rejects_invalid_base64_audio() -> None:
    events = iter(
        [
            json.dumps({"type": "response.output_audio.delta", "delta": "!!!!"}),
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
        pytest.raises(RuntimeError, match="invalid audio data"),
    ):
        spark_hook._synthesize_with_openai_realtime(request=_realtime_request())


def test_realtime_closed_connection_fails_without_spinning() -> None:
    websocket = SimpleNamespace(
        send=Mock(),
        recv=Mock(return_value=None),
        settimeout=Mock(),
        close=Mock(),
    )
    module = SimpleNamespace(create_connection=lambda *args, **kwargs: websocket)

    with (
        patch.dict(sys.modules, {"websocket": module}),
        pytest.raises(RuntimeError, match="connection closed"),
    ):
        spark_hook._synthesize_with_openai_realtime(request=_realtime_request())

    websocket.recv.assert_called_once()


@pytest.mark.parametrize("output_format", ["ulaw_8000", "mu-law", "mulaw_8000"])
def test_mulaw_output_metadata_is_explicit(output_format: str) -> None:
    assert spark_hook._resolve_elevenlabs_output_metadata(output_format) == (
        "audio/basic",
        ".ulaw",
        False,
    )


@pytest.mark.parametrize(
    ("sample_rate", "expected"),
    [("100", 8_000), ("96000", 48_000), ("nan", 24_000), ("inf", 24_000)],
)
def test_realtime_sample_rate_is_finite_and_bounded(
    sample_rate: str,
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "packet253-test-key")
    request = spark_hook._resolve_tts_request(
        {
            "text": "hello",
            "tts": {
                "provider_id": "openai-realtime",
                "sample_rate": sample_rate,
            },
        },
        profile=profile.load_voice_profile(),
    )

    assert request["sample_rate"] == expected


def test_runtime_state_string_false_never_claims_ready() -> None:
    assert runtime_state.coerce_bool("false") is False
    assert runtime_state.coerce_bool("0") is False
    delivery = runtime_state._normalize_telegram_delivery({"ready": "false"})
    stt = runtime_state._normalize_stt({"ready": "false"})
    tts = runtime_state._normalize_tts({"ready": "false", "voice_compatible": "false"})

    assert delivery["ready"] is False
    assert stt["ready"] is False
    assert tts["ready"] is False
    assert tts["voice_compatible"] is False


def test_claim_levels_tolerate_missing_provider_keys() -> None:
    claims = runtime_state._claim_levels(
        stt={"ready": False},
        tts={"ready": False},
        delivery={"ready": False},
    )

    assert claims["configured"] is False
    assert claims["conversation_ready"] is False


def test_voice_status_contract_has_one_consistent_key_set() -> None:
    with patch.object(
        spark_hook,
        "_build_voice_status_core",
        return_value={"ready": True, "reason": "packet253"},
    ):
        status = spark_hook._build_voice_status({})

    assert status["ready"] is True
    assert status["reason"] == "packet253"
    assert set(status) == {
        "ready",
        "local_ready",
        "local_tts_ready",
        "local_tts_provider",
        "tts_ready",
        "tts_provider_id",
        "tts_status",
        "reason",
        "provider_id",
        "provider_kind",
        "model",
        "speech_reply_status",
        "provider_note",
        "hosted_provider_id",
        "hosted_provider_kind",
    }


def test_unexpected_hook_errors_are_typed_and_public_safe() -> None:
    secret = "sk-packet253-private-provider-detail"
    payload = spark_hook._hook_error_payload(RuntimeError(secret))
    encoded = json.dumps(payload)

    assert payload["error_type"] == "RuntimeError"
    assert payload["error_code"] == "voice_hook_runtime_error"
    assert payload["error"] == "The voice hook could not complete safely."
    assert secret not in encoded


def test_tts_character_limit_bounds_provider_cost() -> None:
    with pytest.raises(ValueError, match="10000-character limit"):
        spark_hook._resolve_tts_request(
            {"text": "a" * 10_001},
            profile=profile.load_voice_profile(),
        )
