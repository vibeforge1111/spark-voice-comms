from __future__ import annotations

import argparse
import base64
import hashlib
import importlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from uuid import uuid4
from typing import Any

from .profile import get_provider_voice_profile, load_voice_profile, summarize_voice_profile
from .runtime_state import state_from_speak, state_from_status, state_from_transcribe

DEFAULT_TRANSCRIPTION_MODEL = "whisper-1"
SUPPORTED_PROVIDER_KINDS = {"openai", "custom"}
SUPPORTED_FALLBACK_MODES = {"deterministic"}
DEFAULT_OPENAI_TRANSCRIPTION_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TTS_PROVIDER = "elevenlabs"
LOCAL_TTS_PROVIDER = "pyttsx3"
LOCAL_KOKORO_TTS_PROVIDER = "kokoro"
OPENAI_REALTIME_TTS_PROVIDER = "openai-realtime"
DEFAULT_ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"
DEFAULT_ELEVENLABS_MODEL_ID = "eleven_turbo_v2_5"
DEFAULT_ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"
DEFAULT_TELEGRAM_ELEVENLABS_OUTPUT_FORMAT = "opus_48000_64"
DEFAULT_OPENAI_REALTIME_WS_URL = "wss://api.openai.com/v1/realtime"
DEFAULT_OPENAI_REALTIME_MODEL_ID = "gpt-realtime-2"
DEFAULT_OPENAI_REALTIME_VOICE = "coral"
DEFAULT_OPENAI_REALTIME_SAMPLE_RATE = 24000
DEFAULT_OPENAI_REALTIME_TIMEOUT_SECONDS = 45
DEFAULT_OPENAI_REALTIME_INSTRUCTIONS = (
    "Read the exact input text aloud verbatim. Do not answer it, paraphrase it, summarize it, "
    "add words, remove words, or mention these instructions. Use natural prosody while preserving the wording."
)
OPENAI_REALTIME_PROVIDER_ALIASES = {OPENAI_REALTIME_TTS_PROVIDER, "gpt-realtime-2", "realtime", "openai-realtime-2"}
ENV_TTS_PROVIDER = "VOICE_TTS_PROVIDER"
ENV_TTS_BASE_URL = "VOICE_TTS_ELEVENLABS_BASE_URL"
ENV_TTS_MODEL_ID = "VOICE_TTS_ELEVENLABS_MODEL_ID"
ENV_TTS_VOICE_ID = "VOICE_TTS_ELEVENLABS_VOICE_ID"
ENV_TTS_VOICE_NAME = "VOICE_TTS_ELEVENLABS_VOICE_NAME"
ENV_LOCAL_TTS_VOICE_NAME = "VOICE_TTS_LOCAL_VOICE_NAME"
ENV_LOCAL_TTS_RATE = "VOICE_TTS_LOCAL_RATE"
ENV_LOCAL_TTS_VOLUME = "VOICE_TTS_LOCAL_VOLUME"
ENV_KOKORO_MODEL_PATH = "VOICE_TTS_KOKORO_MODEL_PATH"
ENV_KOKORO_VOICES_PATH = "VOICE_TTS_KOKORO_VOICES_PATH"
ENV_KOKORO_VOICE = "VOICE_TTS_KOKORO_VOICE"
ENV_KOKORO_SPEED = "VOICE_TTS_KOKORO_SPEED"
ENV_KOKORO_LANG = "VOICE_TTS_KOKORO_LANG"
ENV_OPENAI_REALTIME_SECRET_REF = "VOICE_TTS_OPENAI_REALTIME_SECRET_ENV_REF"
ENV_OPENAI_REALTIME_WS_URL = "VOICE_TTS_OPENAI_REALTIME_WS_URL"
ENV_OPENAI_REALTIME_MODEL_ID = "VOICE_TTS_OPENAI_REALTIME_MODEL_ID"
ENV_OPENAI_REALTIME_VOICE = "VOICE_TTS_OPENAI_REALTIME_VOICE"
ENV_OPENAI_REALTIME_REASONING_EFFORT = "VOICE_TTS_OPENAI_REALTIME_REASONING_EFFORT"
ENV_OPENAI_REALTIME_INSTRUCTIONS = "VOICE_TTS_OPENAI_REALTIME_INSTRUCTIONS"
ENV_OPENAI_REALTIME_TIMEOUT_SECONDS = "VOICE_TTS_OPENAI_REALTIME_TIMEOUT_SECONDS"
ENV_RUNTIME_STATE_PATH = "SPARK_VOICE_RUNTIME_STATE_PATH"
DEFAULT_KOKORO_VOICE = "af_sarah"
DEFAULT_KOKORO_LANG = "en-us"
VOICE_ENV_KEYS = {
    "OPENAI_API_KEY",
    "VOICE_TRANSCRIBE_PROVIDER",
    "VOICE_TRANSCRIBE_BASE_URL",
    "VOICE_TRANSCRIBE_SECRET_ENV_REF",
    "VOICE_TRANSCRIBE_LOCAL_MODEL",
    "VOICE_TRANSCRIBE_LOCAL_LANGUAGE",
    "VOICE_TRANSCRIBE_LOCAL_VAD_FILTER",
    "VOICE_TRANSCRIBE_LOCAL_BEAM_SIZE",
    "ELEVENLABS_API_KEY",
    ENV_TTS_PROVIDER,
    ENV_TTS_BASE_URL,
    ENV_TTS_MODEL_ID,
    ENV_TTS_VOICE_ID,
    ENV_TTS_VOICE_NAME,
    ENV_LOCAL_TTS_VOICE_NAME,
    ENV_LOCAL_TTS_RATE,
    ENV_LOCAL_TTS_VOLUME,
    ENV_KOKORO_MODEL_PATH,
    ENV_KOKORO_VOICES_PATH,
    ENV_KOKORO_VOICE,
    ENV_KOKORO_SPEED,
    ENV_KOKORO_LANG,
    ENV_OPENAI_REALTIME_SECRET_REF,
    ENV_OPENAI_REALTIME_WS_URL,
    ENV_OPENAI_REALTIME_MODEL_ID,
    ENV_OPENAI_REALTIME_VOICE,
    ENV_OPENAI_REALTIME_REASONING_EFFORT,
    ENV_OPENAI_REALTIME_INSTRUCTIONS,
    ENV_OPENAI_REALTIME_TIMEOUT_SECONDS,
}


def handle_voice_status_hook(payload: dict[str, Any]) -> dict[str, Any]:
    status = _build_voice_status(payload)
    profile_summary = summarize_voice_profile(load_voice_profile())
    runtime_state = state_from_status(status=status, profile_summary=profile_summary, payload=payload)
    if status.get("local_ready"):
        local_tts_ready = bool(status.get("local_tts_ready"))
        profile_name = str(profile_summary["profile_name"])
        tone_identity = str(profile_summary["tone_identity"]).replace("_", " ")
        lines = [
            "Local voice is ready." if local_tts_ready else "Local transcription is ready.",
            "",
            "I will listen with faster-whisper from this machine.",
        ]
        speech_status = str(status.get("speech_reply_status") or "").strip()
        if local_tts_ready and speech_status:
            lines.extend(["", f"Speech replies are {speech_status}."])
        provider_note = str(status.get("provider_note") or "").strip()
        if provider_note:
            lines.extend(
                [
                    "",
                    provider_note,
                ]
            )
        lines.extend(
            [
                "",
                f"Voice profile: {profile_name}, {tone_identity}.",
                "",
                (
                    "Next: send a short Telegram voice note, or ask me to say something with Kokoro."
                    if local_tts_ready
                    else "Next: send a short Telegram voice note to test local transcription."
                ),
            ]
        )
    else:
        lines = [
            "Voice chip is ready." if status["ready"] else "Voice chip is not ready yet.",
            f"Current state: {status['reason']}",
        ]
        lines.append(
            f"Voice profile: {profile_summary['profile_name']} "
            f"({profile_summary['tone_identity']}, default emotion {profile_summary['default_emotion']})."
        )
        if status["ready"]:
            lines.append("Next: send a Telegram voice note and I will route it through this chip.")
        else:
            lines.append(
                "Next: finish provider setup for voice transcription, then rerun `/voice`."
            )
    return {
        "returncode": 0,
        "stdout": status["reason"],
        "stderr": "",
        "metrics": {"ready": 1 if status["ready"] else 0},
        "result": {
            **status,
            "voice_profile": profile_summary,
            "runtime_state": runtime_state,
            "reply_text": "\n".join(lines),
        },
    }


def handle_voice_plan_hook(payload: dict[str, Any]) -> dict[str, Any]:
    profile_summary = summarize_voice_profile(load_voice_profile())
    reply_text = (
        "Telegram voice plan:\n"
        "1. transcribe Telegram voice/audio through `spark-voice-comms`.\n"
        "2. route the transcript through the same Builder Telegram runtime and saved persona.\n"
        f"3. add optional voice reply synthesis around the canonical `{profile_summary['profile_name']}` voice profile without bloating Builder.\n"
        "Next: validate `voice.status`, then dogfood real Telegram voice notes."
    )
    return {
        "returncode": 0,
        "stdout": "voice plan ready",
        "stderr": "",
        "metrics": {"plan_steps": 3},
        "result": {
            "reply_text": reply_text,
            "voice_profile": profile_summary,
            "steps": [
                "transcribe Telegram voice/audio through spark-voice-comms",
                "route the transcript through the same Builder Telegram runtime and saved persona",
                "add optional voice reply synthesis as a second hook around the canonical voice profile",
            ],
        },
    }


def handle_voice_onboard_hook(payload: dict[str, Any]) -> dict[str, Any]:
    snapshot = _build_onboarding_snapshot(payload)
    route = str(payload.get("route") or payload.get("preference") or "").strip().lower()
    provider_note = _voice_provider_note(payload)
    preference_note = _voice_preference_note(payload)
    if route in {"free", "local", "offline"}:
        recommended_path = "local_free"
        recommendation = _local_voice_recommendation(
            snapshot=snapshot,
            provider_note=provider_note,
            preference_note=preference_note,
        )
    elif route in {"paid", "production", "hosted"}:
        recommended_path = "paid_provider"
        recommendation = _paid_voice_recommendation(
            snapshot=snapshot,
            provider_note=provider_note,
            preference_note=preference_note,
        )
    else:
        recommended_path = "guided_choice"
        recommendation = _guided_voice_recommendation(
            snapshot=snapshot,
            provider_note=provider_note,
            preference_note=preference_note,
        )
    reply_text = _voice_onboarding_reply_text(
        recommended_path=recommended_path,
        snapshot=snapshot,
        provider_note=provider_note,
        preference_note=preference_note,
    )
    return {
        "returncode": 0,
        "stdout": recommended_path,
        "stderr": "",
        "metrics": {
            "local_ready": 1 if snapshot["local_stt"]["ready"] and snapshot["local_tts"]["ready"] else 0,
            "paid_ready": 1 if snapshot["paid_stt"]["ready"] and snapshot["paid_tts"]["ready"] else 0,
        },
        "result": {
            "reply_text": reply_text,
            "recommended_path": recommended_path,
            "next_step": _voice_onboarding_next_step(recommended_path=recommended_path, snapshot=snapshot),
            "snapshot": snapshot,
            "provider_note": provider_note,
            "preference_note": preference_note,
            "agent_prompts": [
                "voice onboard local",
                "voice onboard paid",
                "voice status",
                "voice plan",
            ],
        },
    }


