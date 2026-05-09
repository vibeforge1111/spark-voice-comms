# Voice Hardening Map

License: AGPL-3.0-only.

Status: proposed implementation map

This map captures the next improvements for `spark-voice-comms` and its Builder/Telegram integration. The goal is to make voice faster, clearer, easier to debug, and harder to regress without disturbing the stable path that now works.

## Current Stable Path

The working production direction is:

```text
Telegram update
-> spark-telegram-bot normalization
-> Spark Intelligence Builder turn handling
-> memory, wiki, character, and routing context
-> spark-voice-comms hook call when speech is needed
-> Telegram voice delivery
```

Current stable user controls:

- `/voice`
- `/voice status`
- `/voice map`
- `/probe voice`
- `/voice provider`
- `/voice onboard local`
- `/voice onboard paid`
- `/voice reply on`
- `/voice reply off`
- `/voice ask <question>`
- `/voice speak <text>`
- `switch my voice to ElevenLabs`
- `use Kokoro for voice`
- `use GPT Realtime 2 for voice`
- `find me a natural geeky QA tester voice`
- `use voice Elise`
- `make it warmer`
- `a little faster`
- `audition the voice`

## Non-Regression Invariants

These must stay true through every improvement:

- Builder owns reasoning, memory usage, character/personality, and final answer composition.
- `spark-voice-comms` owns speech I/O only: STT, TTS, provider calls, audio metadata, and provider readiness.
- Telegram bot owns Telegram delivery and user command surface.
- `spark-character` owns style/persona constraints, not provider readiness.
- Voice provider availability is not inferred from chat LLM availability.
- `voice.speak` reads the supplied Builder answer; it must not invent a second answer.
- `/voice speak <text>` reads exact text.
- `/voice ask <question>` generates an answer first, then speaks that answer.
- Voice tuning phrases stay in the voice route and must not trigger Spawner or project-build flows.
- Secrets stay in local config or Spark's secret layer, never in Telegram, examples, screenshots, or git.
- Legacy `domain-chip-voice-comms` is migration vocabulary only; the canonical chip is `spark-voice-comms`.

## Ownership Matrix

Use this table when deciding where a fix belongs. Most regressions came from the same behavior being owned in more than one place.

| Concern | Owner | Must not be owned by |
| --- | --- | --- |
| User message ingress and Telegram command parsing | `spark-telegram-bot` | voice provider adapters |
| Route choice, memory, personality, spoken answer composition | Spark Intelligence Builder | `spark-voice-comms` |
| STT, TTS, provider calls, audio bytes, provider readiness | `spark-voice-comms` | Telegram bot or character docs |
| Telegram `sendVoice`, file download, format conversion | `spark-telegram-bot` plus Builder bridge | `spark-voice-comms` hook code |
| Character, tone, spoken style constraints | `spark-character` | provider readiness checks |
| Long-running build/project missions | Spawner | voice tuning phrases |
| Persistent user/DM/agent voice preference | Builder runtime state scoped by agent, Telegram profile, and DM | global voice profile files alone |
| Provider secrets | local env or Spark secret layer | Telegram messages, docs, logs, git |

## Fighting Elements To Remove Or Contain

These are the concrete conflict sources observed in live testing:

- `domain-chip-voice-comms` appearing as a second active voice chip. Keep it only as an alias/migration term; runtime status should point to `spark-voice-comms`.
- Voice commands falling through to the dashboard/resonance fallback. `/voice`, `/voice ask`, `/voice speak`, `/voice provider`, and reply toggles must be claimed before generic unsupported-surface handlers.
- Voice tuning phrases being interpreted as project build requests. Phrases like `make it warmer`, `a little faster`, `audition the voice`, and `use voice Elise` must stay in the voice preference route when a voice-tuning context is active.
- `/voice speak` echoing the prompt instead of reading intended text. Exact-read behavior is correct only for `/voice speak`; `/voice ask` must answer first.
- Text and audio being generated as separate answers. Builder should create one canonical answer, then derive a spoken variant and optional caption from it.
- Synthesis success being treated as Telegram delivery success. Delivery is only proven after `sendVoice` returns a successful Telegram message result.
- Provider readiness being inferred from the active chat LLM. GLM, MiniMax, Codex CLI, or any text provider should not imply STT/TTS readiness without a dedicated voice adapter.
- Voice tuning state bleeding across agents or named profiles. Host runtimes should read/write provider and profile preferences by agent + Telegram profile + DM when possible, and avoid legacy DM-only fallback for non-default profiles.
- User-facing diagnostics sounding like failures when setup is healthy. Normal replies should be conversational; raw paths, env names, and stack detail belong in explicit operator diagnostics.

