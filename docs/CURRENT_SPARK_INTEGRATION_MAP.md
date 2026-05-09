# Current Spark Integration Map

This chip is the speech I/O layer for Spark. It is not the whole agent and it should not own personality, memory, or mission routing.

## Stable Telegram Path

1. Telegram receives the user's message.
2. `spark-telegram-bot` forwards the normalized update to Spark Intelligence Builder.
3. Builder loads route state, memory context, character/personality, and chip context.
4. Builder calls this chip when speech is needed:
   - `voice.transcribe` for Telegram voice/audio input.
   - `voice.speak` for spoken replies.
   - `voice.status` for current readiness.
   - `voice.onboard` and `voice.install` for guided setup.
5. Builder sends the final answer and optional voice payload back through the Telegram bot.

## Provider Roles

- Local/private: faster-whisper for STT and Kokoro for local neural TTS.
- Hosted/polished: ElevenLabs for natural TTS and calibration.
- OpenAI-hosted: GPT Realtime 2 as an OpenAI voice option when configured.
- Explicit future adapters: MiniMax and Z.ai/GLM should be verified through dedicated speech adapters before being reported as ready.

Chat LLM availability is not voice readiness. A provider can be a strong text model and still have no verified STT/TTS path.

## Character And Personality Boundary

Builder owns the final response text. `spark-character` can provide voice-surface style guidance and persona context, but this chip should speak the Builder answer rather than inventing a separate answer.

Use `/voice ask <question>` when Builder should answer first and then speak the answer.

Use `/voice speak <text>` only when exact supplied text should be read aloud.

## Multi-Agent Voice Preference Boundary

Voice provider choice and voice tuning are host identity state. They should live in Builder or the host runtime, not inside this chip.

For Telegram-facing Spark agents, the host should scope persistent TTS preferences by the most specific available identity:

1. agent + Telegram profile + Telegram DM
2. Telegram profile + Telegram DM
3. legacy Telegram DM-only state, only for the default profile

This prevents one agent's voice experiments from changing another agent's character voice. For example, a default DM ElevenLabs tuning should not override a named Parrot Cove profile unless the operator tunes Parrot Cove while that profile is active.

This chip can accept the selected provider/profile through the `tts` hook payload, but it should not decide which user, agent, or Telegram profile owns that preference.

## Telegram Self-Awareness

Spark should be able to answer:

- what voice provider is active for this Telegram DM
- which voice preference scope is active
- whether voice replies are on or off
- what the active ElevenLabs voice/profile is
- whether `voice.status` currently reports STT/TTS ready
- whether a real Telegram voice send has been tested

The Builder-side `/voice map`, `/voice provider`, `/voice status`, and `/probe voice` commands are the runtime-facing surfaces for those answers.

`/voice dashboard` is the visual layer for the same truth. Builder can write a redacted runtime snapshot for Spawner UI, and Spawner UI should render it at `/voice-system`. The dashboard should also read live Builder runtime state for the active provider/profile and last Telegram `sendVoice` proof, so users do not need to run `/voice dashboard` after every voice reply just to refresh delivery status.

That dashboard can show the active provider, masked voice ID, preference scope, runtime path, delivery proof, and ownership boundaries, but it must not receive provider keys, Telegram tokens, raw env values, or private account identifiers.

## Natural Voice Tuning

Telegram should let users tune voice in plain language without falling into project-build or mission-control routes.

Supported host-runtime examples:

- `find me a natural geeky QA tester voice`
- `use voice Elise`
- `audition the voice`
- `make it warmer`
- `a little faster`
- `go back to the previous voice`

Rollback is host-scoped. It should restore the previous voice profile/provider for the current agent + Telegram profile + DM only, not for every Spark agent on the machine.

## Security Boundary

Never place API keys in Telegram messages, docs, examples, screenshots, or committed config. Use environment variable names and masked IDs only.
