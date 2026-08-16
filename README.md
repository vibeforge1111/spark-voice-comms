# Spark Voice Comms

Give a Spark agent a voice.

License: MIT. See [LICENSE](./LICENSE).

`spark-voice-comms` is the public voice chip for Spark agents. It lets a Spark agent listen to voice notes and send spoken replies, especially through Telegram, while keeping the agent's personality, memory, permissions, and secrets in the main Spark runtime.

In plain English: this repo is the speech layer. Spark still decides what to say. This chip helps Spark turn audio into text and text back into audio.

## Installation

### Prerequisites

- Python 3.10 or later
- A Spark Builder runtime (see [Spark Intelligence](https://github.com/spark-ai/spark-intelligence))
- Git

### Quick Install

```bash
# Clone the repository
git clone https://github.com/spark-ai/spark-voice-comms.git
cd spark-voice-comms

# Install with development dependencies
python -m pip install -e ".[dev]"

# Verify installation
python -m pytest -q
```

### Add to Spark Builder

```bash
# Add the chip root to your Spark Builder home
python -m spark_intelligence.cli attachments add-root chips "<path-to-spark-voice-comms-parent>" --home "<spark-home>"

# Activate the chip
python -m spark_intelligence.cli attachments activate-chip spark-voice-comms --home "<spark-home>"

# Verify activation
python -m spark_intelligence.cli attachments run-hook voice.status --chip-key spark-voice-comms --home "<spark-home>"
```

### Install Voice Providers

**Local/Free (recommended for privacy):**

```bash
# Install both STT and TTS
python -m pip install -e ".[local-stt,local-tts]"

# Or install Kokoro for better TTS quality
python -m pip install -e ".[local-stt,local-kokoro]"
```

**ElevenLabs (hosted TTS):**

```bash
python -m pip install -e ".[elevenlabs]"
```

**OpenAI GPT Realtime 2:**

```bash
python -m pip install -e ".[openai-realtime]"
```

### Environment Setup

Copy the example environment file and configure your providers:

```bash
cp .env.example .env
# Edit .env with your provider keys (see Local Provider Setup section below)
```

See [.env.example](./.env.example) and [docs/VOICE_ENV_SECURITY.md](./docs/VOICE_ENV_SECURITY.md) for the full provider environment matrix and secure storage guidance.

## Start Here

If you already have a Spark Telegram agent with this chip attached, you should not need to read code or paste keys into chat. Ask your agent:

```text
/voice
/voice onboard
/voice map
Can you help me set up voice locally?
Guide me through ElevenLabs voice setup.
Find me a natural warm voice.
Use voice Elise.
Audition the voice.
Make it warmer and a little faster.
/voice ask Give me one short warm sentence with the current voice.
```

For the private/free local path, ask:

```text
/voice install local
```

That installs local listening (`faster-whisper`) and local speaking (`kokoro-onnx` + `soundfile`) into Spark's active Python runtime. If you only need one side:

```text
/voice install faster-whisper
/voice install kokoro
```

## Choose A Voice Path

Most users can choose one of these:

| Path | Best For | What To Ask Spark |
| --- | --- | --- |
| Local/free | Privacy, no hosted TTS cost, offline-friendly setup | `help me set up local voice` or `/voice install local` |
| ElevenLabs | Most polished, natural character voice | `guide me through ElevenLabs voice setup` |
| GPT Realtime 2 | OpenAI-hosted expressive voice experiments | `use GPT Realtime 2 for voice` |

MiniMax and Z.ai/GLM slots are documented as future adapter paths. Do not treat them as ready until a dedicated adapter and smoke test exist.

## What This Repo Owns

This chip lets a Spark Builder runtime add voice without absorbing voice code into the main agent. Builder keeps the conversation, identity, approvals, and channel transport. This repo owns only the speech I/O hooks:

- `voice.status`
- `voice.plan`
- `voice.onboard`
- `voice.install`
- `voice.transcribe`
- `voice.speak`

## What It Gives A Spark Agent

- speech-to-text for inbound voice/audio turns
- text-to-speech for spoken replies
- guided onboarding replies that Spark agents can show directly in Telegram
- a reusable voice profile shape
- provider compatibility checks
- deterministic fallback transcripts for tests and degraded smoke runs
- Telegram-friendly Opus output when `surface=telegram`

Voice is still an explicitly activated capability. Installing this chip does not grant a Spark agent microphone, Telegram delivery, provider credentials, or approval to speak. The host Spark runtime must attach the chip, provide local secrets, and decide when voice is allowed.

This is the public voice lab. Do not use or document the older `spark-voice-engine` work as the current public voice system.

## Safety Rules

- Do not paste provider keys into Telegram.
- Do not commit `.env` files, recordings, transcripts, generated audio, Telegram tokens, or hosted voice IDs.
- Keep real provider keys in the local Builder environment file or Spark secret layer.
- Treat `/voice`, `/voice map`, and `/voice-system` as redacted status surfaces, not places for secrets.
- A successful TTS call is not the same as Telegram delivery. Real proof is a successful Telegram `sendVoice` event.

## Current Public Boundary

Public and safe to use:

- voice hook code
- voice profile shapes
- deterministic fallback transcripts for tests
- provider compatibility docs
- local STT/TTS setup guidance

Private or review before sharing:

- provider keys
- recordings
- transcripts
- generated audio
- concrete hosted voice ids
- Telegram tokens or runtime state

The default Spark starter installer does not install every public lab automatically. `spark-voice-comms` is available as an optional chip/lab until it exposes the same installable module contract as the starter modules.

Current Spark integration map: [docs/CURRENT_SPARK_INTEGRATION_MAP.md](docs/CURRENT_SPARK_INTEGRATION_MAP.md).

## Telegram Experience

When the host Spark runtime wires this chip into Telegram, operators should be able to use natural language instead of managing provider details by hand:

- `guide me through ElevenLabs voice setup`
- `find me a natural geeky QA tester voice`
- `use voice Elise`
- `audition the voice`
- `make it warmer and more geeky`
- `go back to the previous voice`
- `/voice ask Give me one warm QA-style sentence with the current voice.`

The host owns those preferences and should scope them by agent, Telegram profile, and DM. This chip receives the resolved `tts` payload and speaks the Builder-authored answer.

The visual voice dashboard belongs to the host runtime too. In the current Spark Telegram path, Builder writes redacted voice state and Spawner UI renders it at `/voice-system`; the page can read live Builder profile and delivery proof without requiring `/voice dashboard` after every voice reply.

## For Spark Agents Reading This

When a user asks you about voice, be helpful in normal language first.

Good responses should:

- tell the user which path fits them best: local/free, ElevenLabs, or GPT Realtime 2
- mention what is already configured when runtime state proves it
- guide the next step in Telegram, such as `/voice install local`, `audition the voice`, or `switch my voice to ElevenLabs`
- keep secrets out of chat and point users to local config or Spark's secret layer
- explain failures as setup steps, not as scary stack traces

Avoid:

- claiming a provider is ready just because the chat LLM uses that company
- asking users to paste API keys into Telegram
- mixing voice tuning requests with project-building or Spawner mission creation
- saying audio was delivered unless Telegram `sendVoice` proof exists

## Quick Start

```bash
git clone <repo-url>
cd spark-voice-comms
python -m pip install -e ".[dev]"
python -m pytest -q
```

Add the repo as a Spark chip root and activate it from your Builder home:

```bash
python -m spark_intelligence.cli attachments add-root chips "<path-to-spark-voice-comms-parent>" --home "<spark-home>"
python -m spark_intelligence.cli attachments activate-chip spark-voice-comms --home "<spark-home>"
python -m spark_intelligence.cli attachments run-hook voice.status --chip-key spark-voice-comms --home "<spark-home>"
python -m spark_intelligence.cli attachments run-hook voice.onboard --chip-key spark-voice-comms --home "<spark-home>"
python -m spark_intelligence.cli attachments run-hook voice.install --chip-key spark-voice-comms --home "<spark-home>" --payload-json "{\"target\":\"kokoro\"}"
```

From Telegram, approved operators can also ask for the full local stack:

```text
/voice install local
```

That installs local listening (`faster-whisper`) and local speaking (`kokoro-onnx` + `soundfile`) into Spark's active Python runtime. For one side only, use `/voice install faster-whisper` or `/voice install kokoro`.

If your Builder CLI version supports `--payload-json`, you can run a deterministic local transcribe smoke without a provider:

```bash
python -m spark_intelligence.cli attachments run-hook voice.transcribe --chip-key spark-voice-comms --home "<spark-home>" --payload-json "{\"audio_base64\":\"ZmFrZS1hdWRpby1ieXRlcw==\",\"filename\":\"smoke.ogg\",\"mime_type\":\"audio/ogg\",\"fallback_mode\":\"deterministic\"}"
```

The same payloads are available as files under [`examples/`](./examples/):

```bash
python -m spark_intelligence.cli attachments run-hook voice.onboard --chip-key spark-voice-comms --home "<spark-home>" --payload-file examples/voice_onboard_local.json
python -m spark_intelligence.cli attachments run-hook voice.transcribe --chip-key spark-voice-comms --home "<spark-home>" --payload-file examples/voice_transcribe_fallback.json
```

## Local Provider Setup

Keep provider keys in your local Builder environment file or supported Spark secret layer. Do not commit `.env` files.

Voice env and local model paths are containment-checked. The checkout, `SPARK_HOME`, and `~/.spark` are trusted by default; use a narrow `SPARK_VOICE_ENV_ROOT` or `SPARK_VOICE_ASSET_ROOT` when your deployment keeps those files elsewhere. Custom provider secret names must also be explicitly opted in with `SPARK_VOICE_ALLOWED_SECRET_REFS`.

Hosted STT is still supported when you explicitly want it:

```text
VOICE_OPENAI_API_KEY=<your OpenAI API key>
VOICE_TRANSCRIBE_PROVIDER=openai
VOICE_TRANSCRIBE_SECRET_ENV_REF=VOICE_OPENAI_API_KEY
VOICE_TRANSCRIBE_BASE_URL=https://api.openai.com/v1
```

Free/local STT:

```bash
python -m pip install -e ".[local-stt]"
```

The default `VOICE_TRANSCRIBE_PROVIDER=auto` path expects local faster-whisper for Telegram voice notes. It will not silently fall through to hosted transcription if local STT is missing. Set `VOICE_TRANSCRIBE_PROVIDER=openai` only when you deliberately want hosted STT.

For TTS:

```text
ELEVENLABS_API_KEY=<your ElevenLabs API key>
VOICE_TTS_ELEVENLABS_VOICE_ID=<your ElevenLabs voice id>
VOICE_TTS_ELEVENLABS_MODEL_ID=eleven_turbo_v2_5
```

The public `voices/spark_core.voice_profile.json` intentionally does not ship a concrete ElevenLabs voice id. Bring your own voice id through local config or through the `tts.voice_id` hook payload.

Free/local TTS:

```bash
python -m pip install -e ".[local-tts]"
```

Then call `voice.speak` with:

```json
{
  "text": "Local voice test.",
  "tts": {
    "provider_id": "pyttsx3"
  }
}
```

For better free/local voice quality, install Kokoro support:

```bash
python -m pip install -e ".[local-kokoro]"
```

Set `VOICE_TTS_PROVIDER=kokoro`, `VOICE_TTS_KOKORO_MODEL_PATH`, and `VOICE_TTS_KOKORO_VOICES_PATH` to local Kokoro model files, then call `voice.speak`. You can still override a single call with `tts.provider_id`.

Local TTS is useful for zero-cost setup and desktop playback. Kokoro is the preferred private/free quality path when model assets are configured. Hosted TTS is still the simpler path for Telegram voice-note delivery.

OpenAI GPT Realtime 2 can also be used as a hosted voice provider:

```bash
python -m pip install -e ".[openai-realtime]"
```

```text
VOICE_OPENAI_API_KEY=<your OpenAI API key>
VOICE_TTS_PROVIDER=openai-realtime
VOICE_TTS_OPENAI_REALTIME_MODEL_ID=gpt-realtime-2
VOICE_TTS_OPENAI_REALTIME_VOICE=coral
```

This path uses the Realtime WebSocket API and returns WAV audio to the channel adapter. Keep the key in Builder's local env/secret layer, never in Telegram.

For the full provider env matrix and secure storage guidance, use [.env.example](./.env.example) and [docs/VOICE_ENV_SECURITY.md](./docs/VOICE_ENV_SECURITY.md).

## Runtime Boundary

Builder should:

- detect Telegram or other channel audio messages
- fetch channel media bytes
- pass bounded payloads into chip hooks
- keep personality, memory, approvals, visible reply text, and per-agent voice preference scope

This chip should:

- check provider compatibility
- transcribe audio
- synthesize speech
- resolve voice profile and provider voice mapping
- keep fallback behavior testable

Voice provider and tuning preferences should be scoped by the host runtime, not this chip. For Telegram, prefer agent + Telegram profile + DM state, then Telegram profile + DM state, and use legacy DM-only state only for default-profile compatibility. This keeps one agent's ElevenLabs/Kokoro/OpenAI tuning from changing another agent's character voice.

See [docs/BUILDER_BOUNDARY_2026-04-09.md](./docs/BUILDER_BOUNDARY_2026-04-09.md).

## Current Status

Implemented in this repo:

- `voice.status`
- `voice.plan`
- `voice.onboard`
- `voice.install`
- `voice.transcribe`
- `voice.speak`
- local deterministic fallback transcripts
- local faster-whisper by default for Telegram voice notes
- Telegram-targeted Opus output selection for `voice.speak`
- `runtime_state` on `voice.status`, `voice.transcribe`, and `voice.speak`, so hosts can render one readiness truth
- `delivery_trace` and `coherence` metadata on `voice.speak`, separating synthesis from Telegram delivery and caption/audio consistency

Activation status depends on the host Spark runtime. A Spark agent may have this chip installed but still report voice as unavailable until the operator approves the connector and provider setup is verified.

## Security

- Do not commit `.env` files, provider keys, recordings, transcripts, or generated audio.
- The chip reads provider secret values from local env files supplied by Builder; hook replies should not print secret values.
- Use fake placeholders in tests, not token-shaped examples.
- Review [SECURITY.md](./SECURITY.md) before making a fork public.

Important: before making an existing private repository public, scan the full git history too. If history contains private paths, token-shaped examples, or provider voice ids, publish from a fresh scrubbed repository or rewrite history before changing visibility.

## License

This repo is licensed under the MIT License. See [LICENSE](./LICENSE).

## Docs

- [Getting started with voice](./docs/GETTING_STARTED_WITH_VOICE.md)
- [Deployment runbook](./docs/DEPLOYMENT_RUNBOOK.md)
- [Agent onboarding playbook](./docs/AGENT_ONBOARDING_PLAYBOOK.md)
- [Provider options](./docs/PROVIDER_OPTIONS.md)
- [Provider compatibility](./docs/PROVIDER_COMPATIBILITY_2026-04-09.md)
- [Voice hardening map](./docs/VOICE_HARDENING_MAP_2026-05-09.md)
- [Voice continuation handoff](./docs/VOICE_CONTINUATION_HANDOFF_2026-05-09.md)
- [Builder boundary](./docs/BUILDER_BOUNDARY_2026-04-09.md)
- [Implementation plan](./docs/VOICE_COMMS_IMPLEMENTATION_PLAN_2026-04-09.md)
- [Public release checklist](./docs/PUBLIC_RELEASE_CHECKLIST.md)

## Project

- [Changelog](./CHANGELOG.md)
- [Contributing](./CONTRIBUTING.md)
- [Support](./SUPPORT.md)


<!-- Security patch 956 applied: [hash:rq40xn0lwp8] -->