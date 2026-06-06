import pytest


def simulate_websocket_consumer(messages: list[str], max_messages: int = 10000) -> dict:
    """Simulates the fixed while-True WebSocket consumer loop with a message cap."""
    import json

    audio_chunks = []
    message_count = 0

    for raw_message in messages:
        message_count += 1
        if message_count > max_messages:
            raise RuntimeError(
                f"OpenAI Realtime TTS WebSocket exceeded {max_messages} messages without response.done — aborting to prevent DoS."
            )
        if not raw_message:
            continue
        try:
            event = json.loads(raw_message)
        except json.JSONDecodeError:
            raise RuntimeError("malformed websocket message")
        event_type = str(event.get("type") or "")
        if event_type == "error":
            raise RuntimeError("TTS request failed")
        if event_type == "response.output_audio.delta":
            audio_chunks.append(event.get("delta", ""))
        elif event_type == "response.done":
            return {"audio_chunks": audio_chunks, "message_count": message_count}

    raise RuntimeError("Stream ended without response.done")


class TestWebSocketConsumerDos:
    def test_normal_stream_completes_successfully(self):
        import json
        messages = [
            json.dumps({"type": "response.output_audio.delta", "delta": "AAAA"}),
            json.dumps({"type": "response.done"}),
        ]
        result = simulate_websocket_consumer(messages)
        assert result["message_count"] == 2
        assert "AAAA" in result["audio_chunks"]

    def test_exceeding_max_messages_raises_error(self):
        import json
        messages = [json.dumps({"type": "response.output_audio.delta", "delta": "x"})] * 11
        with pytest.raises(RuntimeError, match="exceeded"):
            simulate_websocket_consumer(messages, max_messages=10)

    def test_exactly_at_limit_does_not_raise(self):
        import json
        messages = [json.dumps({"type": "response.output_audio.delta", "delta": "x"})] * 9
        messages.append(json.dumps({"type": "response.done"}))
        result = simulate_websocket_consumer(messages, max_messages=10)
        assert result["message_count"] == 10

    def test_dripping_server_halted_before_memory_exhaustion(self):
        import json
        infinite_messages = [json.dumps({"type": "response.output_audio.delta", "delta": "x"})] * 10001
        with pytest.raises(RuntimeError, match="exceeded"):
            simulate_websocket_consumer(infinite_messages, max_messages=10000)

    def test_error_event_still_raises(self):
        import json
        messages = [json.dumps({"type": "error", "error": {"message": "provider failure"}})]
        with pytest.raises(RuntimeError, match="TTS request failed"):
            simulate_websocket_consumer(messages)

    def test_empty_messages_skipped_count_toward_limit(self):
        import json
        messages = [""] * 5
        messages.append(json.dumps({"type": "response.done"}))
        result = simulate_websocket_consumer(messages, max_messages=10)
        assert result["message_count"] == 6
