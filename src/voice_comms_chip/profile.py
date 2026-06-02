from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_PATH = PROJECT_ROOT / "voices" / "spark_core.voice_profile.json"


def load_voice_profile(path: str | None = None) -> dict[str, Any]:
    target = Path(path) if path else DEFAULT_PROFILE_PATH
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Voice profile not found. Reinstall the voice-comms chip, or pass a valid "
            "profile path to load_voice_profile()."
        ) from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Voice profile at '{target}' contains invalid JSON. "
            "Reinstall the voice-comms chip or fix the profile file."
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("Voice profile must be a JSON object.")
    return payload


def summarize_voice_profile(profile: dict[str, Any]) -> dict[str, Any]:
    tone = profile.get("tone") if isinstance(profile.get("tone"), dict) else {}
    speech = profile.get("speech") if isinstance(profile.get("speech"), dict) else {}
    interaction = profile.get("interaction") if isinstance(profile.get("interaction"), dict) else {}
    provider_voices = (
        profile.get("provider_voices") if isinstance(profile.get("provider_voices"), dict) else {}
    )
    return {
        "profile_name": str(profile.get("profile_name") or "unknown").strip() or "unknown",
        "tone_identity": str(tone.get("identity") or "unknown").strip() or "unknown",
        "default_rate": speech.get("default_rate"),
        "default_emotion": str(speech.get("default_emotion") or "unknown").strip() or "unknown",
        "barge_in_enabled": bool(interaction.get("barge_in_enabled")),
        "streaming_reply_default": bool(interaction.get("streaming_reply_default")),
        "provider_voice_ids": sorted(
            provider_name
            for provider_name, payload in provider_voices.items()
            if isinstance(provider_name, str) and provider_name.strip() and isinstance(payload, dict)
        ),
    }


def get_provider_voice_profile(profile: dict[str, Any], provider_id: str) -> dict[str, Any]:
    provider_voices = (
        profile.get("provider_voices") if isinstance(profile.get("provider_voices"), dict) else {}
    )
    payload = provider_voices.get(provider_id)
    return payload if isinstance(payload, dict) else {}