def handle_voice_install_hook(payload: dict[str, Any]) -> dict[str, Any]:
    target = str(payload.get("target") or payload.get("provider") or "kokoro").strip().lower()
    target = target.replace("_", "-")
    if target in {"local", "local-voice", "local-stack", "local-voice-stack"}:
        return _install_local_voice_stack(payload)
    if target in {"stt", "local-stt", "transcription", "transcribe", "whisper", "faster-whisper"}:
        return _install_faster_whisper()
    if target in {"local-tts", "kokoro-onnx"}:
        target = LOCAL_KOKORO_TTS_PROVIDER
    if target != LOCAL_KOKORO_TTS_PROVIDER:
        raise ValueError("voice.install supports `kokoro`, `faster-whisper`, or `local`.")
    return _install_kokoro(payload)


def _install_kokoro(payload: dict[str, Any]) -> dict[str, Any]:
    target = LOCAL_KOKORO_TTS_PROVIDER
    if sys.version_info >= (3, 14):
        raise RuntimeError("kokoro-onnx currently requires Python <3.14. Use a Python 3.10-3.13 runtime.")
    was_ready = _local_kokoro_package_available()
    if was_ready:
        install_status = "already_installed"
        pip_tail: list[str] = []
    else:
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "kokoro-onnx>=0.5.0",
            "soundfile>=0.12",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
        pip_output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        pip_tail = _tail_nonempty_lines(pip_output, limit=8)
        if completed.returncode != 0:
            return {
                "returncode": 1,
                "stdout": "kokoro install failed",
                "stderr": "\n".join(pip_tail),
                "metrics": {"installed": 0, "already_installed": 0},
                "result": {
                    "reply_text": (
                        "Kokoro install failed in the local Python runtime.\n"
                        "I did not touch provider keys or model paths.\n"
                        "Next: check the local package error, then rerun `/voice install kokoro`."
                    ),
                    "target": target,
                    "python": sys.executable,
                    "installed": False,
                    "already_installed": False,
                    "pip_tail": pip_tail,
                },
            }
        install_status = "installed"
    is_ready = _local_kokoro_package_available()
    env_map = _safe_builder_env_map(payload)
    kokoro_ready = _local_kokoro_ready(env_map=env_map)
    reply_text = _kokoro_install_reply_text(install_status=install_status, kokoro_ready=kokoro_ready)
    return {
        "returncode": 0,
        "stdout": install_status,
        "stderr": "",
        "metrics": {"installed": 1 if is_ready else 0, "already_installed": 1 if was_ready else 0},
        "result": {
            "reply_text": reply_text,
            "target": target,
            "python": sys.executable,
            "installed": is_ready,
            "already_installed": was_ready,
            "kokoro_ready": kokoro_ready,
            "pip_tail": pip_tail,
        },
    }


def _install_faster_whisper() -> dict[str, Any]:
    was_ready = _local_faster_whisper_available()
    if was_ready:
        install_status = "already_installed"
        pip_tail: list[str] = []
    else:
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "faster-whisper>=1.0",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
        pip_output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        pip_tail = _tail_nonempty_lines(pip_output, limit=8)
        if completed.returncode != 0:
            return {
                "returncode": 1,
                "stdout": "faster-whisper install failed",
                "stderr": "\n".join(pip_tail),
                "metrics": {"installed": 0, "already_installed": 0, "stt_ready": 0},
                "result": {
                    "reply_text": (
                        "faster-whisper install failed in the local Python runtime.\n"
                        "I did not touch provider keys or voice settings.\n"
                        "Next: check the local package error, then rerun `/voice install faster-whisper`."
                    ),
                    "target": "faster-whisper",
                    "python": sys.executable,
                    "installed": False,
                    "already_installed": False,
                    "stt_ready": False,
                    "pip_tail": pip_tail,
                },
            }
        install_status = "installed"
    is_ready = _local_faster_whisper_available()
    return {
        "returncode": 0,
        "stdout": install_status,
        "stderr": "",
        "metrics": {"installed": 1 if is_ready else 0, "already_installed": 1 if was_ready else 0, "stt_ready": 1 if is_ready else 0},
        "result": {
            "reply_text": _faster_whisper_install_reply_text(install_status=install_status, stt_ready=is_ready),
            "target": "faster-whisper",
            "python": sys.executable,
            "installed": is_ready,
            "already_installed": was_ready,
            "stt_ready": is_ready,
            "pip_tail": pip_tail,
        },
    }


def _install_local_voice_stack(payload: dict[str, Any]) -> dict[str, Any]:
    stt = _install_faster_whisper()
    kokoro = _install_kokoro(payload)
    ok = stt.get("returncode") == 0 and kokoro.get("returncode") == 0
    stt_result = stt.get("result") if isinstance(stt.get("result"), dict) else {}
    kokoro_result = kokoro.get("result") if isinstance(kokoro.get("result"), dict) else {}
    stt_ready = bool(stt_result.get("stt_ready"))
    kokoro_installed = bool(kokoro_result.get("installed"))
    kokoro_ready = bool(kokoro_result.get("kokoro_ready"))
    reply_lines = [
        "Local voice package install completed." if ok else "Local voice package install partly failed.",
        f"Listening: {'ready via faster-whisper' if stt_ready else 'faster-whisper still needs attention'}.",
        f"Speaking: {'Kokoro ready with local voice files' if kokoro_ready else 'Kokoro package installed; local voice files may still need connecting' if kokoro_installed else 'Kokoro still needs attention'}.",
        "",
        "Next: rerun `/voice onboard local`, then `/voice`.",
    ]
    return {
        "returncode": 0 if ok else 1,
        "stdout": "local_installed" if ok else "local_install_partial",
        "stderr": "\n".join(
            line
            for result in (stt, kokoro)
            for line in _tail_nonempty_lines(str(result.get("stderr") or ""), limit=4)
        ),
        "metrics": {
            "installed": 1 if stt_ready and kokoro_installed else 0,
            "stt_ready": 1 if stt_ready else 0,
            "kokoro_installed": 1 if kokoro_installed else 0,
            "kokoro_ready": 1 if kokoro_ready else 0,
        },
        "result": {
            "reply_text": "\n".join(reply_lines),
            "target": "local",
            "python": sys.executable,
            "installed": bool(stt_ready and kokoro_installed),
            "stt_ready": stt_ready,
            "kokoro_installed": kokoro_installed,
            "kokoro_ready": kokoro_ready,
            "stt": stt_result,
            "kokoro": kokoro_result,
        },
    }


def _voice_onboarding_reply_text(
    *,
    recommended_path: str,
    snapshot: dict[str, Any],
    provider_note: dict[str, str],
    preference_note: dict[str, str],
) -> str:
    context_line = _voice_context_line(provider_note=provider_note, preference_note=preference_note)
    next_step = _voice_onboarding_next_step(recommended_path=recommended_path, snapshot=snapshot)
    if recommended_path == "local_free":
        if snapshot["local_stt"]["ready"] and snapshot["local_tts"]["ready"]:
            voice_name = "Kokoro" if snapshot["local_tts"].get("provider") == LOCAL_KOKORO_TTS_PROVIDER else "the local system voice"
            lines = [
                f"Nice, local voice is ready: faster-whisper for listening, {voice_name} for replies.",
                "",
                "Ask me for one short voice reply, then send a quick Telegram voice note.",
                "After that, run `/voice self-test` to confirm the proof trail.",
            ]
        elif snapshot["local_stt"]["ready"]:
            lines = [
                "Local listening is ready. The speaking voice is the only missing piece.",
                "I would finish Kokoro next because it gives Spark a much nicer local voice without sending keys through Telegram.",
                context_line,
                next_step,
            ]
        else:
            lines = [
                "I would start with the local voice path for this Spark.",
                "It keeps the first setup private and free, then we can add a hosted voice later if you want more polish.",
                context_line,
                next_step,
            ]
        return "\n".join(line for line in lines if line is not None)
    if recommended_path == "paid_provider":
        if snapshot["paid_tts"].get("provider") == OPENAI_REALTIME_TTS_PROVIDER:
            lead = "GPT Realtime 2 is configured for hosted voice replies."
            recommendation = "I would use it for the more expressive voice-agent path, while keeping ElevenLabs as the simpler classic TTS fallback."
        else:
            lead = "For paid voice, I would optimize for reliable Telegram delivery first, then tune the voice character."
            recommendation = (
                "My current recommendation is GPT Realtime 2 for a premium voice-agent feel, ElevenLabs for simpler hosted TTS, "
                "and MiniMax or Z.ai only through explicit adapters once they are verified."
            )
        lines = [
            lead,
            recommendation,
            context_line,
            "",
            next_step,
        ]
        return "\n".join(line for line in lines if line is not None)
    lines = [
        "I can help set up voice in the direction that fits this Spark best.",
        "Choose local/private for faster-whisper plus Kokoro, or hosted/premium for ElevenLabs after listening is verified.",
        context_line,
        "",
        next_step,
    ]
    return "\n".join(line for line in lines if line is not None)


def _voice_context_line(*, provider_note: dict[str, str], preference_note: dict[str, str]) -> str | None:
    preference = preference_note.get("preference")
    if preference == "local":
        return "This also matches the saved preference signal I can see: local/private tooling when it is good enough."
    if preference == "paid_quality":
        return "This matches the saved preference signal I can see: quality-first voice is worth a paid provider."
    provider = provider_note.get("provider")
    if provider and provider not in {"unknown", "openai"}:
        label = provider_note.get("label") or provider
        return f"I can see this Spark is currently running through {label}; I will not assume that provider has voice until its speech endpoint is verified."
    return "No API keys belong in Telegram; keep provider secrets in Spark's local config or secret layer."


def _safe_builder_env_map(payload: dict[str, Any]) -> dict[str, str]:
    env_file_path = str(payload.get("builder_env_file_path") or "").strip()
    try:
        return _runtime_env_map(env_file_path=env_file_path or None)
    except Exception:
        return _process_voice_env_map()


def _kokoro_install_reply_text(*, install_status: str, kokoro_ready: bool) -> str:
    installed_line = "Kokoro is already installed for this Spark." if install_status == "already_installed" else "Done, Kokoro is installed for this Spark."
    if kokoro_ready:
        ready_line = (
            "Nice, Kokoro is already installed for this Spark. The local voice files are connected too."
            if install_status == "already_installed"
            else "Nice, Kokoro is installed for this Spark. The local voice files are connected too."
        )
        return "\n".join(
            [
                ready_line,
                "",
                "You can test it with `/voice onboard local`.",
            ]
        )
    return "\n".join(
        [
            installed_line,
            "One local setup step is still needed: connect the Kokoro model file and voices file on this computer.",
            "Keep that part outside Telegram. Once those paths are saved in Spark's local config, I can use Kokoro for voice replies.",
            "Then rerun `/voice onboard local`.",
        ]
    )


