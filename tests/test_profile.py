from __future__ import annotations

import pytest

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


def test_load_voice_profile_reports_invalid_json():
    # The profile path must live inside an allowed directory (path-traversal
    # guard), so write the broken fixture into the voices/ dir and clean it up.
    profile_path = DEFAULT_PROFILE_PATH.parent / "_invalid_json_fixture.voice_profile.json"
    profile_path.write_text("{broken", encoding="utf-8")
    try:
        with pytest.raises(RuntimeError, match="contains invalid JSON"):
            load_voice_profile(str(profile_path))
    finally:
        profile_path.unlink(missing_ok=True)


def test_load_voice_profile_rejects_path_outside_allowed_dirs(tmp_path):
    # Path-traversal guard: a profile path outside the allowed directories is
    # rejected before any file read happens.
    outside_path = tmp_path / "voice_profile.json"
    outside_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="outside allowed directories"):
        load_voice_profile(str(outside_path))
