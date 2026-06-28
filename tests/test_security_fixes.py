from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from voice_comms_chip.spark_hook import (
    _build_deterministic_fallback_transcript,
    OPENAI_REALTIME_MAX_MESSAGES,
    OPENAI_REALTIME_MAX_TOTAL_BYTES,
)


class TestBuildDeterministicFallbackTranscript:
    """Tests for the deterministic fallback transcript builder."""

    def test_redacts_internal_exception_details(self):
        """Verify that internal exception details are NOT leaked in the output."""
        audio_bytes = b"\x00" * 16000  # 1 second of silence
        internal_exception = (
            "ConnectionRefusedError: [Errno 111] Connection refused to "
            "192.168.1.100:5432 - PostgreSQL on internal host postgres.internal.corp:5432"
        )
        result = _build_deterministic_fallback_transcript(
            audio_bytes=audio_bytes,
            filename="test.wav",
            reason=internal_exception,
        )
        # Internal details must not appear
        assert "192.168.1.100" not in result
        assert "postgres.internal.corp" not in result
        assert "ConnectionRefusedError" not in result
        assert "Errno 111" not in result
        # Should contain the redacted message
        assert "transcription unavailable" in result

    def test_no_exception_leak_with_empty_reason(self):
        """Verify generic message even with empty reason."""
        audio_bytes = b"\x00" * 8000
        result = _build_deterministic_fallback_transcript(
            audio_bytes=audio_bytes,
            filename="audio.ogg",
            reason="",
        )
        assert "transcription unavailable" in result
        assert "Provider reason:" in result

    def test_no_exception_leak_with_none_like_reason(self):
        """Verify generic message even with None-like reason."""
        audio_bytes = b"\x00" * 4000
        result = _build_deterministic_fallback_transcript(
            audio_bytes=audio_bytes,
            filename="clip.wav",
            reason="",  # Use empty string instead of None for type safety
        )
        assert "transcription unavailable" in result

    def test_output_contains_expected_structure(self):
        """Verify the transcript has the expected format."""
        audio_bytes = b"\x00" * 32000  # 2 seconds
        result = _build_deterministic_fallback_transcript(
            audio_bytes=audio_bytes,
            filename="sample.mp3",
            reason="some internal error",
        )
        assert result.startswith("[Deterministic fallback transcript]")
        assert "Audio received" in result
        assert "2.00s" in result
        assert "32000 bytes" in result
        assert "source sample.mp3" in result
        assert "transcription unavailable" in result


class TestWebSocketDoSLimits:
    """Tests for WebSocket message count and size limits."""

    def test_constants_are_set(self):
        """Verify the DoS protection constants are defined."""
        assert OPENAI_REALTIME_MAX_MESSAGES == 100
        assert OPENAI_REALTIME_MAX_TOTAL_BYTES == 50 * 1024 * 1024

    def test_message_count_limit_enforced(self):
        """Verify that exceeding message count raises RuntimeError."""
        from voice_comms_chip.spark_hook import _synthesize_with_openai_realtime

        ws_mock = MagicMock()
        # Create enough messages to exceed the limit
        messages = [
            json.dumps({"type": "response.output_audio.delta", "delta": ""})
            for _ in range(OPENAI_REALTIME_MAX_MESSAGES + 1)
        ]
        # Add a response.done at the end (but it won't be reached)
        messages.append(json.dumps({"type": "response.done"}))
        ws_mock.recv.side_effect = messages

        request = {
            "model_id": "test-model",
            "base_url": "wss://test.example.com",
            "voice_id": "test-voice",
            "sample_rate": 24000,
            "timeout_seconds": 10,
            "secret_value": "test-secret",
            "text": "Hello",
            "instructions": "Test",
        }

        with patch("voice_comms_chip.spark_hook.importlib.import_module") as mock_import:
            mock_ws_module = MagicMock()
            mock_ws_module.create_connection.return_value = ws_mock
            mock_import.return_value = mock_ws_module

            with pytest.raises(RuntimeError, match="maximum message count limit"):
                _synthesize_with_openai_realtime(request=request)

    def test_total_size_limit_enforced(self):
        """Verify that exceeding total message size raises RuntimeError."""
        from voice_comms_chip.spark_hook import _synthesize_with_openai_realtime

        ws_mock = MagicMock()
        # Create a few large messages to exceed the 50MB limit
        large_delta = "A" * (25 * 1024 * 1024)  # 25MB each
        messages = [
            json.dumps({"type": "response.output_audio.delta", "delta": large_delta})
            for _ in range(3)  # 3 * 25MB = 75MB > 50MB limit
        ]
        ws_mock.recv.side_effect = messages

        request = {
            "model_id": "test-model",
            "base_url": "wss://test.example.com",
            "voice_id": "test-voice",
            "sample_rate": 24000,
            "timeout_seconds": 10,
            "secret_value": "test-secret",
            "text": "Hello",
            "instructions": "Test",
        }

        with patch("voice_comms_chip.spark_hook.importlib.import_module") as mock_import:
            mock_ws_module = MagicMock()
            mock_ws_module.create_connection.return_value = ws_mock
            mock_import.return_value = mock_ws_module

            with pytest.raises(RuntimeError, match="exceeds size limit"):
                _synthesize_with_openai_realtime(request=request)
