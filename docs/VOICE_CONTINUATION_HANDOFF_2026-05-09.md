# Voice Continuation Handoff

License: MIT.

Date: 2026-05-09

This handoff captures the next useful voice-system work after the `spark-voice-comms` v0.1.1 release.

## Current Stable State

- `spark-voice-comms` is public and MIT-licensed as of v0.1.1.
- Telegram live smoke passed for ElevenLabs, GPT Realtime 2, and Kokoro.
- `/voice map`, `/voice provider`, `/voice ask`, `/voice reply on/off`, `/voice dashboard`, and `/voice-system` are working through the host Spark runtime.
- `/voice install local` installs the private/free local stack in Spark's active Python runtime:
  - local STT: `faster-whisper`
  - local neural TTS: `kokoro-onnx` + `soundfile`
- Builder owns conversation, memory, personality, provider selection, scoped voice preferences, and Telegram composition.
- `spark-voice-comms` owns STT/TTS hooks, provider adapters, runtime-state payloads, audio bytes, and local install helpers.
- Spawner UI owns the visual `/voice-system` observability surface and must remain redacted.

## Non-Negotiable Boundaries

- Do not revive `spark-voice-engine` as the current public voice system.
- Do not reintroduce `domain-chip-voice-comms` as a competing voice chip.
- Do not ask users to paste provider keys into Telegram.
- Do not expose Telegram tokens, API keys, transcripts, recordings, generated audio, full hosted voice IDs, or private runtime paths in docs, dashboards, logs, or release notes.
- Do not claim voice delivery from synthesis alone. Telegram `sendVoice` proof is the delivery proof.
- Do not infer voice readiness from the active chat LLM provider. MiniMax, Z.ai/GLM, OpenAI, or any chat provider needs a dedicated voice adapter/probe before it is called ready.

## Handoff 1 - Richer `/voice-system` Dashboard

Goal:
Make the visual dashboard useful as an operator cockpit, not only a proof snapshot.

Candidate features:

- Provider switch actions that route through Builder's existing voice provider path.
- Copy-safe setup hints with placeholders only.
- Last 5 voice events:
  - provider switch
  - voice search/select
  - tuning mutation
  - synthesis result
  - Telegram delivery result
- Latency waterfall:
  - Telegram file metadata
  - media download
  - STT
  - Builder answer
  - spoken-text preparation
  - TTS
  - audio conversion
  - Telegram `sendVoice`
- Per-agent voice matrix:
  - agent/profile label
  - provider
  - masked voice ID
  - voice name
  - reply toggle
  - last delivery status

Architecture notes:

- Spawner UI should not own provider credentials or mutate provider state directly.
- Any action button must call a Builder-owned route or emit a copyable Telegram command.
- The dashboard should keep using redacted Builder runtime state.
- If multiple users/agents are present, avoid reading a single global "latest profile" row as truth for all scopes.

Verification:

```bash
npm run check
npm run test:run -- src/routes/voice-system/voice-system-route.test.ts
```

Manual smoke:

- Switch provider in Telegram.
- Send `/voice ask`.
- Open `/voice-system`.
- Confirm provider, masked voice, scope, last delivery, and latency fields match the latest run.

## Handoff 2 - Voice Rollback History

Goal:
Let users recover from voice tuning experiments without guessing what changed.

Candidate behavior:

- Keep the current one-step rollback behavior.
- Add a small scoped history buffer per agent/profile/DM.
- Support natural phrases:
  - `show my recent voice changes`
  - `go back two voice changes`
  - `restore the voice from before Elise`
  - `reset this agent voice only`

Architecture notes:

- Builder should own scoped preference history.
- Store redacted diffs only:
  - provider ID
  - voice name
  - masked voice ID
  - settings fingerprint
  - human-readable tuning direction
- Do not store provider keys, raw voice IDs, audio, or transcripts in rollback history.
- Keep rollback scoped to the current agent/profile/DM unless the operator explicitly requests a broader scope.

Verification:

