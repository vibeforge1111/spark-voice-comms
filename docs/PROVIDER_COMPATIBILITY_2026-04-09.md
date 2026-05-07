# Provider Compatibility

Date: April 9, 2026

License: AGPL-3.0-only.

## Purpose

This file tracks which providers are actually safe to use for `spark-voice-comms`, instead of assuming that any Builder provider can do STT or TTS.

## Speech To Text

### Verified

- `openai`
  - status: verified contract target
  - expected endpoint: `/audio/transcriptions`
  - expected auth: bearer API key
  - notes: this is the primary contract the chip currently implements

### Supported But Not Yet Verified On The Live Builder Home

- `custom`
  - status: unverified
  - requirement: must be OpenAI-compatible for `/audio/transcriptions`
  - known failure mode: a custom endpoint may return `Voice provider HTTP 404` when it does not expose the expected transcription path
  - policy: `voice.status` must report this as not ready until proven

### Not Supported In The Current STT Hook

- `anthropic`
  - reason: no compatible `/audio/transcriptions` path in the current hook contract
- OAuth-only runtimes
  - reason: current hook expects env-backed API key transport for STT

### Deterministic Fallback

- status: supported for degraded testing
- activation: set `fallback_mode=deterministic` in the `voice.transcribe` payload
- purpose:
  - keep voice-loop tests runnable when provider STT is intentionally unavailable
  - provide bounded degraded output instead of a hard failure when testing fallback paths
- rule:
  - fallback is opt-in
  - normal live operation should still prefer verified provider STT

## Text To Speech

### Implemented

- `pyttsx3`
  - status: optional local/free TTS path
  - expected runtime: installed Python package plus operating-system voices
  - expected auth: none
  - output: WAV
  - policy: useful for onboarding and local smoke tests; channel adapters may need conversion for Telegram voice notes

- `elevenlabs`
  - status: first `voice.speak` provider path
  - expected endpoint: `/text-to-speech/{voice_id}`
  - expected auth: `xi-api-key` from env-backed secret
  - voice id source: local `VOICE_TTS_ELEVENLABS_VOICE_ID`, hook payload `tts.voice_id`, or a private profile override
  - fallback behavior: retry once with a resolved fallback voice when the primary voice id is missing

### Not Implemented Yet

- `minimax`
  - useful existing Spark voice mappings already exist
- `browser_speechsynthesis`
  - should remain a non-Telegram fallback for local/browser surfaces, not the main Telegram voice path

## Decision Rule

Do not mark a provider as ready in `voice.status` until:
- one real request succeeds
- the expected endpoint contract is known
- failures are bounded and explained

## Next Updates

Update this file when:
- `voice.speak` lands
- an attached Builder home gets a verified STT provider
- any custom provider is proven compatible enough to move from unverified to verified
