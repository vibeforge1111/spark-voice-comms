# Voice Comms Implementation Plan

Date: April 9, 2026

License: AGPL-3.0-only.

## Goal

Build a modular voice communications system for Spark where:
- Builder stays small
- Telegram is the first real operator surface
- the same agent personality is preserved across text and voice
- speech-to-text and text-to-speech are explicit chip hooks, not hidden Builder internals

## Current State

Already done in this repo:
- `voice.status`
- `voice.plan`
- `voice.onboard`
- `voice.transcribe`
- `voice.speak`
- canonical `spark_core` voice profile support
- provider compatibility documentation
- deterministic and local STT fallback paths
- local/free TTS via optional Kokoro or `pyttsx3`

Already done in Builder:
- Telegram voice/audio messages are detected
- Builder can fetch Telegram media file bytes
- Builder passes voice payloads into `voice.transcribe`
- Builder can route `/voice` and `/voice plan` through this chip when the chip is attached
- Builder can shape a voice-friendly spoken variant before calling `voice.speak`
- Builder can request Telegram-targeted Opus voice-note media instead of generic MP3 output

Current live constraints:
- voice activation depends on the host Spark runtime's capability ledger and operator approval
- text personality tuning still happens in Builder, not in this chip
- spoken quality still needs iterative tuning during normal operator use
- Telegram is still a turn-based voice surface, not a streaming one

Important implementation note:
- for Telegram, the correct TTS contract is not just “return some audio”
- the chip should return Telegram-friendly Opus voice-note media
- Builder should then deliver that media as a Telegram voice note
- this was a real playback bug boundary, not a cosmetic preference

## Architecture Decision

Builder should own:
- Telegram message normalization
- Telegram file download
- passing safe voice payloads into chip hooks
- applying persona/style framing to the final reply

`spark-voice-comms` should own:
- provider compatibility logic
- STT
- TTS
- voice profile selection
- fallback behavior
- tuning and evaluation

`spark-swarm` should not own voice personality. Swarm can later share voice-related learnings or reusable operating intelligence, but the visible speaking style should still stay local to Builder + this chip.

## Useful Prior Art

The strongest reference is the earlier local Spark PC voice link prototype. Do not publish private prototype paths, recordings, or tuning notes unless they have been separately scrubbed.

Patterns worth reusing:

1. STT fallback discipline
- `backend/main.py`
- `_deterministic_transcript(...)`
- `_transcribe_with_fallback(...)`

Why it matters:
- voice should fail honestly but not dead-end
- we need a deterministic fallback for testing and degraded runtime modes

2. Partial / streaming transcribe pattern
- `backend/main.py`
- `/ws/transcribe`
- `_partial_transcript(...)`

Why it matters:
- this is useful for future non-Telegram realtime surfaces
- Telegram itself is not realtime voice chat, but the protocol design should not block later streaming voice

3. TTS fallback voice selection
- `backend/main.py`
- `_resolve_elevenlabs_fallback_voice_id(...)`
- `_synthesize_elevenlabs_tts(...)`

Why it matters:
- provider voice ids drift or disappear
- fallback voice resolution should be explicit and tested

4. Canonical voice profile shape
- `voice/voice_profile.json`
- `voice/SPARK_VOICE_SYSTEM.md`
- `voice/VOICE_TUNING_PLAYBOOK.md`

Why it matters:
- we already have a concrete structure for tone, speech rate, provider voice mapping, and tuning workflow

5. Voice-specific text rules
- `voice/SPARK_VOICE_SYSTEM.md`
- short sentences
- concrete wording
- punctuation for cadence
- calm/confident/concise default

Why it matters:
- good spoken output is not just TTS, it starts with voice-friendly text composition

## Product Order

### Phase 1: Make Telegram STT real and honest

Goal:
- a Telegram voice note becomes transcript text in Builder through this chip

Needed:
- verify one production STT provider end to end
- keep current honest failure when provider compatibility is unknown
- add deterministic fallback mode for tests and controlled degraded runtime

Deliverables:
- `voice.transcribe` supports at least one verified provider
- explicit provider compatibility matrix in this repo
- deterministic fallback transcript mode for degraded testing
- transcript metadata in result payload:
  - `transcript_text`
  - `provider_id`
  - `model`
  - `mode` such as `provider` or `fallback`

