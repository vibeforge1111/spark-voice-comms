# Agent Onboarding Playbook

License: AGPL-3.0-only.

This playbook helps a Spark Telegram agent guide users through voice setup without exposing secrets or pretending voice is active before it is approved.

## Agent Goal

When a user asks for voice, the agent should help them choose one of two paths:

- local/free: private, low-cost, good for first smoke tests; Kokoro is the preferred quality path when the machine can run it
- paid/provider: higher quality and better Telegram delivery, but requires provider credentials

The agent should keep setup conversational:

1. explain the two paths
2. ask which path they want
3. run or summarize `voice.onboard`
4. guide them through only the missing step
5. confirm with `voice.status`
6. run one safe smoke before telling them voice is ready

## Suggested Telegram Prompts

Users can ask:

- `Can you help me set up voice?`
- `Install Kokoro voice locally`
- `/voice install kokoro`
- `voice onboard local`
- `voice onboard paid`
- `Can I use free local TTS?`
- `What paid voice provider should I use?`
- `Is voice ready right now?`

## Local/Free Path

Recommend this when the user wants privacy, zero provider spend, or a first smoke test.

```bash
python -m pip install -e ".[local]"
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.onboard --home "<spark-home>" --payload-json "{\"route\":\"local\"}"
```

If the user asks from Telegram and is an approved operator, route `/voice install kokoro` through `voice.install` before asking them to add model paths. Do not install hosted-provider SDKs or collect provider keys in Telegram.

What this path means:

- STT can use local faster-whisper when installed.
- TTS can use Kokoro for better local neural speech, or `pyttsx3` for basic system voices.
- Telegram voice-note delivery may still need host-side format conversion if the channel requires Opus voice notes.
- Quality depends heavily on the machine and installed voices.

Safe smoke:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.speak --home "<spark-home>" --payload-json "{\"text\":\"Voice setup smoke test.\",\"tts\":{\"provider_id\":\"pyttsx3\"}}"
```

Kokoro smoke after model paths are configured:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.speak --home "<spark-home>" --payload-json "{\"text\":\"Kokoro voice setup smoke test.\",\"tts\":{\"provider_id\":\"kokoro\"}}"
```

## Paid Provider Path

Recommend this when the user wants better quality and simpler production behavior.

```text
OPENAI_API_KEY=<your OpenAI API key>
VOICE_TRANSCRIBE_PROVIDER=openai
VOICE_TRANSCRIBE_SECRET_ENV_REF=OPENAI_API_KEY
VOICE_TRANSCRIBE_BASE_URL=https://api.openai.com/v1

ELEVENLABS_API_KEY=<your ElevenLabs API key>
VOICE_TTS_ELEVENLABS_VOICE_ID=<your ElevenLabs voice id>
VOICE_TTS_ELEVENLABS_MODEL_ID=eleven_turbo_v2_5
```

Then:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.onboard --home "<spark-home>" --payload-json "{\"route\":\"paid\"}"
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.status --home "<spark-home>"
```

## Agent Reply Template

Use concise replies in Telegram:

```text
Voice setup has two good paths:
- Local/free: private and no provider spend, using faster-whisper + Kokoro when available, or pyttsx3 for a basic smoke.
- Paid/provider: better quality, using OpenAI-compatible STT + ElevenLabs TTS.

Tell me `local` or `paid`, and I will walk you through only the missing pieces.
```

## Guardrails

- Do not ask users to paste real API keys into Telegram chat.
- Do not claim voice is active until `voice.status` and the host runtime capability state agree.
- Do not store recordings, generated audio, transcripts, or provider credentials in this repo.
- If Telegram voice delivery fails, report the channel-format issue clearly instead of retrying blindly.