def _faster_whisper_install_reply_text(*, install_status: str, stt_ready: bool) -> str:
    if stt_ready:
        ready_line = (
            "faster-whisper is already installed for this Spark."
            if install_status == "already_installed"
            else "Done, faster-whisper is installed for this Spark."
        )
        return "\n".join(
            [
                ready_line,
                "",
                "You can test listening with `/voice`, then send one short Telegram voice note.",
            ]
        )
    return "\n".join(
        [
            "faster-whisper was installed, but the package is not importable yet in this Python runtime.",
            "Restart the Spark runtime if needed, then rerun `/voice install faster-whisper`.",
        ]
    )


def _voice_preference_note(payload: dict[str, Any]) -> dict[str, str]:
    advisor_context = payload.get("advisor_context") if isinstance(payload.get("advisor_context"), dict) else {}
    preferences = advisor_context.get("preferences") if isinstance(advisor_context.get("preferences"), list) else []
    normalized: list[dict[str, str]] = []
    for item in preferences:
        if not isinstance(item, dict):
            continue
        value = " ".join(str(item.get("value") or item.get("summary") or "").split())
        source = " ".join(str(item.get("source") or item.get("source_kind") or "").split())
        if value:
            normalized.append({"value": value, "source": source or "source-labeled context"})
    joined = " ".join(item["value"].lower() for item in normalized[:5])
    if any(token in joined for token in ("local", "offline", "privacy", "private", "open source", "self host")):
        return {
            "preference": "local",
            "note": "I can see source-labeled preference context leaning local/private, so I would weight the free local path higher.",
        }
    if any(token in joined for token in ("quality", "premium", "natural voice", "paid", "elevenlabs", "minimax")):
        return {
            "preference": "paid_quality",
            "note": "I can see source-labeled preference context leaning toward higher voice quality, so I would weight the paid TTS path higher.",
        }
    return {
        "preference": "unknown",
        "note": "",
    }


def _voice_provider_note(payload: dict[str, Any]) -> dict[str, str]:
    provider = payload.get("provider") if isinstance(payload.get("provider"), dict) else {}
    provider_id = str(provider.get("provider_id") or "").strip().lower()
    provider_kind = str(provider.get("provider_kind") or "").strip().lower()
    base_url = str(provider.get("base_url") or "").strip().lower()
    default_model = str(provider.get("default_model") or "").strip()
    label = provider_id or provider_kind or "unknown"
    if provider_kind == "minimax" or provider_id == "minimax":
        return {
            "provider": "minimax",
            "label": "MiniMax",
            "note": (
                "I can see a MiniMax-flavored runtime, so I would treat MiniMax as a strong future "
                "TTS option for characterful replies. The current voice chip still needs a dedicated "
                "MiniMax speech adapter before I call it ready."
            ),
        }
    if provider_id in {"zai", "z.ai", "glm"} or "bigmodel" in base_url or "zhipu" in base_url:
        return {
            "provider": "zai",
            "label": "Z.ai",
            "note": (
                "I can see a Z.ai/GLM-shaped runtime, so GLM-TTS is a natural future fit. "
                "Today I would pair this with local or OpenAI-compatible STT until the Z.ai voice adapter lands."
            ),
        }
    if provider_kind == "openai" or provider_id == "openai":
        return {
            "provider": "openai",
            "label": "OpenAI-compatible",
            "note": "Your active provider shape is already the easiest path for hosted transcription.",
        }
    if label != "unknown":
        model_part = f" ({default_model})" if default_model else ""
        return {
            "provider": label,
            "label": f"{label}{model_part}",
            "note": (
                f"I can see `{label}` as the active runtime provider. I will not assume it can do voice "
                "unless its STT/TTS endpoint has been verified."
            ),
        }
    return {
        "provider": "unknown",
        "label": "unknown",
        "note": "I do not have enough provider evidence to personalize the hosted path yet.",
    }


def _local_voice_recommendation(
    *,
    snapshot: dict[str, Any],
    provider_note: dict[str, str],
    preference_note: dict[str, str],
) -> str:
    if snapshot["local_stt"]["ready"] and snapshot["local_tts"]["ready"]:
        lead = "For this Spark, I would start local: the private/free path is already in reach."
    elif snapshot["local_stt"]["ready"]:
        lead = "For this Spark, I would still lean local first: transcription is already local-ready, and TTS is the missing piece."
    else:
        lead = "For local voice, I would build the private/free path first and keep hosted providers optional."
    preference_line = f"\n{preference_note['note']}" if preference_note.get("note") else ""
    return (
        f"{lead}\n"
        f"{provider_note['note']}\n"
        "No API keys belong in Telegram; local setup should happen through the machine or Spark's secret layer."
        f"{preference_line}"
    )


def _paid_voice_recommendation(
    *,
    snapshot: dict[str, Any],
    provider_note: dict[str, str],
    preference_note: dict[str, str],
) -> str:
    if provider_note["provider"] == "minimax":
        lead = "For high-quality paid voice, MiniMax is worth supporting, but I would not mark it ready until the speech adapter is real."
    elif provider_note["provider"] == "zai":
        lead = "For a Z.ai/GLM-centered Spark, I would keep GLM-TTS on the roadmap and use a verified voice path today."
    elif snapshot["paid_tts"].get("provider") == OPENAI_REALTIME_TTS_PROVIDER:
        lead = "For paid voice, GPT Realtime 2 is already configured, so I would use that for the more voice-agent-like path."
    elif snapshot["paid_stt"]["ready"] or snapshot["paid_tts"]["ready"]:
        lead = "For paid voice, I would build on the hosted pieces already visible instead of starting from scratch."
    else:
        lead = "For paid voice, I would optimize for reliable Telegram delivery first, then voice character."
    if snapshot["paid_tts"].get("provider") == OPENAI_REALTIME_TTS_PROVIDER:
        recommendation = "My recommendation here is GPT Realtime 2 for expressive hosted voice, while keeping ElevenLabs as the simpler classic TTS fallback."
    else:
        recommendation = (
            "My default recommendation today is GPT Realtime 2 for a premium voice-agent feel, ElevenLabs for simpler hosted TTS, "
            "and MiniMax or Z.ai only through explicit adapters once they are verified."
        )
    return (
        f"{lead}\n"
        f"{provider_note['note']}\n"
        f"{recommendation}"
        + (f"\n{preference_note['note']}" if preference_note.get("note") else "")
    )


def _guided_voice_recommendation(
    *,
    snapshot: dict[str, Any],
    provider_note: dict[str, str],
    preference_note: dict[str, str],
) -> str:
    if preference_note.get("preference") == "local":
        lead = "Because the available preference context leans local/private, I would start with the local path."
    elif preference_note.get("preference") == "paid_quality":
        lead = "Because the available preference context leans quality-first, I would plan a paid TTS path after STT is verified."
    elif snapshot["local_stt"]["ready"] and not snapshot["paid_tts"]["ready"]:
        lead = "Given what I can see, I would start with local input and add premium voice output later."
    elif snapshot["paid_stt"]["ready"] and snapshot["paid_tts"]["ready"]:
        lead = "Given what I can see, the paid/provider path is closest to a polished Telegram experience."
    else:
        lead = "I would choose the path based on what the user values most: privacy and zero spend, or premium voice quality."
    return f"{lead}\n{provider_note['note']}"


def _voice_onboarding_next_step(*, recommended_path: str, snapshot: dict[str, Any]) -> str:
    if recommended_path == "local_free":
        if snapshot["local_stt"]["ready"] and snapshot["local_tts"]["ready"]:
            return "Next: ask for one short voice reply, send a quick Telegram voice note, then run `/voice self-test`."
        return "Next: run `/voice install local`, then rerun `/voice onboard local`."
    if recommended_path == "paid_provider":
        if snapshot["paid_stt"]["ready"] and snapshot["paid_tts"]["ready"]:
            return "Next: verify `/voice status`, ask for one short paid voice reply, then run `/voice self-test`."
        return "Next: configure provider secrets locally or in Spark's secret layer; do not paste keys into Telegram. Then run `/voice self-test` after one voice note."
    return "Next: reply `local/private` or `highest-quality voice`; I will recommend the setup."


def handle_voice_speak_hook(payload: dict[str, Any]) -> dict[str, Any]:
    profile = load_voice_profile()
    profile_summary = summarize_voice_profile(profile)
    request = _resolve_tts_request(payload, profile=profile)
    synthesize_started = time.perf_counter()
    if request["provider_id"] == LOCAL_KOKORO_TTS_PROVIDER:
        audio_bytes, resolved_voice_id = _synthesize_with_kokoro(request=request)
    elif request["provider_id"] == LOCAL_TTS_PROVIDER:
        audio_bytes, resolved_voice_id = _synthesize_with_pyttsx3(request=request)
    elif request["provider_id"] == OPENAI_REALTIME_TTS_PROVIDER:
        audio_bytes, resolved_voice_id = _synthesize_with_openai_realtime(request=request)
    else:
        audio_bytes, resolved_voice_id = _synthesize_with_elevenlabs(request=request)
    synthesize_ms = _elapsed_ms(synthesize_started)
    runtime_payload = {
        **payload,
        "latency": _merge_latency(payload.get("latency"), synthesize_ms=synthesize_ms),
    }
    runtime_state = state_from_speak(
        request=request,
        resolved_voice_id=resolved_voice_id,
        audio_bytes=audio_bytes,
        profile_summary=profile_summary,
        payload=runtime_payload,
    )
    delivery_trace = _build_speak_delivery_trace(
        request=request,
        resolved_voice_id=resolved_voice_id,
        audio_bytes=audio_bytes,
        runtime_state=runtime_state,
    )
    coherence = _build_speak_coherence(request=request, payload=payload)
    return {
        "returncode": 0,
        "stdout": f"{request['provider_id']}:{resolved_voice_id}",
        "stderr": "",
        "metrics": {
            "audio_bytes": len(audio_bytes),
            "text_characters": len(request["text"]),
            "synthesize_ms": synthesize_ms,
        },
        "result": {
            "provider_id": request["provider_id"],
            "voice_id": resolved_voice_id,
            "model_id": request["model_id"],
            "mime_type": request["mime_type"],
            "filename": f"voice-reply-{uuid4().hex[:8]}{request['file_extension']}",
            "voice_compatible": bool(request["voice_compatible"]),
            "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
            "voice_profile": profile_summary,
            "runtime_state": runtime_state,
            "delivery_trace": delivery_trace,
            "coherence": coherence,
        },
    }


