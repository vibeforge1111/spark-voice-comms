from __future__ import annotations

from voice_comms_chip.runtime_state import (
    CANONICAL_CHIP_KEY,
    SCHEMA_VERSION,
    build_voice_runtime_state,
    state_from_speak,
    state_from_status,
    state_from_transcribe,
)


def test_runtime_state_masks_voice_id_and_tracks_claim_levels():
    state = build_voice_runtime_state(
        generated_at="2026-05-09T00:00:00Z",
        surface="telegram",
        dm_voice_replies="on",
        stt={"provider_id": "openai", "mode": "hosted", "ready": True},
        tts={
            "provider_id": "elevenlabs",
            "mode": "hosted",
            "ready": True,
            "voice_id": "private-elevenlabs-voice-id",
            "settings": {"stability": 0.4, "speed": 1.09},
        },
        telegram_delivery={"status": "success", "telegram_message_id": 123},
        source_ledger=["voice.status", "per-dm-state"],
    )

    assert state["schema_version"] == SCHEMA_VERSION
    assert state["canonical_chip_key"] == CANONICAL_CHIP_KEY
    assert state["tts"]["voice_id_masked"] == "priv...e-id"
    assert "private-elevenlabs-voice-id" not in str(state)
    assert state["telegram_delivery"]["telegram_message_id_present"] is True
    assert state["claim_levels"] == {
        "configured": True,
        "synthesis_ready": True,
        "delivery_ready": True,
        "conversation_ready": True,
    }


def test_status_state_does_not_claim_delivery_from_transcription_readiness():
    state = state_from_status(
        status={
            "ready": True,
            "local_ready": False,
            "provider_id": "openai",
            "provider_kind": "openai",
            "model": "whisper-1",
            "tts_ready": True,
            "tts_provider_id": "elevenlabs",
        },
        profile_summary={"profile_name": "spark_core"},
        payload={"surface": "telegram", "dm_voice_replies": "on"},
    )

    assert state["stt"]["ready"] is True
    assert state["tts"]["ready"] is True
    assert state["telegram_delivery"]["ready"] is False
    assert state["claim_levels"]["conversation_ready"] is False


def test_speak_state_marks_synthesis_ready_without_stt_claim():
    state = state_from_speak(
        request={
            "provider_id": "kokoro",
            "surface": "telegram",
            "model_id": "kokoro-v1.0.onnx",
            "mime_type": "audio/wav",
            "voice_compatible": False,
        },
        resolved_voice_id="af_sarah",
        audio_bytes=b"audio",
        profile_summary={"profile_name": "spark_core"},
        payload={"dm_voice_replies": "on"},
    )

    assert state["stt"]["provider_id"] == "not_used"
    assert state["stt"]["ready"] is False
    assert state["tts"]["provider_id"] == "kokoro"
    assert state["tts"]["ready"] is True
    assert state["claim_levels"]["synthesis_ready"] is True
    assert state["claim_levels"]["delivery_ready"] is False


def test_transcribe_state_tracks_transcript_without_delivery_claim():
    state = state_from_transcribe(
        provider_id="openai",
        mode="provider",
        model="whisper-1",
        audio_bytes=321,
        transcript_text="Hello from a voice note.",
        payload={"surface": "telegram"},
        transcribe_ms=42,
    )

    assert state["stt"]["provider_id"] == "openai"
    assert state["stt"]["ready"] is True
    assert state["tts"]["ready"] is False
    assert state["telegram_delivery"]["ready"] is False
    assert state["latency"]["transcribe_ms"] == 42
    assert state["transcript"]["characters"] == len("Hello from a voice note.")
    assert state["transcript"]["audio_bytes"] == 321
    assert state["claim_levels"]["conversation_ready"] is False


def test_delivery_ready_string_false_not_truthy():
    """String 'false' from JSON must not be treated as truthy readiness."""
    from voice_comms_chip.runtime_state import _normalize_telegram_delivery

    # Case 1: ready='false', no success status → should be False
    result = _normalize_telegram_delivery({"ready": "false"})
    assert result["ready"] is False, (
        "string 'false' should not claim delivery readiness"
    )

    # Case 2: ready='false', status='success' → should still be True via status
    result = _normalize_telegram_delivery({
        "ready": "false",
        "last_send_voice_status": "success",
    })
    assert result["ready"] is True

    # Case 3: ready='true' → should be True
    result = _normalize_telegram_delivery({"ready": "true"})
    assert result["ready"] is True

    # Case 4: ready=True (bool) → should be True
    result = _normalize_telegram_delivery({"ready": True})
    assert result["ready"] is True

    # Case 5: ready=None, no success → should be False
    result = _normalize_telegram_delivery({})
    assert result["ready"] is False
