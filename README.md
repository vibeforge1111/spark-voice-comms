# Spark Voice Comms

Drop-in voice communications hooks for Spark agents.

License: AGPL-3.0-only. See [LICENSE](./LICENSE).

This chip lets a Spark Builder runtime add voice without absorbing voice code into the main agent. Builder keeps the conversation, identity, approvals, and channel transport. This repo owns only the speech I/O hooks:

- `voice.status`
- `voice.plan`
- `voice.onboard`
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
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.status --home "<spark-home>"
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.onboard --home "<spark-home>"
```

If your Builder CLI version supports `--payload-json`, you can run a deterministic local transcribe smoke without a provider:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.transcribe --home "<spark-home>" --payload-json "{\"audio_base64\":\"ZmFrZS1hdWRpby1ieXRlcw==\",\"filename\":\"smoke.ogg\",\"mime_type\":\"audio/ogg\",\"fallback_mode\":\"deterministic\"}"
```

The same payloads are available as files under [`examples/`](./examples/):

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.onboard --home "<spark-home>" --payload-file examples/voice_onboard_local.json
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.transcribe --home "<spark-home>" --payload-file examples/voice_transcribe_fallback.json
```

## Local Provider Setup

Keep provider keys in your local Builder environment file or supported Spark secret layer. Do not commit `.env` files.

For STT:

```text
OPENAI_API_KEY=<your OpenAI API key>
VOICE_TRANSCRIBE_PROVIDER=openai
VOICE_TRANSCRIBE_SECRET_ENV_REF=OPENAI_API_KEY
VOICE_TRANSCRIBE_BASE_URL=https://api.openai.com/v1
```

Free/local STT:

```bash
python -m pip install -e ".[local-stt]"
```

That enables local faster-whisper fallback when it is installed and the host runtime allows local model execution.

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

Set `VOICE_TTS_KOKORO_MODEL_PATH` and `VOICE_TTS_KOKORO_VOICES_PATH` to local Kokoro model files, then call `voice.speak` with `tts.provider_id=kokoro`.

Local TTS is useful for zero-cost setup and desktop playback. Kokoro is the preferred private/free quality path when model assets are configured. Hosted TTS is still the simpler path for Telegram voice-note delivery.

## Runtime Boundary

Builder should:

- detect Telegram or other channel audio messages
- fetch channel media bytes
- pass bounded payloads into chip hooks
- keep personality, memory, approvals, and visible reply text

This chip should:

- check provider compatibility
- transcribe audio
- synthesize speech
- resolve voice profile and provider voice mapping
- keep fallback behavior testable

See [docs/BUILDER_BOUNDARY_2026-04-09.md](./docs/BUILDER_BOUNDARY_2026-04-09.md).

## Current Status

Implemented in this repo:

- `voice.status`
- `voice.plan`
- `voice.transcribe`
- `voice.speak`
- local deterministic fallback transcripts
- local faster-whisper fallback when installed
- Telegram-targeted Opus output selection for `voice.speak`

Activation status depends on the host Spark runtime. A Spark agent may have this chip installed but still report voice as unavailable until the operator approves the connector and provider setup is verified.

## Security

- Do not commit `.env` files, provider keys, recordings, transcripts, or generated audio.
- The chip reads provider secret values from local env files supplied by Builder; hook replies should not print secret values.
- Use fake placeholders in tests, not token-shaped examples.
- Review [SECURITY.md](./SECURITY.md) before making a fork public.

Important: before making an existing private repository public, scan the full git history too. If history contains private paths, token-shaped examples, or provider voice ids, publish from a fresh scrubbed repository or rewrite history before changing visibility.

## License

This repo is licensed under the GNU Affero General Public License v3.0 only. See [LICENSE](./LICENSE).

## Docs

- [Getting started with voice](./docs/GETTING_STARTED_WITH_VOICE.md)
- [Deployment runbook](./docs/DEPLOYMENT_RUNBOOK.md)
- [Agent onboarding playbook](./docs/AGENT_ONBOARDING_PLAYBOOK.md)
- [Provider options](./docs/PROVIDER_OPTIONS.md)
- [Provider compatibility](./docs/PROVIDER_COMPATIBILITY_2026-04-09.md)
- [Builder boundary](./docs/BUILDER_BOUNDARY_2026-04-09.md)
- [Implementation plan](./docs/VOICE_COMMS_IMPLEMENTATION_PLAN_2026-04-09.md)
- [Public release checklist](./docs/PUBLIC_RELEASE_CHECKLIST.md)

## Project

- [Changelog](./CHANGELOG.md)
- [Contributing](./CONTRIBUTING.md)
- [Support](./SUPPORT.md)