## Runtime Claim Levels

Voice status should use claim levels instead of a single ready/not-ready flag:

1. `configured`: local references or provider refs exist.
2. `synthesis_ready`: `voice.speak` can return audio bytes for the selected provider.
3. `delivery_ready`: Telegram `sendVoice` has worked for this chat or runtime.
4. `conversation_ready`: voice note input, Builder answer generation, spoken output, reply toggle, and memory/personality route have all worked together.

User-facing `/voice` should only say "ready" for the level it can prove. For example, ElevenLabs can be configured while Telegram delivery is still unverified.

## What Needs To Improve

### 1. Canonical Voice Runtime State

Today, voice truth is spread across `/voice`, `/voice provider`, `/probe voice`, per-DM state, env/config, hook output, and Telegram send behavior.

Target: create one canonical voice runtime state object that every surface can render from.

Current progress:

- Builder emits `spark.voice_runtime_state.v1` from `voice.speak` and Telegram delivery paths.
- Telegram delivery proof is recorded back into Builder runtime state after `sendVoice`.
- `/voice` now appends the same scoped Builder profile state and last delivery proof used by provider/dashboard surfaces.
- Spawner UI `/voice-system` reads live Builder profile and delivery proof directly, so `/voice dashboard` is no longer required after every voice reply just to refresh status.

Suggested shape:

```json
{
  "schema_version": "spark.voice_runtime_state.v1",
  "generated_at": "iso timestamp",
  "surface": "telegram",
  "dm_voice_replies": "on|off|unknown",
  "canonical_chip_key": "spark-voice-comms",
  "legacy_alias_visible": false,
  "stt": {
    "provider_id": "faster-whisper|openai|custom|none",
    "mode": "local|hosted|unknown",
    "ready": true,
    "last_probe_ref": "voice.status:...",
    "claim_boundary": "Transcription readiness is not Telegram delivery proof."
  },
  "tts": {
    "provider_id": "elevenlabs|kokoro|openai-realtime|pyttsx3|none",
    "mode": "local|hosted|unknown",
    "voice_name": "masked or public display name",
    "voice_id_masked": "abc123-xyz9",
    "settings_fingerprint": "short hash",
    "ready": true,
    "last_probe_ref": "voice.speak:..."
  },
  "telegram_delivery": {
    "ready": true,
    "last_send_voice_at": "iso timestamp",
    "last_send_voice_status": "success|failure|unknown",
    "last_failure_reason": ""
  },
  "latency": {
    "download_audio_ms": 0,
    "transcribe_ms": 0,
    "builder_answer_ms": 0,
    "synthesize_ms": 0,
    "convert_audio_ms": 0,
    "send_voice_ms": 0,
    "total_ms": 0
  },
  "source_ledger": [
    "voice.status",
    "per-dm-state",
    "telegram-sendVoice-trace",
    "builder-runtime-provider"
  ]
}
```

Renderers should read this state instead of reconstructing their own truth.

Affected surfaces:

- `/voice`
- `/voice provider`
- `/voice map`
- `/probe voice`
- Builder Agent Operating Context
- Telegram diagnostics
- future Spawner or dashboard views

### 2. Delivery Evidence

Voice currently proves synthesis better than it proves Telegram delivery.

Target: record first-class delivery evidence after Telegram `sendVoice`.

Record:

- provider id
- voice id masked or fingerprinted
- mime type
- voice-compatible flag
- audio duration if known
- audio byte size
- synthesis latency
- conversion latency
- Telegram send latency
- Telegram message id when safe
- failure reason when not delivered