def handle_voice_transcribe_hook(payload: dict[str, Any]) -> dict[str, Any]:
    transcribe_started = time.perf_counter()
    audio_base64 = str(payload.get("audio_base64") or "").strip()
    if not audio_base64:
        raise ValueError("voice.transcribe requires audio_base64.")
    audio_bytes = base64.b64decode(audio_base64.encode("ascii"))
    filename = str(payload.get("filename") or "telegram-voice.ogg").strip() or "telegram-voice.ogg"
    mime_type = str(payload.get("mime_type") or "application/octet-stream").strip() or "application/octet-stream"
    fallback_mode = _resolve_fallback_mode(payload)
    transcription_mode = _transcription_provider_mode(payload)
    if transcription_mode in {"auto", "local"} and _local_faster_whisper_available():
        try:
            transcript_text = _transcribe_with_local_faster_whisper(
                payload=payload,
                audio_bytes=audio_bytes,
                filename=filename,
            )
        except Exception as exc:
            if fallback_mode == "deterministic":
                return _with_transcribe_runtime_state(
                    _deterministic_transcribe_response(audio_bytes=audio_bytes, filename=filename, reason=str(exc)),
                    payload=payload,
                    audio_bytes=len(audio_bytes),
                    started_at=transcribe_started,
                )
            raise RuntimeError(
                "Local faster-whisper transcription failed before any hosted transcription call was made. "
                "Fix local STT, or set VOICE_TRANSCRIBE_PROVIDER=openai to opt into hosted transcription."
            ) from exc
        else:
            return _with_transcribe_runtime_state({
                "returncode": 0,
                "stdout": transcript_text,
                "stderr": "",
                "metrics": {
                    "transcript_characters": len(transcript_text),
                    "audio_bytes": len(audio_bytes),
                    "local_first": 1,
                },
                "result": {
                    "transcript_text": transcript_text,
                    "provider_id": "local_faster_whisper",
                    "model": _resolve_local_faster_whisper_model(payload),
                    "mode": "local_faster_whisper",
                },
            }, payload=payload, audio_bytes=len(audio_bytes), started_at=transcribe_started)
    if transcription_mode in {"auto", "local"}:
        raise ValueError(
            "Local faster-whisper transcription is the default Telegram voice path, but `faster_whisper` is not installed. "
            "Install `spark-voice-comms[local-stt]`, or set VOICE_TRANSCRIBE_PROVIDER=openai to explicitly opt into hosted transcription."
        )
    try:
        provider = _resolve_provider(payload)
        transcript_text = _transcribe_with_provider(
            provider=provider,
            audio_bytes=audio_bytes,
            filename=filename,
            mime_type=mime_type,
        )
    except Exception as exc:
        if fallback_mode == "deterministic":
            return _with_transcribe_runtime_state(
                _deterministic_transcribe_response(audio_bytes=audio_bytes, filename=filename, reason=str(exc)),
                payload=payload,
                audio_bytes=len(audio_bytes),
                started_at=transcribe_started,
            )
        if _local_faster_whisper_available():
            transcript_text = _transcribe_with_local_faster_whisper(
                payload=payload,
                audio_bytes=audio_bytes,
                filename=filename,
            )
            return _with_transcribe_runtime_state({
                "returncode": 0,
                "stdout": transcript_text,
                "stderr": "",
                "metrics": {
                    "transcript_characters": len(transcript_text),
                    "audio_bytes": len(audio_bytes),
                    "fallback_used": 1,
                },
                "result": {
                    "transcript_text": transcript_text,
                    "provider_id": "local_faster_whisper",
                    "model": _resolve_local_faster_whisper_model(payload),
                    "mode": "local_faster_whisper",
                    "fallback_reason": str(exc),
                },
            }, payload=payload, audio_bytes=len(audio_bytes), started_at=transcribe_started)
        raise
    return _with_transcribe_runtime_state({
        "returncode": 0,
        "stdout": transcript_text,
        "stderr": "",
        "metrics": {
            "transcript_characters": len(transcript_text),
            "audio_bytes": len(audio_bytes),
        },
        "result": {
            "transcript_text": transcript_text,
            "provider_id": provider["provider_id"],
            "model": DEFAULT_TRANSCRIPTION_MODEL,
            "mode": "provider",
        },
    }, payload=payload, audio_bytes=len(audio_bytes), started_at=transcribe_started)


def _build_voice_status(payload: dict[str, Any]) -> dict[str, Any]:
    env_file_path = str(payload.get("builder_env_file_path") or "").strip()
    env_map = _process_voice_env_map()
    if env_file_path:
        try:
            env_map.update({key: value for key, value in _read_env_map(env_file_path=env_file_path).items() if value})
        except Exception:
            pass
    transcription_mode = _transcription_provider_mode(payload)
    local_stt_ready = _local_faster_whisper_available()
    local_tts_status = _local_tts_status(env_map=env_map)
    active_tts_status = _active_tts_status(env_map=env_map, local_tts_status=local_tts_status)
    if transcription_mode in {"auto", "local"} and not local_stt_ready:
        return {
            "ready": False,
            "local_ready": False,
            "local_tts_ready": bool(local_tts_status["ready"]),
            "local_tts_provider": str(local_tts_status["provider"]),
            "tts_ready": bool(active_tts_status["ready"]),
            "tts_provider_id": str(active_tts_status["provider"]),
            "tts_status": str(active_tts_status["status"]),
            "speech_reply_status": str(local_tts_status["status"]),
            "reason": (
                "local faster-whisper transcription is the default Telegram voice path, "
                "but `faster_whisper` is not installed"
            ),
            "provider_id": "local_faster_whisper",
            "provider_kind": "local",
            "model": _resolve_local_faster_whisper_model(payload),
        }
    if local_stt_ready and transcription_mode in {"auto", "local"}:
        provider_note = (
            "Hosted transcription is configured, but the default Telegram path will stay on local faster-whisper. "
            "Set VOICE_TRANSCRIBE_PROVIDER=openai to opt into hosted STT."
        )
        provider_id = None
        provider_kind = None
        try:
            provider = _resolve_provider(payload)
            provider_id = provider["provider_id"]
            provider_kind = provider["provider_kind"]
            if provider["provider_kind"] == "custom":
                provider_note = (
                    "Custom provider transcription compatibility is not verified yet, so local faster-whisper will be used."
                )
        except Exception as exc:
            provider_note = f"Hosted transcription provider is not configured; local faster-whisper will be used. Detail: {exc}"
        return {
            "ready": True,
            "local_ready": True,
            "local_tts_ready": bool(local_tts_status["ready"]),
            "local_tts_provider": str(local_tts_status["provider"]),
            "tts_ready": bool(active_tts_status["ready"]),
            "tts_provider_id": str(active_tts_status["provider"]),
            "tts_status": str(active_tts_status["status"]),
            "speech_reply_status": str(local_tts_status["status"]),
            "reason": f"local transcription is configured via faster-whisper using model {_resolve_local_faster_whisper_model(payload)}",
            "provider_note": provider_note,
            "provider_id": "local_faster_whisper",
            "provider_kind": "local",
            "hosted_provider_id": provider_id,
            "hosted_provider_kind": provider_kind,
            "model": _resolve_local_faster_whisper_model(payload),
        }
    try:
        provider = _resolve_provider(payload)
    except Exception as exc:
        return {
            "ready": False,
            "local_ready": False,
            "local_tts_ready": bool(local_tts_status["ready"]),
            "local_tts_provider": str(local_tts_status["provider"]),
            "tts_ready": bool(active_tts_status["ready"]),
            "tts_provider_id": str(active_tts_status["provider"]),
            "tts_status": str(active_tts_status["status"]),
            "reason": str(exc),
            "provider_id": None,
            "provider_kind": None,
            "model": None,
        }
    if provider["provider_kind"] == "custom":
        return {
            "ready": False,
            "local_ready": False,
            "local_tts_ready": bool(local_tts_status["ready"]),
            "local_tts_provider": str(local_tts_status["provider"]),
            "tts_ready": bool(active_tts_status["ready"]),
            "tts_provider_id": str(active_tts_status["provider"]),
            "tts_status": str(active_tts_status["status"]),
            "reason": (
                "custom provider transcription compatibility is not verified yet. "
                "This chip expects an OpenAI-compatible `/audio/transcriptions` endpoint."
            ),
            "provider_id": provider["provider_id"],
            "provider_kind": provider["provider_kind"],
            "model": DEFAULT_TRANSCRIPTION_MODEL,
        }
    return {
        "ready": True,
        "local_ready": False,
        "local_tts_ready": bool(local_tts_status["ready"]),
        "local_tts_provider": str(local_tts_status["provider"]),
        "tts_ready": bool(active_tts_status["ready"]),
        "tts_provider_id": str(active_tts_status["provider"]),
        "tts_status": str(active_tts_status["status"]),
        "reason": (
            f"transcription is configured via {provider['provider_id']} "
            f"using model {DEFAULT_TRANSCRIPTION_MODEL}"
            + (" with local faster-whisper fallback available" if _local_faster_whisper_available() else "")
        ),
        "provider_id": provider["provider_id"],
        "provider_kind": provider["provider_kind"],
        "model": DEFAULT_TRANSCRIPTION_MODEL,
    }


def _build_onboarding_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    env_file_path = str(payload.get("builder_env_file_path") or "").strip()
    env_map: dict[str, str] = _process_voice_env_map()
    env_note = "no Builder env file provided"
    if env_file_path:
        try:
            env_map.update({key: value for key, value in _read_env_map(env_file_path=env_file_path).items() if value})
            env_note = "Builder env file read"
        except Exception as exc:
            env_note = f"Builder env file unavailable: {exc}"
    local_stt_ready = _local_faster_whisper_available()
    local_tts_status = _local_tts_status(env_map=env_map)
    local_tts_ready = local_tts_status["ready"]
    paid_stt_ready = bool(env_map.get("OPENAI_API_KEY") or env_map.get("VOICE_TRANSCRIBE_SECRET_ENV_REF"))
    paid_tts_status = _paid_tts_status(env_map=env_map)
    paid_tts_ready = paid_tts_status["ready"]
    return {
        "env": {"status": env_note, "provided": bool(env_file_path)},
        "local_stt": {
            "ready": local_stt_ready,
            "status": "ready via faster-whisper" if local_stt_ready else "install optional `faster-whisper` for offline STT",
            "cost": "free/local",
        },
        "local_tts": {
            "ready": local_tts_ready,
            "status": local_tts_status["status"],
            "provider": local_tts_status["provider"],
            "cost": "free/local",
        },
        "paid_stt": {
            "ready": paid_stt_ready,
            "status": "configured for OpenAI-compatible STT" if paid_stt_ready else "add OpenAI-compatible STT env refs",
            "cost": "provider usage",
        },
        "paid_tts": {
            "ready": paid_tts_ready,
            "status": paid_tts_status["status"],
            "provider": paid_tts_status["provider"],
            "cost": "provider usage",
        },
    }