```bash
python -m pytest tests/test_operator_pairing_flows.py -k "voice_undo or voice_history or voice_scope" -q
```

Manual smoke:

- Select an ElevenLabs voice.
- Tune it warmer.
- Tune it faster.
- Ask for recent voice changes.
- Roll back one step.
- Confirm another agent/profile did not change.

## Handoff 3 - MiniMax TTS Adapter

Goal:
Add MiniMax as a real voice provider only after the official speech endpoint contract is verified.

Current state:

- Env placeholders exist.
- Docs describe MiniMax as planned.
- It must not be reported as ready from chat-provider configuration alone.

Implementation checklist:

- Verify official MiniMax speech endpoint, auth headers, model IDs, request body, response format, and rate limits.
- Add adapter code behind `provider_id=minimax`.
- Add config validation for:
  - `MINIMAX_API_KEY`
  - `VOICE_TTS_MINIMAX_BASE_URL`
  - `VOICE_TTS_MINIMAX_GROUP_ID`
  - `VOICE_TTS_MINIMAX_MODEL`
  - `VOICE_TTS_MINIMAX_VOICE_ID`
- Return audio bytes in a channel-adapter-friendly format.
- Add friendly failure copy for missing group ID, invalid key, quota/billing, and unsupported voice/model.
- Update provider docs only after the smoke test passes.

Verification:

```bash
python -m pytest -q
```

Manual smoke:

- Configure MiniMax in local secret layer.
- Switch provider through Telegram.
- `/voice ask Give me one short MiniMax voice sentence.`
- Confirm audio arrives and `/voice-system` shows delivery proof.

## Handoff 4 - Z.ai / GLM Voice Adapter

Goal:
Add Z.ai/GLM speech only if a verified TTS/STT endpoint exists.

Current state:

- Z.ai is a chat/model provider in Spark environments.
- GLM voice should be treated as planned until a speech endpoint is verified.
- Do not assume Z.ai chat compatibility means voice compatibility.

Implementation checklist:

- Verify official Z.ai/GLM speech endpoint and response format.
- Decide whether the first adapter is TTS-only or both STT/TTS.
- Add adapter code behind `provider_id=zai`.
- Add config validation for:
  - `ZAI_API_KEY`
  - `VOICE_TTS_ZAI_BASE_URL`
  - `VOICE_TTS_ZAI_MODEL`
  - `VOICE_TTS_ZAI_VOICE`
- Add provider-specific failure copy.
- Keep `voice.status` honest when only chat provider state exists.

Verification:

```bash
python -m pytest -q
```

Manual smoke:

- Configure Z.ai/GLM voice credentials in local secret layer.
- Switch provider through Telegram.
- Run `/voice ask`.
- Confirm real audio delivery and dashboard proof before marking ready.

## Handoff 5 - Realtime / Non-Telegram Streaming Voice

Goal:
Explore streaming voice as a separate surface without complicating Telegram voice notes.

Current state:

- Telegram remains turn-based:
  - voice note in
  - Builder answer
  - voice note out
- GPT Realtime 2 is available as a hosted TTS-style path through `voice.speak`.

Candidate surfaces:

- local desktop voice loop
- browser voice session
- dedicated realtime agent room
- push-to-talk operator console

Architecture notes:

- Keep streaming voice separate from Telegram command handling.
- Reuse Builder personality, memory, and scoped voice preferences.
- Add interruption/barge-in only where the channel supports it.
- Preserve source-ledger and memory discipline: audio/transcript residue should not become durable memory without explicit policy.
- Keep cost and latency visible.

Verification:

- Streaming session starts/stops cleanly.
- Barge-in or interruption does not corrupt the Builder turn.
- Transcript and spoken answer stay aligned.
- No private audio/transcripts are written to public logs.

## Suggested Order

1. Dashboard event history and latency waterfall.
2. Voice rollback history.
3. MiniMax adapter.
4. Z.ai/GLM adapter.
5. Realtime/non-Telegram streaming surface.

The dashboard and rollback work improve every provider. Provider adapters should come after the observability and recovery surfaces are strong enough to debug them.
