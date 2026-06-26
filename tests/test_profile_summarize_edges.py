"""Edge-case tests for voice profile summarizer + provider lookup.

profile.summarize_voice_profile + get_provider_voice_profile do the type
defensive work for downstream consumers: tone / speech / interaction /
provider_voices may all be missing or the wrong type and the summary
must still come back with stable defaults instead of crashing.
test_profile.py covers the happy path against the shipped
spark_core.voice_profile.json. The edge cases (empty profile, mistyped
sub-keys, unknown provider, non-dict provider payload) are unpinned.
"""

from __future__ import annotations

from voice_comms_chip.profile import (
    get_provider_voice_profile,
    summarize_voice_profile,
)


# ----- summarize_voice_profile defensive defaults -----


def test_summarize_empty_profile_returns_unknown_defaults() -> None:
    summary = summarize_voice_profile({})
    assert summary["profile_name"] == "unknown"
    assert summary["tone_identity"] == "unknown"
    assert summary["default_emotion"] == "unknown"
    assert summary["default_rate"] is None
    assert summary["barge_in_enabled"] is False
    assert summary["streaming_reply_default"] is False
    assert summary["provider_voice_ids"] == []


def test_summarize_handles_non_dict_subkeys_gracefully() -> None:
    # If tone or speech come back as a string from a malformed profile,
    # the summarizer must still produce defaults rather than raise.
    summary = summarize_voice_profile({
        "tone": "not-a-dict",
        "speech": 42,
        "interaction": ["not", "a", "dict"],
        "provider_voices": "not-a-dict",
    })
    assert summary["tone_identity"] == "unknown"
    assert summary["default_rate"] is None
    assert summary["barge_in_enabled"] is False
    assert summary["provider_voice_ids"] == []


def test_summarize_uses_explicit_default_rate_when_provided() -> None:
    summary = summarize_voice_profile({"speech": {"default_rate": 0.9}})
    assert summary["default_rate"] == 0.9


def test_summarize_strips_whitespace_only_strings_to_unknown() -> None:
    summary = summarize_voice_profile({
        "profile_name": "   ",
        "tone": {"identity": "   "},
        "speech": {"default_emotion": "   "},
    })
    assert summary["profile_name"] == "unknown"
    assert summary["tone_identity"] == "unknown"
    assert summary["default_emotion"] == "unknown"


def test_summarize_provider_voice_ids_skips_non_dict_payloads() -> None:
    summary = summarize_voice_profile({
        "provider_voices": {
            "elevenlabs": {"primary_voice_id": "v1"},
            "broken-payload": "not-a-dict",
            "": {"primary_voice_id": "v2"},  # blank provider name skipped
            "  ": {"primary_voice_id": "v3"},  # whitespace-only skipped
        }
    })
    # Only well-formed (str provider name, dict payload) entries appear,
    # and the output list is sorted.
    assert summary["provider_voice_ids"] == ["elevenlabs"]


def test_summarize_provider_voice_ids_is_sorted() -> None:
    summary = summarize_voice_profile({
        "provider_voices": {
            "zeta": {"primary_voice_id": "v1"},
            "alpha": {"primary_voice_id": "v2"},
            "mu": {"primary_voice_id": "v3"},
        }
    })
    assert summary["provider_voice_ids"] == ["alpha", "mu", "zeta"]


# ----- get_provider_voice_profile lookups -----


def test_get_provider_voice_profile_returns_payload_for_known_provider() -> None:
    profile = {"provider_voices": {"elevenlabs": {"primary_voice_id": "v1"}}}
    out = get_provider_voice_profile(profile, "elevenlabs")
    assert out == {"primary_voice_id": "v1"}


def test_get_provider_voice_profile_returns_empty_dict_for_missing_provider() -> None:
    profile = {"provider_voices": {"elevenlabs": {"primary_voice_id": "v1"}}}
    assert get_provider_voice_profile(profile, "openai") == {}


def test_get_provider_voice_profile_returns_empty_dict_for_non_dict_payload() -> None:
    profile = {"provider_voices": {"elevenlabs": "not-a-dict"}}
    assert get_provider_voice_profile(profile, "elevenlabs") == {}


def test_get_provider_voice_profile_returns_empty_dict_when_provider_voices_missing() -> None:
    assert get_provider_voice_profile({}, "elevenlabs") == {}
    assert get_provider_voice_profile({"provider_voices": "not-a-dict"}, "x") == {}