This should feed `/probe voice` and Agent Operating Context.

### 3. Latency Trace

The user experience felt slow in live tests. We need timing by leg, not guesses.

Trace segments:

1. Telegram file metadata fetch
2. Telegram file download
3. STT hook
4. Builder answer generation
5. spoken-text preparation
6. TTS hook
7. audio conversion to Telegram-compatible Opus
8. Telegram `sendVoice`

Target:

- show concise timing in diagnostics
- keep noisy details out of normal user replies
- store enough detail to identify the slow provider or conversion step

### 4. Text And Audio Coherence

Voice replies previously produced different text and audio content in some paths.

Target policy:

- `/voice speak`: caption can be short, audio reads exact supplied text.
- `/voice ask`: Builder answer is canonical; audio speaks the prepared spoken variant of that same answer.
- voice reply mode: text caption should be either omitted, short, or a faithful preview of spoken content.
- never send a long unformatted text blob beside a polished voice answer.
- avoid dual-answer behavior where the text says one thing and the audio says another.

Suggested fields:

```json
{
  "builder_answer_text": "...",
  "spoken_text": "...",
  "caption_text": "...",
  "coherence_mode": "exact|spoken_variant|caption_preview",
  "coherence_check": "passed|failed|not_run"
}
```

### 5. Provider Profiles And Calibration

ElevenLabs tuning is useful but still shallow.

Target:

- save named voice profiles per DM/user/agent
- preserve provider, voice id, model id, settings, and settings fingerprint
- keep a small audition history
- allow natural language tuning without mission-control collisions
- support rollback to baseline voice profile

Examples:

- `make it warmer`
- `less polished`
- `a little faster`
- `save this as QA Spark`
- `go back to the previous voice`

### 6. Local Voice Path

Kokoro should become as easy to understand as ElevenLabs.

Target:

- local readiness state separates package installed from model files connected
- user-facing onboarding stays conversational
- operator diagnostics can still show local config details when explicitly requested
- voice selection and speed/tone hints are available for Kokoro where supported
- local path has an acceptance test with real or mocked Kokoro output

### 7. Provider Adapter Roadmap

Current supported/near-supported roles:

- faster-whisper: local STT
- OpenAI-compatible STT: hosted transcription
- ElevenLabs: polished hosted TTS and voice calibration
- Kokoro: private/free local neural TTS
- GPT Realtime 2: OpenAI hosted voice path
- pyttsx3: basic local system TTS fallback

Future explicit adapters:

- MiniMax speech
- Z.ai/GLM speech if verified

Do not report MiniMax or Z.ai/GLM voice as ready just because their chat providers are configured.

## Phased Implementation Plan

### Phase A - State Unification

- [x] Add `VoiceRuntimeState` builder-side contract.
- [x] Normalize `voice.status`, per-DM provider state, env-derived profile, and delivery evidence into that contract for the Telegram voice path.
- [x] Render `/voice`, `/voice provider`, `/voice map`, and `/voice-system` from shared Builder state where current code supports it.
- Add regression tests for each renderer using the same state fixture.
- Make legacy chip aliases collapse into the canonical `spark-voice-comms` identity before rendering.

Exit gate:

- same fixture produces consistent provider/readiness claims across all voice surfaces
- no secrets or raw local paths appear in user-facing renderers
- the dashboard/resonance fallback cannot answer known voice commands

### Phase B - Delivery Trace

- [x] Capture successful Telegram `sendVoice` evidence.
- [x] Capture failed Telegram delivery with safe failure reason.
- [x] Record delivery evidence into Builder runtime state.
- Include delivery status in `/probe voice`.

Exit gate:

- a synthesized-but-not-delivered reply is reported as partial readiness
- a delivered Telegram voice message becomes last-success evidence
- `/voice` can explain whether failure happened in synthesis, conversion, or Telegram delivery

### Phase C - Latency Trace

- Add timing segments around download, STT, Builder answer, TTS, conversion, and delivery.
- Keep timing in trace fields and diagnostics, not normal chat unless requested.
- Add tests that preserve timing fields through the bridge payload.

