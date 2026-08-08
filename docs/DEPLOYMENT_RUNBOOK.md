# Deployment Runbook

License: MIT.

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
/voice provider
/voice install kokoro
/voice install faster-whisper
/voice install local
/voice onboard local
/voice onboard paid
```

Natural prompts should work too if the host Builder has the onboarding route:

```text
Can you help me set up voice?
Can I use free local TTS?
Can you help me set up voice using paid?
Guide me through ElevenLabs voice setup.
Find me a natural warm voice.
Use voice Elise.
Audition the voice.
Make it warmer and a little faster.
```

Provider changes, voice search, auditions, tuning, and rollback are owned by the host Builder route. The chip supplies the speech hooks and provider adapters; Builder owns conversation, memory, personality, scoped preferences, and Telegram composition.

## 4. Local/Free Smoke

For the easiest local path from Telegram, ask the agent:

```text
/voice install local
```

That installs the local listening package (`faster-whisper`) and the local neural speaking package (`kokoro-onnx` + `soundfile`) in the Python runtime used by Spark. If you only need one side:

```text
/voice install faster-whisper
/voice install kokoro
```

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

Local faster-whisper STT is preferred for transcription when installed, so Telegram voice notes do not require OpenAI transcription spend by default. Use the hosted STT settings below only when paid transcription is intentional. Do not paste real keys into Telegram chat.

```text
VOICE_OPENAI_API_KEY=<your OpenAI API key>
VOICE_TRANSCRIBE_PROVIDER=openai
VOICE_TRANSCRIBE_SECRET_ENV_REF=VOICE_OPENAI_API_KEY
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
VOICE_OPENAI_API_KEY=<your OpenAI API key>
VOICE_TTS_PROVIDER=openai-realtime
VOICE_TTS_OPENAI_REALTIME_SECRET_ENV_REF=VOICE_OPENAI_API_KEY
VOICE_TTS_OPENAI_REALTIME_MODEL_ID=gpt-realtime-2
VOICE_TTS_OPENAI_REALTIME_VOICE=coral
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
/voice provider
/voice onboard local
/voice ask Give me one warm QA-style sentence with the current voice.
/voice reply on
```

Expected behavior:

- `/voice` explains readiness or the missing provider step.
- `/voice provider` shows the selected provider and safe next choices without revealing keys or full hosted voice IDs.
- `/voice onboard local` gives a clear local/free setup path.
- `/voice onboard paid` gives a provider setup path.
- `/voice ask ...` should generate a Builder-authored answer first, then speak that answer.
- `/voice reply on` should make the next normal reply eligible for audio delivery when the host runtime and connector approval allow it.
- The visual dashboard, when available at `/voice-system`, should show masked provider/profile state and Telegram `sendVoice` proof without requiring `/voice dashboard` after every test.

## Rollback

```bash
python -m spark_intelligence.cli attachments deactivate-chip spark-voice-comms --home "<spark-home>"
```

Then ask the Telegram agent:

```text
/voice
```

It should report that the voice chip is not attached or not active.