Success criteria:
- Telegram voice note roundtrip works on the canonical Builder home
- degraded mode returns bounded, operator-readable failure or fallback transcript

### Phase 2: Add canonical voice profile support

Goal:
- make Spark sound like the same agent across systems

Needed:
- add a repo-owned voice profile file
- adapt the `spark-pc-voice-link` profile structure instead of inventing a new one

Recommended files:
- `voices/spark_core.voice_profile.json`
- `docs/VOICE_TUNING_PLAYBOOK.md`

Core fields to keep:
- tone identity
- warmth / energy / formality
- default rate
- allowed rates
- default emotion
- provider voice mapping
- fallback voice mapping

Success criteria:
- one canonical profile is readable by this chip
- profile can be referenced by future `voice.speak` and `voice.status`

### Phase 3: Add TTS as a chip hook

Goal:
- Builder can ask the chip to synthesize a persona-consistent voice reply

Recommended new hook:
- `voice.speak`

Suggested payload:
- `text`
- `voice_profile_id`
- `surface`
- `human_id`
- `agent_id`
- optional `emotion`
- optional `format`

Suggested result:
- `audio_base64` or file artifact path
- `mime_type`
- `provider_id`
- `voice_id`
- `mode`

Current status:
- `voice.speak` is now implemented with an ElevenLabs-backed first provider path
- Builder integration is available where the host runtime attaches and approves this chip
- Telegram-compatible voice-note output is supported through the `surface=telegram` hook payload
- remaining work includes host-runtime activation, voice-quality tuning, and evaluation

Important rule:
- first make TTS work as an internal hook
- only after that decide whether Telegram should receive actual voice-note replies by default or only when requested

Success criteria:
- one provider-backed TTS path works
- voice output remains bounded and stable
- provider voice fallback is explicit

### Phase 4: Add Telegram audio reply delivery

Goal:
- Builder can send audio replies back into Telegram, not just text

Needed in Builder later:
- Telegram send-audio / send-voice client support
- routing rule for when to send text, audio, or both

Recommended first mode:
- text remains the safe visible caption mode
- voice-origin turns can request audio only after explicit operator approval
- optional audio reply mode remains available for later text turns
- command examples:
  - `/voice reply on`
  - `/voice reply off`
  - `/voice speak <text>`

Success criteria:
- text remains the safe visible default
- audio reply can be explicitly enabled without degrading core Telegram usability
- Builder can pass a more voice-friendly spoken string into `voice.speak` than the caption it keeps in Telegram

### Phase 5: Add tuning and evaluation

Goal:
- voice quality should be testable, not just subjective

Needed:
- benchmark prompts from the existing tuning playbook
- evaluation notes for:
  - clarity
  - pacing
  - confidence
  - warmth
  - latency
  - consistency with Builder persona

Recommended future hooks:
- `voice.profile`
- `voice.evaluate`

Success criteria:
- one repeatable tuning loop exists
- the chosen voice configuration can be accepted or rejected on concrete criteria

## Immediate Tasks

1. Improve voice-specific text shaping and reply-length rules using live Telegram conversations.
2. Add a repeatable voice tuning checklist and evaluation prompts for normal operator use.
3. Decide whether spoken replies should be shorter than text captions by default on every surface, not just Telegram.
4. Verify whether the current ElevenLabs voice remains the right canonical default after real usage.
5. Keep Builder/personality/voice boundaries explicit as the operator style evolves.

## Open Questions

1. Which provider should be the primary STT path for Telegram:
- OpenAI
- OpenAI-compatible custom endpoint
- local fallback only for some environments

2. Which provider should be the primary TTS path:
- ElevenLabs
- Minimax
- browser playback for non-Telegram surfaces only

3. Should Telegram audio replies be:
- opt-in
- opt-out
- only available via explicit command

My recommendation:
- STT first
- TTS second
- audio reply delivery third

## Near-Term Definition Of Done

This repo is in a good first operational state when:
- `/voice` reports a verified provider honestly
- Telegram voice note transcription works on an attached Builder home
- one canonical voice profile exists in this repo
- `voice.speak` is implemented without publishing private provider voice ids
- all remaining voice logic stays modular here rather than moving back into Builder