def _local_tts_status(*, env_map: dict[str, str]) -> dict[str, Any]:
    if _local_kokoro_ready(env_map=env_map):
        return {
            "ready": True,
            "provider": LOCAL_KOKORO_TTS_PROVIDER,
            "status": "ready via Kokoro local neural TTS",
        }
    if _local_kokoro_package_available():
        return {
            "ready": False,
            "provider": LOCAL_KOKORO_TTS_PROVIDER,
            "status": (
                f"configure {ENV_KOKORO_MODEL_PATH} and {ENV_KOKORO_VOICES_PATH} "
                "for Kokoro local neural TTS"
            ),
        }
    if _local_pyttsx3_available():
        return {
            "ready": True,
            "provider": LOCAL_TTS_PROVIDER,
            "status": "ready via pyttsx3 basic system TTS",
        }
    return {
        "ready": False,
        "provider": "none",
        "status": "install optional Kokoro for better offline TTS, or `pyttsx3` for basic system voices",
    }


def _paid_tts_status(*, env_map: dict[str, str]) -> dict[str, Any]:
    if env_map.get("ELEVENLABS_API_KEY") and env_map.get(ENV_TTS_VOICE_ID):
        return {
            "ready": True,
            "provider": "elevenlabs",
            "status": "configured for ElevenLabs TTS",
        }
    openai_secret_ref = env_map.get(ENV_OPENAI_REALTIME_SECRET_REF) or "OPENAI_API_KEY"
    openai_realtime_selected = str(env_map.get(ENV_TTS_PROVIDER) or "").strip().lower() in OPENAI_REALTIME_PROVIDER_ALIASES
    if openai_realtime_selected and env_map.get(openai_secret_ref):
        return {
            "ready": True,
            "provider": OPENAI_REALTIME_TTS_PROVIDER,
            "status": "configured for OpenAI GPT Realtime 2 voice",
        }
    return {
        "ready": False,
        "provider": "none",
        "status": f"add ElevenLabs voice settings, or set {ENV_TTS_PROVIDER}=openai-realtime with an OpenAI key for GPT Realtime 2",
    }


def _active_tts_status(*, env_map: dict[str, str], local_tts_status: dict[str, Any]) -> dict[str, Any]:
    selected_provider = str(env_map.get(ENV_TTS_PROVIDER) or "").strip().lower()
    paid_tts_status = _paid_tts_status(env_map=env_map)
    if selected_provider in {"kokoro", "kokoro-onnx", "local-kokoro", "pyttsx3", "local"}:
        return local_tts_status
    if selected_provider in {"elevenlabs", *OPENAI_REALTIME_PROVIDER_ALIASES}:
        return paid_tts_status
    if local_tts_status.get("ready"):
        return local_tts_status
    return paid_tts_status


def _build_speak_delivery_trace(
    *,
    request: dict[str, Any],
    resolved_voice_id: str,
    audio_bytes: bytes,
    runtime_state: dict[str, Any],
) -> dict[str, Any]:
    delivery = runtime_state["telegram_delivery"]
    status = str(delivery.get("last_send_voice_status") or "unknown")
    failure_stage = "" if status == "success" else "host_delivery"
    if status == "unknown":
        failure_stage = "not_attempted_by_chip"
    return {
        "provider_id": request["provider_id"],
        "voice_id_masked": runtime_state["tts"]["voice_id_masked"],
        "voice_id_fingerprint": runtime_state["tts"]["voice_id_fingerprint"],
        "mime_type": request["mime_type"],
        "voice_compatible": bool(request["voice_compatible"]),
        "audio_bytes": len(audio_bytes),
        "synthesis_status": "success",
        "telegram_delivery_status": status,
        "telegram_delivery_ready": bool(delivery.get("ready")),
        "failure_stage": failure_stage,
        "failure_reason": str(delivery.get("last_failure_reason") or ""),
        "delivery_boundary": (
            "spark-voice-comms produced audio bytes; Telegram delivery is only proven after the host records sendVoice success."
        ),
    }


