from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "spark.voice_runtime_state.v1"
CANONICAL_CHIP_KEY = "spark-voice-comms"


def build_voice_runtime_state(
    *,
    surface: str = "unknown",
    dm_voice_replies: str = "unknown",
    stt: dict[str, Any] | None = None,
    tts: dict[str, Any] | None = None,
    telegram_delivery: dict[str, Any] | None = None,
    latency: dict[str, Any] | None = None,
    source_ledger: list[str] | None = None,
    request_ref: str | None = None,
    trace_ref: str | None = None,
    harness_proof_ref: str | None = None,
    trace_context_scope: str | None = None,
    generated_at: str | None = None,
    legacy_alias_visible: bool = False,
) -> dict[str, Any]:
    stt_state = _normalize_stt(stt or {})
    tts_state = _normalize_tts(tts or {})
    delivery_state = _normalize_telegram_delivery(telegram_delivery or {})
    latency_state = _normalize_latency(latency or {})
    claim_levels = _claim_levels(stt=stt_state, tts=tts_state, delivery=delivery_state)
    safe_request_ref = _redacted_ref("request", request_ref)
    safe_trace_ref = _redacted_ref("trace", trace_ref)
    safe_proof_ref = _redacted_ref("proof", harness_proof_ref)
    trace_continuity = _trace_continuity(
        request_ref=safe_request_ref,
        trace_ref=safe_trace_ref,
        harness_proof_ref=safe_proof_ref,
        trace_context_scope=trace_context_scope,
    )
    state = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _now_iso(),
        "surface": str(surface or "unknown"),
        "dm_voice_replies": str(dm_voice_replies or "unknown"),
        "canonical_chip_key": CANONICAL_CHIP_KEY,
        "legacy_alias_visible": bool(legacy_alias_visible),
        "stt": stt_state,
        "tts": tts_state,
        "telegram_delivery": delivery_state,
        "latency": latency_state,
        "claim_levels": claim_levels,
        "source_ledger": list(source_ledger or []),
        "trace_continuity": trace_continuity,
    }
    if safe_request_ref:
        state["request_ref"] = safe_request_ref
    if safe_trace_ref:
        state["trace_ref"] = safe_trace_ref
    if safe_proof_ref:
        state["harness_proof_ref"] = safe_proof_ref
    return state


