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

## Telegram Self-Awareness

Spark should be able to answer:

- what voice provider is active for this Telegram DM
- whether voice replies are on or off
- what the active ElevenLabs voice/profile is
- whether `voice.status` currently reports STT/TTS ready
- whether a real Telegram voice send has been tested

The Builder-side `/voice map`, `/voice provider`, `/voice status`, and `/probe voice` commands are the runtime-facing surfaces for those answers.

## Security Boundary

Never place API keys in Telegram messages, docs, examples, screenshots, or committed config. Use environment variable names and masked IDs only.

