# Changelog

License: AGPL-3.0-only.

## 0.1.0 - Unreleased

Initial public-ready Spark voice chip.

- Added Spark hook manifest for `voice.status`, `voice.plan`, `voice.onboard`, `voice.transcribe`, and `voice.speak`.
- Added OpenAI-compatible speech-to-text support.
- Added ElevenLabs text-to-speech support.
- Added optional local/free TTS via `pyttsx3`.
- Added deterministic fallback transcripts for safe smoke tests.
- Added optional local faster-whisper fallback support.
- Added Telegram-oriented Opus output selection for hosted TTS.
- Added deployment runbook, provider options, and agent onboarding playbook.
- Documented natural-language Telegram voice onboarding, provider switching, ElevenLabs audition/tuning, Kokoro local setup, GPT Realtime 2 hosted setup, scoped rollback, and live dashboard proof boundaries.
- Added AGPL-3.0-only license.
