from __future__ import annotations

from voice_comms_chip.profile import DEFAULT_PROFILE_PATH, load_voice_profile, summarize_voice_profile


def test_default_voice_profile_loads():
    profile = load_voice_profile()
    assert profile["profile_name"] == "spark_core"
    assert profile["tone"]["identity"] == "calm_confident_concise"
    assert profile["speech"]["default_emotion"] == "calm"


def test_default_voice_profile_summary_is_stable():
    summary = summarize_voice_profile(load_voice_profile())
    assert summary["profile_name"] == "spark_core"
    assert summary["tone_identity"] == "calm_confident_concise"
    assert summary["default_rate"] == 1.0
    assert summary["barge_in_enabled"] is True
    assert "elevenlabs" in summary["provider_voice_ids"]


def test_default_profile_path_exists():
    assert DEFAULT_PROFILE_PATH.exists()