Exit gate:

- one live voice-note round trip can identify its slowest leg

### Phase D - Coherence Policy

- Add a shared text/audio coherence policy.
- Enforce `/voice speak` exact-read behavior.
- Enforce `/voice ask` generated-answer-then-speak behavior.
- Improve captions for long spoken answers.
- Add tests for no dual-answer mismatch.
- Add a route guard so natural voice requests do not trigger self-improvement plans unless the user explicitly asks for self-improvement.

Exit gate:

- text caption and audio content cannot diverge silently
- long text captions are composed with paragraphs or suppressed in favor of audio
- normal voice requests stay conversational and do not produce route-planning residue

### Phase E - Voice Profiles

- Store named provider profiles with fingerprints.
- [x] Add scoped rollback to previous profile/provider for Telegram voice tuning.
- Add audition history.
- Keep per-DM overrides separate from global defaults.

Exit gate:

- `use voice X`, `make it warmer`, `audition`, and rollback work without Spawner collisions
- status shows masked/fingerprinted profile identity
- natural tuning phrases are handled even when the user does not use slash commands

### Phase F - Local Path Polish

- Improve Kokoro onboarding state.
- Add local voice selection hints.
- Add mocked Kokoro acceptance tests.
- Document model-file setup without making Telegram replies look like failures.

Exit gate:

- local users can understand what remains without seeing raw config dumps

## Test Matrix

Unit tests:

- `voice.status` local/hosted/custom states
- `voice.speak` providers: ElevenLabs, Kokoro, OpenAI Realtime, pyttsx3
- redaction of provider errors
- Telegram Opus conversion
- natural language routing for provider switch, voice search, tuning, audition
- voice tuning does not trigger Spawner
- `/voice ask` does not echo the prompt
- `/voice speak` reads exact text

Integration tests:

- Builder runtime command: `/voice`
- Builder runtime command: `/voice map`
- Builder runtime command: `/probe voice`
- Telegram bridge sends voice media payload
- delivery success and failure traces
- caption/spoken text coherence

Live smoke tests:

1. `/voice`
2. `/voice provider`
3. `find me a natural geeky QA tester voice`
4. `use voice <name>`
5. `audition the voice`
6. `make it warmer`
7. `/voice ask Say one warm QA-style sentence with the current voice.`
8. `/voice reply on`
9. normal text question gets voice reply
10. Telegram voice note gets transcribed and answered
11. `/voice reply off`
12. normal text question stays text-only

Security checks:

- no real API keys
- no Telegram IDs
- no private voice IDs
- no local operator paths in public docs
- no recordings, transcripts, or generated audio committed

## Production Release Order

Ship in this order to avoid destabilizing the working path:

1. Add tests around current working behavior before refactoring.
2. Add `VoiceRuntimeState` as an internal contract and keep existing renderers.
3. Move one renderer at a time to the shared state: `/voice`, then `/voice provider`, then `/probe voice`, then `/voice map`.
4. Add delivery evidence without changing provider selection.
5. Add latency trace fields without changing user-facing replies.
6. Add coherence checks and route guards.
7. Add profile persistence and voice tuning improvements.
8. Only then expand provider adapters.

Each step should have a small rollback: turn off the new renderer or trace field and keep the stable hooks untouched.

## Rollback Plan

Every phase should be reversible:

- Keep current `/voice` commands stable.
- Keep current provider env names stable.
- Keep `spark-voice-comms` hook names stable.
- Add new runtime state as an internal data contract first.
- If state unification regresses live Telegram, render from old code path while keeping traces for debugging.
- If a provider adapter fails, fall back to text reply with a safe reason and keep voice reply mode unchanged.

## Recommended Next Step

Start with Phase A and Phase B together:

1. Define `VoiceRuntimeState`.
2. Make `/voice`, `/voice provider`, and `/probe voice` render from it.
3. Record Telegram `sendVoice` success/failure as delivery evidence.

That gives the biggest reliability improvement without changing provider behavior.