def state_from_status(
    *,
    status: dict[str, Any],
    profile_summary: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    surface = str(payload.get("surface") or "telegram").strip() or "telegram"
    local_tts_ready = bool(status.get("local_tts_ready"))
    local_tts_provider = str(status.get("local_tts_provider") or "").strip()
    if not local_tts_provider and local_tts_ready:
        local_tts_provider = "local"
    tts_ready = bool(status.get("tts_ready", local_tts_ready))
    tts_provider_id = str(status.get("tts_provider_id") or local_tts_provider or "none").strip() or "none"
    delivery = payload.get("telegram_delivery") if isinstance(payload.get("telegram_delivery"), dict) else {}
    latency = payload.get("latency") if isinstance(payload.get("latency"), dict) else {}
    return build_voice_runtime_state(
        surface=surface,
        dm_voice_replies=str(payload.get("dm_voice_replies") or "unknown"),
        stt={
            "provider_id": status.get("provider_id") or "none",
            "provider_kind": status.get("provider_kind") or "unknown",
            "mode": "local" if status.get("local_ready") else ("hosted" if status.get("ready") else "unknown"),
            "ready": bool(status.get("ready")),
            "model": status.get("model"),
            "claim_boundary": "Transcription readiness is not Telegram delivery proof.",
        },
        tts={
            "provider_id": tts_provider_id,
            "mode": "local" if tts_provider_id in {"kokoro", "pyttsx3", "local"} else "hosted",
            "ready": tts_ready,
            "voice_name": profile_summary.get("profile_name"),
            "voice_id": status.get("tts_voice_id"),
            "model_id": status.get("tts_model_id"),
            "settings": status.get("tts_settings") if isinstance(status.get("tts_settings"), dict) else {},
        },
        telegram_delivery=delivery,
        latency=latency,
        source_ledger=["voice.status", "voice_profile"] + _optional_sources(payload),
        request_ref=_payload_trace_value(payload, "request_ref", "request_id", "requestId"),
        trace_ref=_payload_trace_value(payload, "trace_ref", "trace_id", "traceId"),
        harness_proof_ref=_payload_trace_value(payload, "harness_proof_ref", "harnessProofRef", "proof_ref"),
        trace_context_scope=_payload_trace_value(payload, "trace_context_scope") or "voice.status",
        legacy_alias_visible=bool(payload.get("legacy_alias_visible")),
    )


def state_from_speak(
    *,
    request: dict[str, Any],
    resolved_voice_id: str,
    audio_bytes: bytes,
    profile_summary: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    surface = str(request.get("surface") or payload.get("surface") or "unknown").strip() or "unknown"
    delivery = payload.get("telegram_delivery") if isinstance(payload.get("telegram_delivery"), dict) else {}
    latency = payload.get("latency") if isinstance(payload.get("latency"), dict) else {}
    return build_voice_runtime_state(
        surface=surface,
        dm_voice_replies=str(payload.get("dm_voice_replies") or "unknown"),
        stt={
            "provider_id": "not_used",
            "provider_kind": "none",
            "mode": "not_applicable",
            "ready": False,
            "claim_boundary": "Synthesis readiness is not transcription readiness.",
        },
        tts={
            "provider_id": request.get("provider_id") or "none",
            "mode": "local" if request.get("provider_id") in {"kokoro", "pyttsx3"} else "hosted",
            "ready": bool(audio_bytes),
            "voice_name": request.get("preferred_voice_name") or profile_summary.get("profile_name"),
            "voice_id": resolved_voice_id,
            "model_id": request.get("model_id"),
            "mime_type": request.get("mime_type"),
            "voice_compatible": bool(request.get("voice_compatible")),
            "audio_bytes": len(audio_bytes),
            "settings": request.get("voice_settings") if isinstance(request.get("voice_settings"), dict) else {},
        },
        telegram_delivery=delivery,
        latency=latency,
        source_ledger=["voice.speak", "voice_profile"] + _optional_sources(payload),
        request_ref=_payload_trace_value(payload, "request_ref", "request_id", "requestId"),
        trace_ref=_payload_trace_value(payload, "trace_ref", "trace_id", "traceId"),
        harness_proof_ref=_payload_trace_value(payload, "harness_proof_ref", "harnessProofRef", "proof_ref"),
        trace_context_scope=_payload_trace_value(payload, "trace_context_scope") or "voice.speak",
        legacy_alias_visible=bool(payload.get("legacy_alias_visible")),
    )


def state_from_transcribe(
    *,
    provider_id: str,
    mode: str,
    model: str,
    audio_bytes: int,
    transcript_text: str,
    payload: dict[str, Any],
    transcribe_ms: int = 0,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    surface = str(payload.get("surface") or "telegram").strip() or "telegram"
    return build_voice_runtime_state(
        surface=surface,
        dm_voice_replies=str(payload.get("dm_voice_replies") or "unknown"),
        stt={
            "provider_id": provider_id,
            "provider_kind": "local" if provider_id in {"local_faster_whisper", "deterministic_fallback"} else "hosted",
            "mode": mode,
            "ready": True,
            "model": model,
            "claim_boundary": "Transcription succeeded; TTS and Telegram delivery are separate claims.",
            "last_failure_reason": fallback_reason or "",
        },
        tts={
            "provider_id": "not_used",
            "mode": "not_applicable",
            "ready": False,
        },
        telegram_delivery={},
        latency={"transcribe_ms": transcribe_ms},
        source_ledger=["voice.transcribe"] + _optional_sources(payload),
        request_ref=_payload_trace_value(payload, "request_ref", "request_id", "requestId"),
        trace_ref=_payload_trace_value(payload, "trace_ref", "trace_id", "traceId"),
        harness_proof_ref=_payload_trace_value(payload, "harness_proof_ref", "harnessProofRef", "proof_ref"),
        trace_context_scope=_payload_trace_value(payload, "trace_context_scope") or "voice.transcribe",
        legacy_alias_visible=bool(payload.get("legacy_alias_visible")),
    ) | {
        "transcript": {
            "characters": len(transcript_text),
            "fingerprint": fingerprint(transcript_text),
            "audio_bytes": max(0, int(audio_bytes)),
            "fallback_reason": _safe_reason(fallback_reason),
        }
    }


def _normalize_stt(stt: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_id": str(stt.get("provider_id") or "none"),
        "provider_kind": str(stt.get("provider_kind") or "unknown"),
        "mode": str(stt.get("mode") or "unknown"),
        "ready": coerce_bool(stt.get("ready")),
        "model": _optional_string(stt.get("model")),
        "last_probe_ref": _optional_string(stt.get("last_probe_ref")),
        "last_failure_reason": _safe_reason(stt.get("last_failure_reason")),
        "claim_boundary": str(stt.get("claim_boundary") or "Readiness is scoped to this state section."),
    }


def _normalize_tts(tts: dict[str, Any]) -> dict[str, Any]:
    voice_id = _optional_string(tts.get("voice_id"))
    settings = tts.get("settings") if isinstance(tts.get("settings"), dict) else {}
    return {
        "provider_id": str(tts.get("provider_id") or "none"),
        "mode": str(tts.get("mode") or "unknown"),
        "ready": coerce_bool(tts.get("ready")),
        "voice_name": _optional_string(tts.get("voice_name")),
        "voice_id_masked": mask_identifier(voice_id),
        "voice_id_fingerprint": fingerprint(voice_id),
        "model_id": _optional_string(tts.get("model_id")),
        "mime_type": _optional_string(tts.get("mime_type")),
        "voice_compatible": coerce_bool(tts.get("voice_compatible")),
        "audio_bytes": int(tts.get("audio_bytes") or 0),
        "settings_fingerprint": fingerprint(settings),
        "last_probe_ref": _optional_string(tts.get("last_probe_ref")),
        "claim_boundary": str(tts.get("claim_boundary") or "Synthesis readiness is not Telegram delivery proof."),
    }


def _normalize_telegram_delivery(delivery: dict[str, Any]) -> dict[str, Any]:
    status = str(delivery.get("last_send_voice_status") or delivery.get("status") or "unknown")
    return {
        "ready": coerce_bool(delivery.get("ready")) or status == "success",
        "last_send_voice_at": _optional_string(delivery.get("last_send_voice_at")),
        "last_send_voice_status": status,
        "last_failure_reason": _safe_reason(delivery.get("last_failure_reason") or delivery.get("failure_reason")),
        "telegram_message_id_present": bool(delivery.get("telegram_message_id")),
    }


def _normalize_latency(latency: dict[str, Any]) -> dict[str, int]:
    keys = [
        "download_audio_ms",
        "transcribe_ms",
        "builder_answer_ms",
        "prepare_spoken_text_ms",
        "synthesize_ms",
        "convert_audio_ms",
        "send_voice_ms",
        "total_ms",
    ]
    return {key: _nonnegative_int(latency.get(key)) for key in keys}


def _claim_levels(
    *,
    stt: dict[str, Any],
    tts: dict[str, Any],
    delivery: dict[str, Any],
) -> dict[str, bool]:
    configured = stt.get("provider_id", "none") != "none" or tts.get("provider_id", "none") != "none"
    synthesis_ready = bool(tts["ready"])
    delivery_ready = bool(delivery["ready"])
    conversation_ready = bool(stt["ready"] and synthesis_ready and delivery_ready)
    return {
        "configured": configured,
        "synthesis_ready": synthesis_ready,
        "delivery_ready": delivery_ready,
        "conversation_ready": conversation_ready,
    }


def fingerprint(value: Any) -> str:
    if value in (None, "", {}, []):
        return ""
    encoded = json_safe(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


def mask_identifier(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return f"{text[:2]}...{fingerprint(text)[:6]}"
    return f"{text[:4]}...{text[-4:]}"


def _redacted_ref(kind: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    prefix = f"{kind}:sha256:"
    if text.startswith(prefix):
        suffix = text[len(prefix):]
        if suffix and all(char in "0123456789abcdefABCDEF" for char in suffix):
            return f"{prefix}{suffix.lower()}"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}"


def _trace_continuity(
    *,
    request_ref: str,
    trace_ref: str,
    harness_proof_ref: str,
    trace_context_scope: str | None,
) -> dict[str, Any]:
    return {
        "request_joined": bool(request_ref),
        "trace_joined": bool(trace_ref),
        "proof_joined": bool(harness_proof_ref),
        "proof_storage": "redacted_ref_only" if harness_proof_ref else "missing",
        "trace_context_scope": str(trace_context_scope or "missing").strip() or "missing",
        "proof_status": "ref_only" if harness_proof_ref else "not_execution_proof",
        "raw_audio_exported": False,
        "transcript_bodies_exported": False,
    }


def json_safe(value: Any, _depth: int = 0) -> str:
    if _depth >= 10:
        return "[depth limit]"
    if isinstance(value, dict):
        parts = [f"{key}:{json_safe(value[key], _depth + 1)}" for key in sorted(value)]
        return "{" + ",".join(parts) + "}"
    if isinstance(value, list):
        return "[" + ",".join(json_safe(item, _depth + 1) for item in value) + "]"
    return str(value)


def _safe_reason(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > 240:
        return text[:237].rstrip() + "..."
    return text


def _optional_string(value: Any) -> str:
    return str(value or "").strip()


def coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
        return default
    if value is None:
        return default
    return bool(value)


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def _optional_sources(payload: dict[str, Any]) -> list[str]:
    sources = payload.get("source_ledger")
    if not isinstance(sources, list):
        return []
    return [str(source) for source in sources if str(source or "").strip()]


def _payload_trace_value(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if str(value or "").strip():
            return str(value).strip()
    trace_context = payload.get("trace_context")
    if isinstance(trace_context, dict):
        for key in keys:
            value = trace_context.get(key)
            if str(value or "").strip():
                return str(value).strip()
    return ""


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
