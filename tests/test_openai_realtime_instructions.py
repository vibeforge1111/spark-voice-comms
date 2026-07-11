"""
Trust-boundary tests for _synthesize_with_openai_realtime — instructions key fix.

Boundary: caller dict → _synthesize_with_openai_realtime → WebSocket payload
Before fix: request["instructions"] raised KeyError when instructions absent.
After fix:  request.get("instructions", "") uses empty string as default.

Tests cover: valid input, malformed/missing input, bounded output, safe failure,
no secret/env leakage.
"""

import base64
import json
import sys
from unittest.mock import MagicMock, patch
import pytest


def _make_fake_websocket_module(recv_events=None):
    """Return (fake_module, fake_ws). recv() yields given events in sequence."""
    if recv_events is None:
        recv_events = [{"type": "response.done"}]
    fake_ws = MagicMock()
    fake_ws.recv.side_effect = [json.dumps(e) for e in recv_events]
    fake_ws.send = MagicMock()
    fake_ws.close = MagicMock()
    fake_module = MagicMock()
    fake_module.create_connection.return_value = fake_ws
    return fake_module, fake_ws


def _base_request(**extra):
    """Minimum valid request dict without instructions."""
    return {
        "model_id": "gpt-4o-realtime-preview",
        "base_url": "wss://api.openai.com/v1",
        "secret_value": "sk-FAKE-DO-NOT-USE-IN-PROD",
        "text": "Hello world",
        **extra,
    }


# ---------------------------------------------------------------------------
# Valid input
# ---------------------------------------------------------------------------

def test_missing_instructions_defaults_to_empty_string_in_payload():
    """When instructions is absent, response.create must send instructions='' not raise KeyError."""
    fake_module, fake_ws = _make_fake_websocket_module()
    with patch.dict(sys.modules, {"websocket": fake_module}):
        import voice_comms_chip.spark_hook as hook
        try:
            hook._synthesize_with_openai_realtime(request=_base_request())
        except RuntimeError:
            pass  # expected: empty audio from mock

    assert fake_ws.send.call_count == 2, "expected session.update + response.create sends"
    response_create = json.loads(fake_ws.send.call_args_list[1][0][0])
    assert response_create["response"]["instructions"] == ""


def test_instructions_present_forwarded_verbatim():
    """Present instructions value is forwarded verbatim to response.create payload."""
    fake_module, fake_ws = _make_fake_websocket_module()
    with patch.dict(sys.modules, {"websocket": fake_module}):
        import voice_comms_chip.spark_hook as hook
        try:
            hook._synthesize_with_openai_realtime(
                request=_base_request(instructions="speak slowly and clearly")
            )
        except RuntimeError:
            pass

    assert fake_ws.send.call_count == 2
    response_create = json.loads(fake_ws.send.call_args_list[1][0][0])
    assert response_create["response"]["instructions"] == "speak slowly and clearly"


# ---------------------------------------------------------------------------
# Malformed / missing input
# ---------------------------------------------------------------------------

def test_missing_instructions_no_keyerror():
    """Absent instructions key must never raise KeyError — regression guard."""
    fake_module, _ = _make_fake_websocket_module()
    with patch.dict(sys.modules, {"websocket": fake_module}):
        import voice_comms_chip.spark_hook as hook
        try:
            hook._synthesize_with_openai_realtime(request=_base_request())
        except KeyError as e:
            pytest.fail(f"KeyError must not propagate for missing instructions: {e}")
        except RuntimeError:
            pass  # expected


def test_integer_instructions_converted_to_str_not_crash():
    """Non-string instructions value is coerced by str() — no type crash."""
    fake_module, fake_ws = _make_fake_websocket_module()
    with patch.dict(sys.modules, {"websocket": fake_module}):
        import voice_comms_chip.spark_hook as hook
        try:
            hook._synthesize_with_openai_realtime(request=_base_request(instructions=42))
        except KeyError as e:
            pytest.fail(f"KeyError raised: {e}")
        except RuntimeError:
            pass

    assert fake_ws.send.call_count == 2
    response_create = json.loads(fake_ws.send.call_args_list[1][0][0])
    assert response_create["response"]["instructions"] == "42"


# ---------------------------------------------------------------------------
# Safe failure
# ---------------------------------------------------------------------------

def test_safe_failure_empty_audio_raises_runtime_error():
    """Server sends response.done with no audio → RuntimeError, not a bare crash."""
    fake_module, _ = _make_fake_websocket_module(recv_events=[{"type": "response.done"}])
    with patch.dict(sys.modules, {"websocket": fake_module}):
        import voice_comms_chip.spark_hook as hook
        with pytest.raises(RuntimeError, match="empty audio"):
            hook._synthesize_with_openai_realtime(request=_base_request())


def test_server_error_event_wrapped_in_runtime_error():
    """Server-sent error events are wrapped in RuntimeError — not re-raised as bare data."""
    error_event = [{"type": "error", "error": {"message": "rate limit exceeded"}}]
    fake_module, _ = _make_fake_websocket_module(recv_events=error_event)
    with patch.dict(sys.modules, {"websocket": fake_module}):
        import voice_comms_chip.spark_hook as hook
        with pytest.raises(RuntimeError, match="OpenAI Realtime TTS request failed"):
            hook._synthesize_with_openai_realtime(request=_base_request())


# ---------------------------------------------------------------------------
# Bounded output
# ---------------------------------------------------------------------------

def test_bounded_output_is_bytes_str_tuple():
    """When audio is produced, function returns (bytes, str) — no internal relay state leaked."""
    pcm = b"\x00\x01" * 200
    audio_b64 = base64.b64encode(pcm).decode("ascii")
    recv_events = [
        {"type": "response.output_audio.delta", "delta": audio_b64},
        {"type": "response.done"},
    ]
    fake_module, _ = _make_fake_websocket_module(recv_events=recv_events)
    with patch.dict(sys.modules, {"websocket": fake_module}):
        import voice_comms_chip.spark_hook as hook
        result = hook._synthesize_with_openai_realtime(request=_base_request())

    assert isinstance(result, tuple) and len(result) == 2
    audio_bytes, voice_id = result
    assert isinstance(audio_bytes, bytes) and len(audio_bytes) > 0
    assert isinstance(voice_id, str)


# ---------------------------------------------------------------------------
# No secret / env leakage
# ---------------------------------------------------------------------------

def test_secret_value_not_echoed_in_runtime_error():
    """secret_value from request must not appear verbatim in a RuntimeError message."""
    error_event = [{"type": "error", "error": {"message": "authentication failed"}}]
    fake_module, _ = _make_fake_websocket_module(recv_events=error_event)
    secret = "sk-FAKE-DO-NOT-USE-IN-PROD"
    with patch.dict(sys.modules, {"websocket": fake_module}):
        import voice_comms_chip.spark_hook as hook
        with pytest.raises(RuntimeError) as exc_info:
            hook._synthesize_with_openai_realtime(request=_base_request(secret_value=secret))
    assert secret not in str(exc_info.value)