def _build_speak_coherence(*, request: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    caption_text = str(payload.get("caption_text") or "").strip()
    spoken_text = str(request["text"])
    mode = str(payload.get("coherence_mode") or "exact").strip() or "exact"
    caption_fingerprint = _text_fingerprint(caption_text)
    spoken_fingerprint = _text_fingerprint(spoken_text)
    if caption_text:
        check = "passed" if caption_text == spoken_text or mode == "caption_preview" else "not_run"
    else:
        check = "passed"
    return {
        "mode": mode,
        "spoken_text_characters": len(spoken_text),
        "spoken_text_fingerprint": spoken_fingerprint,
        "caption_text_characters": len(caption_text),
        "caption_text_fingerprint": caption_fingerprint,
        "caption_matches_spoken": bool(caption_text and caption_text == spoken_text),
        "check": check,
        "policy": "/voice speak reads exact supplied text; /voice ask must pass an already-generated answer into voice.speak.",
    }


def _merge_latency(latency_payload: Any, **updates: int) -> dict[str, int]:
    latency = latency_payload if isinstance(latency_payload, dict) else {}
    merged: dict[str, int] = {}
    for key, value in latency.items():
        try:
            merged[str(key)] = max(0, int(float(value)))
        except (TypeError, ValueError):
            continue
    for key, value in updates.items():
        merged[key] = max(0, int(value))
    return merged


def _elapsed_ms(started_at: float) -> int:
    return max(0, int((time.perf_counter() - started_at) * 1000))


def _text_fingerprint(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _resolve_provider(payload: dict[str, Any]) -> dict[str, str]:
    dedicated_provider = _resolve_dedicated_transcription_provider(payload)
    if dedicated_provider is not None:
        return dedicated_provider
    provider_error = str(payload.get("provider_error") or "").strip()
    if provider_error:
        raise ValueError(provider_error)
    provider = payload.get("provider")
    if not isinstance(provider, dict):
        raise ValueError("Builder did not provide a voice transcription provider payload.")
    provider_id = str(provider.get("provider_id") or "").strip()
    provider_kind = str(provider.get("provider_kind") or "").strip()
    auth_method = str(provider.get("auth_method") or "").strip()
    execution_transport = str(provider.get("execution_transport") or "").strip()
    base_url = str(provider.get("base_url") or "").strip()
    secret_env_ref = str(provider.get("secret_env_ref") or "").strip()
    env_file_path = str(payload.get("builder_env_file_path") or "").strip()
    if provider_kind not in SUPPORTED_PROVIDER_KINDS:
        raise ValueError(f"Active provider '{provider_id or provider_kind or 'unknown'}' does not support direct voice transcription in this runtime.")
    if execution_transport and execution_transport != "direct_http":
        raise ValueError(
            f"Active provider '{provider_id or provider_kind or 'unknown'}' uses unsupported execution transport '{execution_transport}'."
        )
    if auth_method != "api_key_env":
        raise ValueError(
            f"Active provider '{provider_id or provider_kind or 'unknown'}' uses unsupported auth method '{auth_method or 'unknown'}' for voice transcription."
        )
    if not base_url:
        raise ValueError(f"Active provider '{provider_id or provider_kind or 'unknown'}' has no base URL configured.")
    if not env_file_path:
        raise ValueError("Builder did not provide an env file path for voice transcription.")
    if not secret_env_ref:
        raise ValueError(f"Active provider '{provider_id or provider_kind or 'unknown'}' has no env secret reference configured.")
    secret_value = _read_env_value(env_file_path=env_file_path, key=secret_env_ref)
    if not secret_value:
        raise ValueError(
            f"Active provider '{provider_id or provider_kind or 'unknown'}' is missing secret value for env ref '{secret_env_ref}'."
        )
    return {
        "provider_id": provider_id,
        "provider_kind": provider_kind,
        "base_url": base_url,
        "secret_value": secret_value,
    }


def _resolve_dedicated_transcription_provider(payload: dict[str, Any]) -> dict[str, str] | None:
    env_file_path = str(payload.get("builder_env_file_path") or "").strip()
    env_map = _runtime_env_map(env_file_path=env_file_path or None)
    provider_id = str(env_map.get("VOICE_TRANSCRIBE_PROVIDER") or "").strip().lower()
    normalized_provider_id = provider_id.replace("_", "-")
    if normalized_provider_id in {"auto", "default"}:
        provider_id = ""
    elif normalized_provider_id in {"local", "offline", "faster-whisper", "local-faster-whisper"}:
        return None
    elif normalized_provider_id in {"builder", "provider", "configured-provider"}:
        return None
    base_url = str(env_map.get("VOICE_TRANSCRIBE_BASE_URL") or "").strip()
    secret_env_ref = str(env_map.get("VOICE_TRANSCRIBE_SECRET_ENV_REF") or "").strip()
    if provider_id or base_url or secret_env_ref:
        resolved_provider_id = provider_id or "openai"
        if resolved_provider_id != "openai":
            raise ValueError(f"VOICE_TRANSCRIBE_PROVIDER '{resolved_provider_id}' is not supported yet.")
        resolved_secret_env_ref = secret_env_ref or "OPENAI_API_KEY"
        secret_value = env_map.get(resolved_secret_env_ref)
        if not secret_value:
            raise ValueError(
                f"Voice transcription is missing secret value for env ref '{resolved_secret_env_ref}'."
            )
        return {
            "provider_id": "openai",
            "provider_kind": "openai",
            "base_url": base_url or DEFAULT_OPENAI_TRANSCRIPTION_BASE_URL,
            "secret_value": str(secret_value).strip(),
        }
    openai_key = str(env_map.get("OPENAI_API_KEY") or "").strip()
    if openai_key:
        return {
            "provider_id": "openai",
            "provider_kind": "openai",
            "base_url": DEFAULT_OPENAI_TRANSCRIPTION_BASE_URL,
            "secret_value": openai_key,
        }
    return None


def _read_env_value(*, env_file_path: str, key: str) -> str | None:
    return _runtime_env_map(env_file_path=env_file_path).get(key)


def _read_env_map(*, env_file_path: str) -> dict[str, str]:
    path = Path(env_file_path)
    if not path.exists():
        raise ValueError(f"Builder env file does not exist at '{env_file_path}'.")
    env_map: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        env_map[name.strip()] = value.strip()
    return env_map


def _process_voice_env_map() -> dict[str, str]:
    env_map: dict[str, str] = {}
    for key in VOICE_ENV_KEYS:
        value = str(os.environ.get(key) or "").strip()
        if value:
            env_map[key] = value
    return env_map


def _runtime_env_map(*, env_file_path: str | None = None) -> dict[str, str]:
    env_map = _process_voice_env_map()
    if env_file_path:
        env_map.update({key: value for key, value in _read_env_map(env_file_path=env_file_path).items() if value})
    return env_map


def _tail_nonempty_lines(text: str, *, limit: int) -> list[str]:
    lines = [" ".join(line.strip().split()) for line in str(text or "").splitlines()]
    return [line for line in lines if line][-limit:]


def _resolve_fallback_mode(payload: dict[str, Any]) -> str | None:
    mode = str(payload.get("fallback_mode") or "").strip().lower()
    if not mode:
        return None
    if mode not in SUPPORTED_FALLBACK_MODES:
        raise ValueError(
            f"Unsupported fallback_mode '{mode}'. Supported fallback modes: {', '.join(sorted(SUPPORTED_FALLBACK_MODES))}."
        )
    return mode


def _deterministic_transcribe_response(*, audio_bytes: bytes, filename: str, reason: str) -> dict[str, Any]:
    transcript_text = _build_deterministic_fallback_transcript(
        audio_bytes=audio_bytes,
        filename=filename,
        reason=reason,
    )
    return {
        "returncode": 0,
        "stdout": transcript_text,
        "stderr": "",
        "metrics": {
            "transcript_characters": len(transcript_text),
            "audio_bytes": len(audio_bytes),
            "fallback_used": 1,
        },
        "result": {
            "transcript_text": transcript_text,
            "provider_id": "deterministic_fallback",
            "model": "deterministic_fallback",
            "mode": "deterministic_fallback",
            "fallback_reason": reason,
        },
    }


def _with_transcribe_runtime_state(
    response: dict[str, Any],
    *,
    payload: dict[str, Any],
    audio_bytes: int,
    started_at: float,
) -> dict[str, Any]:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    transcribe_ms = _elapsed_ms(started_at)
    metrics = response.get("metrics") if isinstance(response.get("metrics"), dict) else {}
    metrics["transcribe_ms"] = transcribe_ms
    response["metrics"] = metrics
    result["runtime_state"] = state_from_transcribe(
        provider_id=str(result.get("provider_id") or "unknown"),
        mode=str(result.get("mode") or "unknown"),
        model=str(result.get("model") or ""),
        audio_bytes=audio_bytes,
        transcript_text=str(result.get("transcript_text") or ""),
        payload=payload,
        transcribe_ms=transcribe_ms,
        fallback_reason=str(result.get("fallback_reason") or ""),
    )
    response["result"] = result
    return response


def _transcription_provider_mode(payload: dict[str, Any]) -> str:
    env_file_path = str(payload.get("builder_env_file_path") or "").strip()
    try:
        env_map = _runtime_env_map(env_file_path=env_file_path or None)
    except Exception:
        env_map = _process_voice_env_map()
    provider_id = str(env_map.get("VOICE_TRANSCRIBE_PROVIDER") or "").strip().lower()
    if not provider_id:
        return "auto"
    normalized = provider_id.replace("_", "-")
    if normalized in {"auto", "default"}:
        return "auto"
    if normalized in {"local", "offline", "faster-whisper", "local-faster-whisper"}:
        return "local"
    return "provider"


def _resolve_tts_request(payload: dict[str, Any], *, profile: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text") or "").strip()
    if not text:
        raise ValueError("voice.speak requires non-empty text.")
    env_file_path = str(payload.get("builder_env_file_path") or "").strip()
    tts_payload = payload.get("tts")
    tts = tts_payload if isinstance(tts_payload, dict) else {}
    surface = str(payload.get("surface") or "").strip().lower()
    env_map = _runtime_env_map(env_file_path=env_file_path or None)
    provider_id = str(tts.get("provider_id") or env_map.get(ENV_TTS_PROVIDER) or DEFAULT_TTS_PROVIDER).strip().lower() or DEFAULT_TTS_PROVIDER
    if provider_id in {LOCAL_KOKORO_TTS_PROVIDER, "kokoro-onnx", "local-kokoro"}:
        return _resolve_kokoro_tts_request(tts=tts, env_map=env_map, text=text, surface=surface)
    if provider_id in {LOCAL_TTS_PROVIDER, "local"}:
        return _resolve_local_tts_request(payload=payload, tts=tts, env_map=env_map, text=text, surface=surface)
    if provider_id in OPENAI_REALTIME_PROVIDER_ALIASES:
        return _resolve_openai_realtime_tts_request(tts=tts, env_map=env_map, text=text, surface=surface)
    if provider_id != "elevenlabs":
        raise ValueError(f"voice.speak does not yet support provider '{provider_id}'.")
    if not env_file_path:
        raise ValueError("Builder did not provide an env file path for voice synthesis.")
    auth_method = str(tts.get("auth_method") or "api_key_env").strip() or "api_key_env"
    if auth_method != "api_key_env":
        raise ValueError(f"voice.speak uses unsupported auth method '{auth_method}'.")
    secret_env_ref = str(tts.get("secret_env_ref") or "ELEVENLABS_API_KEY").strip()
    if not secret_env_ref:
        raise ValueError("voice.speak requires a secret_env_ref for the TTS provider.")
    secret_value = env_map.get(secret_env_ref)
    if not secret_value:
        raise ValueError(f"voice.speak is missing secret value for env ref '{secret_env_ref}'.")
    provider_profile = get_provider_voice_profile(profile, "elevenlabs")
    speech = profile.get("speech") if isinstance(profile.get("speech"), dict) else {}
    voice_settings = tts.get("voice_settings")
    provided_voice_settings = voice_settings if isinstance(voice_settings, dict) else {}
    output_format = str(tts.get("output_format") or "").strip()
    if not output_format:
        output_format = (
            DEFAULT_TELEGRAM_ELEVENLABS_OUTPUT_FORMAT if surface == "telegram" else DEFAULT_ELEVENLABS_OUTPUT_FORMAT
        )
    mime_type, file_extension, voice_compatible = _resolve_elevenlabs_output_metadata(output_format)
    return {
        "provider_id": "elevenlabs",
        "surface": surface,
        "base_url": str(tts.get("base_url") or env_map.get(ENV_TTS_BASE_URL) or DEFAULT_ELEVENLABS_BASE_URL).strip()
        or DEFAULT_ELEVENLABS_BASE_URL,
        "secret_value": secret_value,
        "text": text,
        "voice_id": str(tts.get("voice_id") or env_map.get(ENV_TTS_VOICE_ID) or provider_profile.get("primary_voice_id") or "").strip(),
        "preferred_voice_name": str(
            tts.get("voice_name") or env_map.get(ENV_TTS_VOICE_NAME) or provider_profile.get("primary_voice_name") or ""
        ).strip(),
        "model_id": str(tts.get("model_id") or env_map.get(ENV_TTS_MODEL_ID) or provider_profile.get("model_id") or DEFAULT_ELEVENLABS_MODEL_ID).strip()
        or DEFAULT_ELEVENLABS_MODEL_ID,
        "output_format": output_format,
        "mime_type": mime_type,
        "file_extension": file_extension,
        "voice_compatible": voice_compatible,
        "voice_settings": {
            "stability": provided_voice_settings.get("stability", 0.92),
            "similarity_boost": provided_voice_settings.get("similarity_boost", 0.78),
            "style": provided_voice_settings.get("style", 0.03),
            "use_speaker_boost": provided_voice_settings.get("use_speaker_boost", True),
            "speed": provided_voice_settings.get("speed", speech.get("default_rate", 1.0)),
        },
    }


def _resolve_kokoro_tts_request(
    *,
    tts: dict[str, Any],
    env_map: dict[str, str],
    text: str,
    surface: str,
) -> dict[str, Any]:
    model_path = str(tts.get("model_path") or env_map.get(ENV_KOKORO_MODEL_PATH) or "").strip()
    voices_path = str(tts.get("voices_path") or env_map.get(ENV_KOKORO_VOICES_PATH) or "").strip()
    if not model_path or not voices_path:
        raise ValueError(
            f"Kokoro TTS requires local model assets. Set `{ENV_KOKORO_MODEL_PATH}` and `{ENV_KOKORO_VOICES_PATH}`."
        )
    speed = _resolve_optional_float(tts.get("speed") or env_map.get(ENV_KOKORO_SPEED))
    if speed is None:
        speed = 1.0
    return {
        "provider_id": LOCAL_KOKORO_TTS_PROVIDER,
        "surface": surface,
        "text": text,
        "voice_id": str(tts.get("voice") or tts.get("voice_id") or env_map.get(ENV_KOKORO_VOICE) or DEFAULT_KOKORO_VOICE).strip()
        or DEFAULT_KOKORO_VOICE,
        "model_id": Path(model_path).name or "kokoro-v1.0.onnx",
        "mime_type": "audio/wav",
        "file_extension": ".wav",
        "voice_compatible": False,
        "model_path": model_path,
        "voices_path": voices_path,
        "speed": max(0.5, min(2.0, float(speed))),
        "lang": str(tts.get("lang") or env_map.get(ENV_KOKORO_LANG) or DEFAULT_KOKORO_LANG).strip()
        or DEFAULT_KOKORO_LANG,
    }


def _resolve_local_tts_request(
    *,
    payload: dict[str, Any],
    tts: dict[str, Any],
    env_map: dict[str, str],
    text: str,
    surface: str,
) -> dict[str, Any]:
    rate = _resolve_optional_float(tts.get("rate") or env_map.get(ENV_LOCAL_TTS_RATE))
    volume = _resolve_optional_float(tts.get("volume") or env_map.get(ENV_LOCAL_TTS_VOLUME))
    voice_name = str(tts.get("voice_name") or env_map.get(ENV_LOCAL_TTS_VOICE_NAME) or "").strip()
    return {
        "provider_id": LOCAL_TTS_PROVIDER,
        "surface": surface,
        "text": text,
        "voice_id": voice_name or "local-system-voice",
        "model_id": "system-tts",
        "mime_type": "audio/wav",
        "file_extension": ".wav",
        "voice_compatible": False,
        "rate": rate,
        "volume": volume,
        "voice_name": voice_name,
    }


def _resolve_openai_realtime_tts_request(
    *,
    tts: dict[str, Any],
    env_map: dict[str, str],
    text: str,
    surface: str,
) -> dict[str, Any]:
    secret_env_ref = str(tts.get("secret_env_ref") or env_map.get(ENV_OPENAI_REALTIME_SECRET_REF) or "OPENAI_API_KEY").strip()
    if not secret_env_ref:
        raise ValueError("voice.speak requires a secret_env_ref for OpenAI Realtime.")
    secret_value = env_map.get(secret_env_ref)
    if not secret_value:
        raise ValueError(f"voice.speak is missing secret value for env ref '{secret_env_ref}'.")
    timeout_seconds = _resolve_optional_float(tts.get("timeout_seconds") or env_map.get(ENV_OPENAI_REALTIME_TIMEOUT_SECONDS))
    if timeout_seconds is None:
        timeout_seconds = DEFAULT_OPENAI_REALTIME_TIMEOUT_SECONDS
    sample_rate = int(_resolve_optional_float(tts.get("sample_rate")) or DEFAULT_OPENAI_REALTIME_SAMPLE_RATE)
    model_id = str(
        tts.get("model_id") or env_map.get(ENV_OPENAI_REALTIME_MODEL_ID) or DEFAULT_OPENAI_REALTIME_MODEL_ID
    ).strip() or DEFAULT_OPENAI_REALTIME_MODEL_ID
    style_instructions = str(tts.get("instructions") or env_map.get(ENV_OPENAI_REALTIME_INSTRUCTIONS) or "").strip()
    return {
        "provider_id": OPENAI_REALTIME_TTS_PROVIDER,
        "surface": surface,
        "text": text,
        "base_url": str(tts.get("base_url") or env_map.get(ENV_OPENAI_REALTIME_WS_URL) or DEFAULT_OPENAI_REALTIME_WS_URL).strip()
        or DEFAULT_OPENAI_REALTIME_WS_URL,
        "secret_value": secret_value,
        "model_id": model_id,
        "voice_id": str(tts.get("voice") or tts.get("voice_id") or env_map.get(ENV_OPENAI_REALTIME_VOICE) or DEFAULT_OPENAI_REALTIME_VOICE).strip()
        or DEFAULT_OPENAI_REALTIME_VOICE,
        "reasoning_effort": str(tts.get("reasoning_effort") or env_map.get(ENV_OPENAI_REALTIME_REASONING_EFFORT) or "").strip(),
        "instructions": _openai_realtime_tts_instructions(style_instructions),
        "sample_rate": sample_rate,
        "timeout_seconds": max(5.0, min(120.0, float(timeout_seconds))),
        "mime_type": "audio/wav",
        "file_extension": ".wav",
        "voice_compatible": False,
    }


def _openai_realtime_tts_instructions(style_instructions: str) -> str:
    style = str(style_instructions or "").strip()
    if not style or style == DEFAULT_OPENAI_REALTIME_INSTRUCTIONS:
        return DEFAULT_OPENAI_REALTIME_INSTRUCTIONS
    return (
        f"{DEFAULT_OPENAI_REALTIME_INSTRUCTIONS}\n\n"
        f"Voice style note, only if it does not change the words: {style}"
    )


def _resolve_optional_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _synthesize_with_elevenlabs(*, request: dict[str, Any]) -> tuple[bytes, str]:
    voice_id = str(request["voice_id"]).strip()
    if not voice_id:
        raise ValueError(
            f"voice.speak requires an ElevenLabs voice_id. Set `tts.voice_id` or `{ENV_TTS_VOICE_ID}`."
        )
    retried_with_fallback = False
    while True:
        base_url = _join_url(request["base_url"], f"text-to-speech/{voice_id}")
        query = {"optimize_streaming_latency": "2"}
        output_format = str(request.get("output_format") or "").strip()
        if output_format:
            query["output_format"] = output_format
        url = f"{base_url}?{urllib.parse.urlencode(query)}"
        body = {
            "text": request["text"],
            "model_id": request["model_id"],
            "voice_settings": request["voice_settings"],
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "xi-api-key": request["secret_value"],
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                audio_bytes = response.read()
            if not audio_bytes:
                raise RuntimeError("ElevenLabs returned empty audio.")
            return audio_bytes, voice_id
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
            is_not_found = "voice_not_found" in detail.lower()
            if is_not_found and not retried_with_fallback:
                fallback_voice_id = _resolve_elevenlabs_fallback_voice_id(request=request)
                if fallback_voice_id and fallback_voice_id != voice_id:
                    voice_id = fallback_voice_id
                    retried_with_fallback = True
                    continue
            raise RuntimeError(f"ElevenLabs TTS request failed: {detail or exc}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"ElevenLabs TTS network error: {exc.reason}") from exc


def _synthesize_with_pyttsx3(*, request: dict[str, Any]) -> tuple[bytes, str]:
    try:
        pyttsx3 = importlib.import_module("pyttsx3")
    except Exception as exc:
        raise RuntimeError("Local TTS requires optional package `pyttsx3`. Install it, then retry.") from exc
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as handle:
            temp_path = handle.name
        engine = pyttsx3.init()
        rate = request.get("rate")
        if rate is not None:
            engine.setProperty("rate", int(rate))
        volume = request.get("volume")
        if volume is not None:
            engine.setProperty("volume", max(0.0, min(1.0, float(volume))))
        voice_name = str(request.get("voice_name") or "").strip().lower()
        if voice_name:
            for voice in engine.getProperty("voices") or []:
                name = str(getattr(voice, "name", "") or "").lower()
                voice_id = str(getattr(voice, "id", "") or "")
                if voice_name in name or voice_name in voice_id.lower():
                    engine.setProperty("voice", voice_id)
                    break
        engine.save_to_file(request["text"], temp_path)
        engine.runAndWait()
        audio_bytes = Path(temp_path).read_bytes()
        if not audio_bytes:
            raise RuntimeError("Local pyttsx3 TTS returned empty audio.")
        return audio_bytes, str(request.get("voice_id") or "local-system-voice")
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def _synthesize_with_kokoro(*, request: dict[str, Any]) -> tuple[bytes, str]:
    try:
        kokoro_module = importlib.import_module("kokoro_onnx")
        soundfile = importlib.import_module("soundfile")
    except Exception as exc:
        raise RuntimeError("Kokoro TTS requires optional packages `kokoro-onnx` and `soundfile`. Install them, then retry.") from exc
    model_path = Path(str(request.get("model_path") or ""))
    voices_path = Path(str(request.get("voices_path") or ""))
    if not model_path.exists():
        raise RuntimeError(f"Kokoro model file was not found at '{model_path}'.")
    if not voices_path.exists():
        raise RuntimeError(f"Kokoro voices file was not found at '{voices_path}'.")
    kokoro = kokoro_module.Kokoro(str(model_path), str(voices_path))
    samples, sample_rate = kokoro.create(
        request["text"],
        voice=str(request.get("voice_id") or DEFAULT_KOKORO_VOICE),
        speed=float(request.get("speed") or 1.0),
        lang=str(request.get("lang") or DEFAULT_KOKORO_LANG),
    )
    buffer = io.BytesIO()
    soundfile.write(buffer, samples, int(sample_rate), format="WAV")
    audio_bytes = buffer.getvalue()
    if not audio_bytes:
        raise RuntimeError("Kokoro TTS returned empty audio.")
    return audio_bytes, str(request.get("voice_id") or DEFAULT_KOKORO_VOICE)


def _synthesize_with_openai_realtime(*, request: dict[str, Any]) -> tuple[bytes, str]:
    try:
        websocket = importlib.import_module("websocket")
    except Exception as exc:
        raise RuntimeError(
            "OpenAI Realtime TTS requires optional package `websocket-client`. Install `spark-voice-comms[openai-realtime]`, then retry."
        ) from exc

    model_id = str(request["model_id"]).strip() or DEFAULT_OPENAI_REALTIME_MODEL_ID
    url = _openai_realtime_ws_url(str(request["base_url"]), model_id=model_id)
    voice_id = str(request.get("voice_id") or DEFAULT_OPENAI_REALTIME_VOICE).strip() or DEFAULT_OPENAI_REALTIME_VOICE
    sample_rate = int(request.get("sample_rate") or DEFAULT_OPENAI_REALTIME_SAMPLE_RATE)
    timeout = float(request.get("timeout_seconds") or DEFAULT_OPENAI_REALTIME_TIMEOUT_SECONDS)
    headers = [
        "Authorization: Bearer " + str(request["secret_value"]),
    ]
    ws = websocket.create_connection(url, header=headers, timeout=timeout)
    audio_chunks: list[bytes] = []
    fallback_audio_chunks: list[bytes] = []
    try:
        session_payload: dict[str, Any] = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": model_id,
                "output_modalities": ["audio"],
                "audio": {
                    "output": {
                        "format": {"type": "audio/pcm", "rate": sample_rate},
                        "voice": voice_id,
                    }
                },
            },
        }
        if request.get("instructions"):
            session_payload["session"]["instructions"] = str(request["instructions"])
        reasoning_effort = str(request.get("reasoning_effort") or "").strip()
        if reasoning_effort:
            session_payload["session"]["reasoning"] = {"effort": reasoning_effort}
        ws.send(json.dumps(session_payload))
        ws.send(
            json.dumps(
                {
                    "type": "response.create",
                    "response": {
                        "conversation": "none",
                        "instructions": str(request["instructions"]),
                        "output_modalities": ["audio"],
                        "audio": {
                            "output": {
                                "format": {"type": "audio/pcm", "rate": sample_rate},
                                "voice": voice_id,
                            }
                        },
                        "input": [
                            {
                                "type": "message",
                                "role": "user",
                                "content": [{"type": "input_text", "text": str(request["text"])}],
                            }
                        ],
                    },
                }
            )
        )
        while True:
            raw_message = ws.recv()
            if not raw_message:
                continue
            event = json.loads(raw_message)
            event_type = str(event.get("type") or "")
            if event_type == "error":
                error = event.get("error") if isinstance(event.get("error"), dict) else {}
                message = str(error.get("message") or event)
                raise RuntimeError(f"OpenAI Realtime TTS request failed: {message}")
            if event_type == "response.output_audio.delta":
                delta = str(event.get("delta") or "")
                if delta:
                    audio_chunks.append(base64.b64decode(delta.encode("ascii")))
            elif event_type == "response.content_part.done":
                part = event.get("part") if isinstance(event.get("part"), dict) else {}
                audio = str(part.get("audio") or "")
                if audio:
                    fallback_audio_chunks.append(base64.b64decode(audio.encode("ascii")))
            elif event_type == "response.done":
                break
    finally:
        ws.close()
    pcm_audio = b"".join(audio_chunks or fallback_audio_chunks)
    if not pcm_audio:
        raise RuntimeError("OpenAI Realtime TTS returned empty audio.")
    return _pcm16_to_wav(pcm_audio, sample_rate=sample_rate), voice_id


def _resolve_elevenlabs_output_metadata(output_format: str) -> tuple[str, str, bool]:
    normalized = str(output_format or "").strip().lower()
    if normalized.startswith("opus") or "ogg" in normalized:
        return ("audio/ogg", ".ogg", True)
    if normalized.startswith("pcm"):
        return ("audio/wav", ".wav", False)
    return ("audio/mpeg", ".mp3", False)


def _openai_realtime_ws_url(base_url: str, *, model_id: str) -> str:
    normalized = str(base_url or DEFAULT_OPENAI_REALTIME_WS_URL).strip().rstrip("/")
    if normalized.startswith("http://"):
        normalized = "ws://" + normalized[len("http://") :]
    elif normalized.startswith("https://"):
        normalized = "wss://" + normalized[len("https://") :]
    if not normalized.endswith("/realtime"):
        normalized = f"{normalized}/realtime"
    return f"{normalized}?{urllib.parse.urlencode({'model': model_id})}"


def _pcm16_to_wav(pcm_audio: bytes, *, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(int(sample_rate))
        wav_file.writeframes(pcm_audio)
    return buffer.getvalue()


def _resolve_elevenlabs_fallback_voice_id(*, request: dict[str, Any]) -> str | None:
    req = urllib.request.Request(
        _join_url(request["base_url"], "voices"),
        headers={"xi-api-key": request["secret_value"]},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    voices = payload.get("voices") if isinstance(payload, dict) else None
    if not isinstance(voices, list) or not voices:
        return None
    preferred_name = str(request.get("preferred_voice_name") or "").strip()
    if preferred_name:
        for voice in voices:
            if str(voice.get("name") or "").strip().lower() == preferred_name.lower():
                candidate = str(voice.get("voice_id") or "").strip()
                if candidate:
                    return candidate
    for voice in voices:
        candidate = str(voice.get("voice_id") or "").strip()
        if candidate:
            return candidate
    return None


def _build_deterministic_fallback_transcript(
    *,
    audio_bytes: bytes,
    filename: str,
    reason: str,
) -> str:
    digest = hashlib.sha256(audio_bytes).hexdigest()
    seed = int(digest[:8], 16)
    approx_seconds = max(0.2, len(audio_bytes) / 16000.0)
    snippets = [
        "Ready when you are.",
        "Holding for your next command.",
        "Signal received and queued.",
        "Spark fallback captured your audio.",
        "Mic packet decoded locally.",
    ]
    snippet = snippets[seed % len(snippets)]
    cleaned_reason = " ".join(str(reason or "").strip().split())
    return (
        f"[Deterministic fallback transcript] Audio received ({approx_seconds:.2f}s, "
        f"{len(audio_bytes)} bytes, source {filename}). {snippet} "
        f"Provider reason: {cleaned_reason or 'unknown failure'}."
    )


def _local_faster_whisper_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def _local_pyttsx3_available() -> bool:
    return importlib.util.find_spec("pyttsx3") is not None


def _local_kokoro_package_available() -> bool:
    return importlib.util.find_spec("kokoro_onnx") is not None and importlib.util.find_spec("soundfile") is not None


def _local_kokoro_ready(*, env_map: dict[str, str]) -> bool:
    if not _local_kokoro_package_available():
        return False
    model_path = str(env_map.get(ENV_KOKORO_MODEL_PATH) or "").strip()
    voices_path = str(env_map.get(ENV_KOKORO_VOICES_PATH) or "").strip()
    return bool(model_path and voices_path and Path(model_path).exists() and Path(voices_path).exists())


def _resolve_local_faster_whisper_model(payload: dict[str, Any]) -> str:
    env_file_path = str(payload.get("builder_env_file_path") or "").strip()
    if env_file_path:
        env_map = _runtime_env_map(env_file_path=env_file_path)
        configured = str(env_map.get("VOICE_TRANSCRIBE_LOCAL_MODEL") or "").strip()
        if configured:
            return configured
    return "tiny"


def _resolve_local_faster_whisper_language(payload: dict[str, Any]) -> str | None:
    env_file_path = str(payload.get("builder_env_file_path") or "").strip()
    if env_file_path:
        env_map = _runtime_env_map(env_file_path=env_file_path)
        configured = str(env_map.get("VOICE_TRANSCRIBE_LOCAL_LANGUAGE") or "").strip()
        if configured:
            return configured
    return None


def _resolve_local_faster_whisper_vad_filter(payload: dict[str, Any]) -> bool:
    env_file_path = str(payload.get("builder_env_file_path") or "").strip()
    if env_file_path:
        env_map = _runtime_env_map(env_file_path=env_file_path)
        configured = str(env_map.get("VOICE_TRANSCRIBE_LOCAL_VAD_FILTER") or "").strip().lower()
        if configured in {"1", "true", "yes", "on"}:
            return True
        if configured in {"0", "false", "no", "off"}:
            return False
    return True


def _resolve_local_faster_whisper_beam_size(payload: dict[str, Any]) -> int:
    env_file_path = str(payload.get("builder_env_file_path") or "").strip()
    if env_file_path:
        env_map = _runtime_env_map(env_file_path=env_file_path)
        configured = str(env_map.get("VOICE_TRANSCRIBE_LOCAL_BEAM_SIZE") or "").strip()
        if configured:
            try:
                return max(1, int(configured))
            except ValueError:
                pass
    return 5


def _transcribe_with_local_faster_whisper(
    *,
    payload: dict[str, Any],
    audio_bytes: bytes,
    filename: str,
) -> str:
    from faster_whisper import WhisperModel

    suffix = Path(filename).suffix or ".wav"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(audio_bytes)
            temp_path = handle.name
        model = WhisperModel(_resolve_local_faster_whisper_model(payload), device="cpu", compute_type="int8")
        transcribe_kwargs: dict[str, Any] = {
            "beam_size": _resolve_local_faster_whisper_beam_size(payload),
            "condition_on_previous_text": False,
            "vad_filter": _resolve_local_faster_whisper_vad_filter(payload),
        }
        language = _resolve_local_faster_whisper_language(payload)
        if language:
            transcribe_kwargs["language"] = language
        segments, _info = model.transcribe(temp_path, **transcribe_kwargs)
        text = " ".join(str(segment.text or "").strip() for segment in segments).strip()
        if not text:
            raise ValueError("Local faster-whisper returned no transcript text.")
        return text
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def _transcribe_with_provider(
    *,
    provider: dict[str, str],
    audio_bytes: bytes,
    filename: str,
    mime_type: str,
) -> str:
    payload = _post_multipart(
        _join_url(provider["base_url"], "audio/transcriptions"),
        headers={"Authorization": f"Bearer {provider['secret_value']}"},
        fields={"model": DEFAULT_TRANSCRIPTION_MODEL},
        files=[
            {
                "field_name": "file",
                "filename": filename,
                "mime_type": mime_type,
                "content": audio_bytes,
            }
        ],
    )
    decoded = _decode_response(payload)
    transcript_text = _extract_transcript_text(decoded)
    if not transcript_text:
        raise ValueError("The voice provider returned no transcript text.")
    return transcript_text


def _post_multipart(
    url: str,
    *,
    headers: dict[str, str],
    fields: dict[str, str],
    files: list[dict[str, object]],
) -> bytes:
    boundary = f"voice-chip-{uuid4().hex}"
    body = bytearray()
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    for file_info in files:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="{file_info["field_name"]}"; '
                f'filename="{file_info["filename"]}"\r\n'
                f'Content-Type: {file_info["mime_type"]}\r\n\r\n'
            ).encode("utf-8")
        )
        body.extend(bytes(file_info["content"]))
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    request = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            **headers,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Voice provider HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Voice provider network error: {exc.reason}") from exc


def _decode_response(payload: bytes) -> dict[str, Any] | str:
    text = payload.decode("utf-8", errors="replace").strip()
    if not text:
        raise ValueError("Voice provider response was empty.")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _extract_transcript_text(payload: dict[str, Any] | str) -> str:
    if isinstance(payload, str):
        return payload.strip()
    for key in ("text", "transcript"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _join_url(base_url: str, suffix: str) -> str:
    return f"{base_url.rstrip('/')}/{suffix.lstrip('/')}"


def _write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _public_runtime_state(runtime_state: dict[str, Any]) -> dict[str, Any]:
    stt = runtime_state.get("stt") if isinstance(runtime_state.get("stt"), dict) else {}
    tts = runtime_state.get("tts") if isinstance(runtime_state.get("tts"), dict) else {}
    delivery = runtime_state.get("telegram_delivery") if isinstance(runtime_state.get("telegram_delivery"), dict) else {}
    return {
        "schema_version": runtime_state.get("schema_version"),
        "generated_at": runtime_state.get("generated_at"),
        "surface": runtime_state.get("surface"),
        "dm_voice_replies": runtime_state.get("dm_voice_replies"),
        "canonical_chip_key": runtime_state.get("canonical_chip_key"),
        "legacy_alias_visible": bool(runtime_state.get("legacy_alias_visible")),
        "stt": {
            "provider_id": stt.get("provider_id"),
            "provider_kind": stt.get("provider_kind"),
            "mode": stt.get("mode"),
            "ready": bool(stt.get("ready")),
            "model": stt.get("model"),
            "last_probe_ref": stt.get("last_probe_ref"),
            "last_failure_reason_present": bool(stt.get("last_failure_reason")),
            "claim_boundary": stt.get("claim_boundary"),
        },
        "tts": {
            "provider_id": tts.get("provider_id"),
            "mode": tts.get("mode"),
            "ready": bool(tts.get("ready")),
            "voice_name": tts.get("voice_name"),
            "voice_id_masked": tts.get("voice_id_masked"),
            "voice_id_fingerprint": tts.get("voice_id_fingerprint"),
            "model_id": tts.get("model_id"),
            "mime_type": tts.get("mime_type"),
            "voice_compatible": bool(tts.get("voice_compatible")),
            "audio_bytes": int(tts.get("audio_bytes") or 0),
            "settings_fingerprint": tts.get("settings_fingerprint"),
            "last_probe_ref": tts.get("last_probe_ref"),
            "claim_boundary": tts.get("claim_boundary"),
        },
        "telegram_delivery": {
            "ready": bool(delivery.get("ready")),
            "last_send_voice_at_present": bool(delivery.get("last_send_voice_at")),
            "last_send_voice_status": delivery.get("last_send_voice_status"),
            "last_failure_reason_present": bool(delivery.get("last_failure_reason")),
            "telegram_message_id_present": bool(delivery.get("telegram_message_id_present")),
        },
        "latency": runtime_state.get("latency") if isinstance(runtime_state.get("latency"), dict) else {},
        "claim_levels": runtime_state.get("claim_levels") if isinstance(runtime_state.get("claim_levels"), dict) else {},
        "source_ledger": runtime_state.get("source_ledger") if isinstance(runtime_state.get("source_ledger"), list) else [],
        "redaction": "metadata only; raw audio, transcript bodies, provider secrets, and unmasked voice ids omitted",
    }


def _export_runtime_state_if_configured(result: dict[str, Any]) -> None:
    path_text = str(os.environ.get(ENV_RUNTIME_STATE_PATH) or "").strip()
    if not path_text:
        return
    result_payload = result.get("result") if isinstance(result.get("result"), dict) else {}
    runtime_state = result_payload.get("runtime_state") if isinstance(result_payload.get("runtime_state"), dict) else None
    if runtime_state is None:
        return
    _write_output(Path(path_text).expanduser(), _public_runtime_state(runtime_state))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "hook",
        choices=["voice.status", "voice.plan", "voice.onboard", "voice.install", "voice.transcribe", "voice.speak"],
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
        if args.hook == "voice.status":
            result = handle_voice_status_hook(payload)
        elif args.hook == "voice.plan":
            result = handle_voice_plan_hook(payload)
        elif args.hook == "voice.onboard":
            result = handle_voice_onboard_hook(payload)
        elif args.hook == "voice.install":
            result = handle_voice_install_hook(payload)
        elif args.hook == "voice.speak":
            result = handle_voice_speak_hook(payload)
        else:
            result = handle_voice_transcribe_hook(payload)
    except Exception as exc:
        _write_output(
            Path(args.output),
            {
                "returncode": 1,
                "stdout": "",
                "stderr": str(exc),
                "metrics": {},
                "result": {},
                "error": str(exc),
            },
        )
        return 1

    _export_runtime_state_if_configured(result)
    _write_output(Path(args.output), result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
