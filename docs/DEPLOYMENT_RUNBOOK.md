# Deployment Runbook

License: AGPL-3.0-only.

This runbook is for Spark operators bringing `spark-voice-comms` to a Telegram-facing Spark agent.

## 1. Install

```bash
git clone <repo-url>
cd spark-voice-comms
python -m pip install -e ".[dev]"
python -m pytest -q
```

For free/local voice testing:

```bash
python -m pip install -e ".[local]"
```

For hosted provider voice, keep using the base install and configure provider secrets in the host Spark environment.

## 2. Attach To Builder

```bash
python -m spark_intelligence.cli attachments add-root chips "<parent-dir-containing-spark-voice-comms>" --home "<spark-home>"
python -m spark_intelligence.cli attachments activate-chip spark-voice-comms --home "<spark-home>"
python -m spark_intelligence.cli attachments list --kind chip --home "<spark-home>"
```

## 3. Ask The Agent To Guide Setup

From Telegram, ask:

```text
/voice onboard
/voice install kokoro
/voice onboard local
/voice onboard paid
```

Natural prompts should work too if the host Builder has the onboarding route:

```text
Can you help me set up voice?
Can I use free local TTS?
Can you help me set up voice using paid?
```

## 4. Local/Free Smoke

Run the onboarding hook:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.onboard --home "<spark-home>" --payload-file examples/voice_onboard_local.json
```

Run deterministic STT fallback:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.transcribe --home "<spark-home>" --payload-file examples/voice_transcribe_fallback.json
```

Run local TTS if `pyttsx3` is installed:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.speak --home "<spark-home>" --payload-file examples/voice_speak_local.json
```

Run Kokoro local neural TTS after `VOICE_TTS_KOKORO_MODEL_PATH` and `VOICE_TTS_KOKORO_VOICES_PATH` are configured:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.speak --home "<spark-home>" --payload-file examples/voice_speak_kokoro.json
```

## 5. Paid Provider Setup

Add this to the host Spark environment or supported secret layer. Do not paste real keys into Telegram chat.

```text
OPENAI_API_KEY=<your OpenAI API key>
VOICE_TRANSCRIBE_PROVIDER=openai
VOICE_TRANSCRIBE_SECRET_ENV_REF=OPENAI_API_KEY
VOICE_TRANSCRIBE_BASE_URL=https://api.openai.com/v1

ELEVENLABS_API_KEY=<your ElevenLabs API key>
VOICE_TTS_ELEVENLABS_VOICE_ID=<your ElevenLabs voice id>
VOICE_TTS_ELEVENLABS_MODEL_ID=eleven_turbo_v2_5
```

For OpenAI GPT Realtime 2 voice, install the optional dependency and use the OpenAI Realtime provider instead of ElevenLabs:

```bash
python -m pip install -e ".[openai-realtime]"
```

```text
OPENAI_API_KEY=<your OpenAI API key>
VOICE_TTS_PROVIDER=openai-realtime
VOICE_TTS_OPENAI_REALTIME_MODEL_ID=gpt-realtime-2
VOICE_TTS_OPENAI_REALTIME_VOICE=sage
```

Then run:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.onboard --home "<spark-home>" --payload-file examples/voice_onboard_paid.json
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.status --home "<spark-home>"
```

## 6. Telegram Acceptance Test

In the Spark Telegram DM:

```text
/voice
/voice plan
/voice onboard local
/voice speak Voice setup smoke test.
```

Expected behavior:

- `/voice` explains readiness or the missing provider step.
- `/voice onboard local` gives a clear local/free setup path.
- `/voice onboard paid` gives a provider setup path.
- `/voice speak ...` should only deliver audio when the host runtime and connector approval allow it.

## Rollback

```bash
python -m spark_intelligence.cli attachments deactivate-chip spark-voice-comms --home "<spark-home>"
```

Then ask the Telegram agent:

```text
/voice
```

It should report that the voice chip is not attached or not active.
