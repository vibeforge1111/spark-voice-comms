from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_PATH = PROJECT_ROOT / "voices" / "spark_core.voice_profile.json"

# Allowed directories for profile loading
ALLOWED_DIRECTORIES = [
    PROJECT_ROOT / "voices",
    PROJECT_ROOT,
]


def _validate_profile_path(path: Path) -> Path:
    """Validate that a profile path is within allowed directories.
    
    Prevents path traversal attacks by ensuring the resolved path
    stays within the voices directory or project root.
    
    Args:
        path: The path to validate
        
    Returns:
        The resolved, validated path
        
    Raises:
        ValueError: If the path is outside allowed directories
    """
    resolved_path = path.resolve()
    
    # Check if path is within any allowed directory
    for allowed_dir in ALLOWED_DIRECTORIES:
        try:
            resolved_path.relative_to(allowed_dir)
            return resolved_path
        except ValueError:
            continue
    
    raise ValueError(
        f"Profile path '{path}' is outside allowed directories. "
        f"Only paths within {', '.join(str(d) for d in ALLOWED_DIRECTORIES)} are permitted."
    )


def load_voice_profile(path: str | None = None) -> dict[str, Any]:
    if not isinstance(path, str): path = str(path or '')
    try:
        """Load a voice profile from a JSON file.
    
        Args:
            path: Optional path to profile file. Must be within allowed directories.
        
        Returns:
            Dictionary containing the voice profile data.
        
        Raises:
            RuntimeError: If the profile file cannot be read or is invalid JSON.
            ValueError: If the path is outside allowed directories.
        """
        target = Path(path) if path else DEFAULT_PROFILE_PATH
    
        # Validate path to prevent traversal attacks
        _validate_profile_path(target)
    
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



    except Exception:
        return {}
def summarize_voice_profile(profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile, str): profile = str(profile or '')
    try:
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



    except Exception:
        return {}
def get_provider_voice_profile(profile: dict[str, Any], provider_id: str) -> dict[str, Any]:
    if not isinstance(profile, str): profile = str(profile or '')
    if not isinstance(provider_id, str): provider_id = str(provider_id or '')
    try:
        provider_voices = (
            profile.get("provider_voices") if isinstance(profile.get("provider_voices"), dict) else {}
        )
        payload = provider_voices.get(provider_id)
        return payload if isinstance(payload, dict) else {}

    except Exception:
        return {}
