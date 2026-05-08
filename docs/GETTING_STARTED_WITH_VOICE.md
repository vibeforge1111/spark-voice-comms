# Getting Started With Voice

License: AGPL-3.0-only.

This guide is for Spark operators who want to bring voice to their own Spark agents without moving voice logic into Builder.

## 1. Install The Chip

```bash
git clone <repo-url>
cd spark-voice-comms
python -m pip install -e ".[dev]"
python -m pytest -q
```

## 2. Attach It To Spark Builder

Point Builder at the parent directory that contains this repo, then activate the chip.

```bash
python -m spark_intelligence.cli attachments add-root chips "<chip-parent-dir>" --home "<spark-home>"
python -m spark_intelligence.cli attachments list --kind chip --home "<spark-home>"
python -m spark_intelligence.cli attachments activate-chip spark-voice-comms --home "<spark-home>"
```

Run the status hook:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.status --home "<spark-home>"
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.onboard --home "<spark-home>"
```

If `voice.status` is not ready, it should explain which provider or secret reference is missing.
If `voice.onboard` is available to your Spark Telegram agent, users can ask setup questions there too. Good first prompts are:

- `voice onboard local`
- `voice install kokoro`
- `voice onboard paid`
- `voice status`
- `voice plan`

Natural-language prompts should work too:

- `Can you help me set up voice locally for Spark?`
- `I want private local voice replies.`
- `I want the highest-quality paid voice for my Spark agent.`

Spark should answer these like an onboarding guide, not like a diagnostic dump. Keep env names, Python paths, and provider secrets out of Telegram unless the operator explicitly asks for local config details.

## 3. Configure Speech-To-Text

Add provider settings to the local Builder environment file or secret layer. Do not commit this file.

```text
OPENAI_API_KEY=<your OpenAI API key>
VOICE_TRANSCRIBE_PROVIDER=openai
VOICE_TRANSCRIBE_SECRET_ENV_REF=OPENAI_API_KEY
VOICE_TRANSCRIBE_BASE_URL=https://api.openai.com/v1
```

Supported STT path today:

- OpenAI-compatible `/audio/transcriptions`
- env-backed API key transport
- deterministic fallback mode for tests
- optional local faster-whisper fallback when installed

For a free local STT path:

```bash
python -m pip install -e ".[local-stt]"
```

Local STT is best for private/offline testing and cost-sensitive setups. Hosted STT is usually simpler for production Telegram bots.

## 4. Configure Text-To-Speech

Add a local ElevenLabs key and voice id:

```text
ELEVENLABS_API_KEY=<your ElevenLabs API key>
VOICE_TTS_ELEVENLABS_VOICE_ID=<your ElevenLabs voice id>
VOICE_TTS_ELEVENLABS_MODEL_ID=eleven_turbo_v2_5
```

The public voice profile intentionally leaves `primary_voice_id` blank. That keeps this repo reusable and prevents publishing a private operator's chosen voice id.

For a free local TTS path:

```bash
python -m pip install -e ".[local-tts]"
```

Then call `voice.speak` with `tts.provider_id=pyttsx3`. Local TTS uses the operating system's installed voices and does not require a provider key.

For a higher-quality free local TTS path, use Kokoro:

```bash
python -m pip install -e ".[local-kokoro]"
```

If the Telegram runtime exposes `voice.install`, an admin can also ask Spark:

```text
/voice install kokoro
```

The Telegram response should simply say whether Kokoro is installed and what human step remains. The structured hook result can still carry the Python path, pip tail, and readiness fields for diagnostics.

Download the Kokoro ONNX model and voices file locally, then point Spark at those files through the Builder env file or secret/config layer:

```text
VOICE_TTS_PROVIDER=kokoro
VOICE_TTS_KOKORO_MODEL_PATH=C:\path\to\kokoro-v1.0.onnx
VOICE_TTS_KOKORO_VOICES_PATH=C:\path\to\voices-v1.0.bin
VOICE_TTS_KOKORO_VOICE=af_sarah
VOICE_TTS_KOKORO_SPEED=1.0
VOICE_TTS_KOKORO_LANG=en-us
```

Then call `voice.speak` with `tts.provider_id=kokoro`. Kokoro keeps TTS local and does not require a provider key.

For OpenAI GPT Realtime 2 hosted voice:

```bash
python -m pip install -e ".[openai-realtime]"
```

```text
OPENAI_API_KEY=<your OpenAI API key>
VOICE_TTS_PROVIDER=openai-realtime
VOICE_TTS_OPENAI_REALTIME_MODEL_ID=gpt-realtime-2
VOICE_TTS_OPENAI_REALTIME_VOICE=coral
VOICE_TTS_OPENAI_REALTIME_REASONING_EFFORT=low
```

Spark should present this as a premium hosted voice-agent path. Do not ask users to paste the key into Telegram; guide them to the local Builder env file or secret layer.

Use `.env.example` as the public template and keep real values in Builder's local env file or Spark's secret layer. The secure storage rules are in [VOICE_ENV_SECURITY.md](./VOICE_ENV_SECURITY.md).

## 5. Run A Safe Local Smoke

You can test transcription flow without a real provider by using deterministic fallback mode:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.transcribe --home "<spark-home>" --payload-json "{\"audio_base64\":\"ZmFrZS1hdWRpby1ieXRlcw==\",\"filename\":\"smoke.ogg\",\"mime_type\":\"audio/ogg\",\"fallback_mode\":\"deterministic\"}"
```

Expected shape:

- `returncode` is `0`
- `result.mode` is `deterministic_fallback`
- `result.transcript_text` is bounded and clearly marked as fallback text

## 6. Wire A Channel

For Telegram or another channel, Builder should:

1. receive the audio message
2. fetch media bytes using the channel's own auth
3. call `voice.transcribe`
4. route the transcript through the normal Spark conversation runtime
5. call `voice.speak` only when voice replies are approved
6. deliver the returned audio with the channel adapter

This chip does not own Telegram tokens, user identity, memory, or approval state.

## 7. Activation Checklist

Before enabling voice for real users:

- `voice.status` reports ready for the intended provider
- a real STT request succeeds
- a real TTS request succeeds
- provider failures return bounded errors
- voice reply mode is explicit and reversible
- no provider key, recording, transcript, or generated audio is committed
- the operator has approved the connector boundary

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `voice.status` says no env file was provided | Builder did not pass its local env path | Configure Builder's supported provider secret layer |
| `voice.transcribe` says provider compatibility is unverified | Active provider is not OpenAI-compatible | Use OpenAI STT or configure an OpenAI-compatible endpoint |
| `voice.speak` asks for a voice id | No `tts.voice_id` or `VOICE_TTS_ELEVENLABS_VOICE_ID` was supplied | Add a local ElevenLabs voice id |
| Local TTS says `pyttsx3` is missing | The optional local TTS package is not installed | Run `python -m pip install -e ".[local-tts]"` |
| Kokoro TTS asks for model assets | The optional package is installed but model paths are missing | Set `VOICE_TTS_KOKORO_MODEL_PATH` and `VOICE_TTS_KOKORO_VOICES_PATH` locally |
| Telegram receives audio that does not play as a voice note | Wrong output format for Telegram | Use `surface=telegram` so the hook selects Opus output |
