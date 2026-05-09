# Spark Voice Experience Plan

License: AGPL-3.0-only.

Status: active

## Goal

Make voice feel like a natural Spark surface: users can ask their Telegram agent to set up voice, choose a free local path or a paid provider path, test it safely, and hear replies that preserve the agent's current Spark personality and character.

## Repo Roles

- `spark-telegram-bot`: Telegram ingress, user command surface, and Builder bridge.
- `spark-intelligence-builder`: route policy, provider/env boundary, memory scope, personality state, reply shaping, Telegram media fetch/delivery.
- `spark-voice-comms`: speech I/O hooks only: status, plan, onboarding, transcription, synthesis, and voice profile metadata.
- `spark-character`: canonical Spark character renderer, surface overlays, voice-specific spoken style, and drift/eval harness.
- `spark-personality-chip-labs`: user-selectable personality chips, EQ traits, room reading, bounded personality evolution inputs.
- memory and recursion systems: source-grounded learning, daily improvement candidates, evals, rollback, and promotion gates.

## Phase 1 - Plug-In Onboarding

- [x] Publish `spark-voice-comms` with `voice.status`, `voice.plan`, `voice.onboard`, `voice.transcribe`, and `voice.speak`.
- [x] Keep provider keys, voice ids, recordings, transcripts, and generated audio out of the repo.
- [x] Add Telegram-friendly onboarding docs for local/free and paid/provider paths.
- [x] Make onboarding replies recommendation-shaped instead of menu-shaped, using visible runtime/provider evidence where available.
- [ ] Verify `/voice`, `/voice onboard`, `/voice onboard local`, and `/voice onboard paid` round-trip through the live Telegram bot into Builder.
- [ ] Verify natural language setup prompts route to `voice.onboard`.

## Phase 1.5 - Contextual Voice Advisor

- [ ] Pass source-labeled Builder wiki and current-state memory hints into `voice.onboard` without turning them into instructions.
- [ ] Personalize recommendations from evidence: active LLM provider, local package/runtime capability, OS/device constraints, user-stated local/privacy/quality preferences, and Spark Character voice profile.
- [ ] Phrase recommendations as Spark judgment, not chatbot interrogation: one clear recommendation, why it fits, what is visible now, and the next safe setup move.
- [ ] Mention user preferences only when source-labeled evidence exists, for example "because your saved preference says you prefer local/private tooling."
- [ ] Keep provider adapter boundaries honest: recommend MiniMax or Z.ai/GLM only as configured/verified when their dedicated adapters exist.

## Phase 2 - Runtime Compatibility

- [ ] Attach and activate `spark-voice-comms` in the target Builder home.
- [ ] Keep legacy `domain-chip-voice-comms` compatibility only as an alias/migration path.
- [ ] Confirm Builder system registry reports Spark Voice through `spark-voice-comms`.
- [ ] Confirm Telegram `/voice speak <text>` returns audio when voice replies are explicitly allowed.
- [ ] Confirm voice note input transcribes, returns to the normal Builder conversation runtime, and does not bypass memory/personality policy.

## Phase 2.5 - Runtime Hardening

Detailed implementation map: [docs/VOICE_HARDENING_MAP_2026-05-09.md](docs/VOICE_HARDENING_MAP_2026-05-09.md)

- [ ] Add a canonical `VoiceRuntimeState` so `/voice`, `/voice provider`, `/voice map`, `/probe voice`, and diagnostics do not reconstruct conflicting readiness claims.
- [ ] Record Telegram `sendVoice` success/failure separately from TTS synthesis success.
- [ ] Add latency segments for download, transcription, Builder answer generation, TTS, conversion, and Telegram delivery.
- [ ] Enforce text/audio coherence: `/voice speak` reads exact text, `/voice ask` answers first then speaks that answer, and captions cannot silently diverge from audio.
- [ ] Guard natural voice tuning phrases so they do not trigger Spawner/project-build routes.
- [ ] Persist provider/voice calibration with masked or fingerprinted identity, audition history, and rollback.
- [ ] Keep user-facing voice onboarding conversational while operator diagnostics carry raw setup detail only on request.

## Phase 3 - Character And Personality

- [ ] Generate visible replies through Builder's active Spark personality and Spark Character contract.
- [ ] Generate spoken variants with Spark Character's `voice` surface constraints: short, declarative, no markdown, easy to listen to.
- [ ] Keep `spark-voice-comms` out of personality authorship. It renders audio; it does not rewrite identity.
- [ ] Pass only bounded metadata into `voice.speak`, such as `surface`, `voice_profile_id`, and provider TTS settings.
- [ ] Add a live eval that compares text reply and spoken reply for same-intent consistency.

## Phase 4 - User-Shaped Agents

- [ ] Let users choose or create a personality chip through natural language, without editing config files.
- [ ] Treat explicit user requests like "be warmer" or "be more concise" as bounded personality signals, not immediate full rewrites.
- [ ] Scope evolved traits per user and agent.
- [ ] Preserve reset and rollback: users can ask the agent to return to baseline.
- [ ] Never let personality expression override safety, truthfulness, privacy, or task completion.

## Phase 5 - Daily Improvement Loop

- [ ] Collect interaction outcomes as source-labeled evidence, not as instructions.
- [ ] Promote only stable, useful, source-grounded learning into durable memory.
- [ ] Run daily voice/personality evals against real failure classes: overclaiming voice, excessive verbosity, emotional overreach, markdown in spoken replies, and provider failure recovery.
- [ ] Require rollback conditions for any persisted prompt, personality, or memory mutation.
- [ ] Keep self-improvement in shadow/supervised mode until evals prove it improves actual user outcomes.

## Release Gate

- [ ] Tests pass in `spark-voice-comms`.
- [ ] Builder voice route tests pass.
- [ ] Telegram command conflict tests pass.
- [ ] Spark Character recognizes `spark-voice-comms` and the legacy alias.
- [ ] Sensitive scan finds no local paths, operator IDs, provider keys, private voice ids, recordings, transcripts, or generated audio.
- [ ] Live Telegram smoke passes for text onboarding, natural language onboarding, status, one safe local/provider smoke, and one failure fallback.
