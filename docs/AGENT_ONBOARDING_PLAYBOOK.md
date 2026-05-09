# Agent Onboarding Playbook

License: AGPL-3.0-only.

This playbook helps a Spark Telegram agent guide users through voice setup without exposing secrets or pretending voice is active before it is approved.

## Agent Goal

When a user asks for voice, the agent should help them choose one of two paths:

- local/free: private, low-cost, good for first smoke tests; Kokoro is the preferred quality path when the machine can run it
- paid/provider: higher quality and better Telegram delivery, but requires provider credentials

The agent should keep setup conversational:

1. start from what the user wants, not from an inventory of providers
2. recommend the best path for this Spark when enough context is available
3. explain only the missing step in plain language
4. keep provider keys, env names, and Python paths out of Telegram unless the user is explicitly doing operator setup
5. confirm with `voice.status`
6. ask for one short voice reply before telling them voice is ready

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
- `Find me a natural geeky QA tester voice`
- `Use voice Elise`
- `Make it warmer and more geeky`
- `Go back to the previous voice`

## Local/Free Path

Recommend this when the user wants privacy, zero provider spend, or a first smoke test.

```bash
python -m pip install -e ".[local]"
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.onboard --home "<spark-home>" --payload-json "{\"route\":\"local\"}"
```

If the user asks from Telegram and is an approved operator, route `/voice install kokoro` through `voice.install` before asking them to add model paths. Do not install hosted-provider SDKs or collect provider keys in Telegram.

For provider keys, point users to their local Builder env file or Spark's secret layer. `.env.example` shows the safe shape for ElevenLabs, GPT Realtime 2, Kokoro, pyttsx3, and planned MiniMax/Z.ai slots. Codex CLI can run agent missions, but it is not a native STT/TTS provider for this chip.

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

For a more voice-agent-like hosted path, use GPT Realtime 2:

```text
VOICE_TTS_PROVIDER=openai-realtime
OPENAI_API_KEY=<your OpenAI API key>
VOICE_TTS_OPENAI_REALTIME_MODEL_ID=gpt-realtime-2
VOICE_TTS_OPENAI_REALTIME_VOICE=coral
```

Then:

```bash
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.onboard --home "<spark-home>" --payload-json "{\"route\":\"paid\"}"
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.status --home "<spark-home>"
```

## Agent Reply Template

Use concise, human replies in Telegram. The reply should feel like Spark is guiding the operator, not printing a diagnostic report.

```text
I can help with voice.

For this Spark, I would start local if you want privacy and no provider spend. Kokoro is the voice I would use for that path when the local model files are connected.

If you want the most natural hosted voice, I would use verified transcription plus a paid TTS provider like ElevenLabs.

Tell me local or paid, and I will walk you through only the part that is still missing.
```

When Spark already knows the user's preference or runtime provider, personalize the recommendation:

```text
Since this Spark is already leaning local/private, I would finish Kokoro first. That keeps voice replies on this machine and avoids putting provider keys into Telegram.
```

For voice self-awareness questions, keep the current map simple:

```text
Builder handles my thinking, memory, and character. The voice chip handles listening and speaking. Telegram is where the voice messages come and go. My current TTS provider is a DM preference, and I only call voice ready after status and delivery have both been tested.
```

Useful Telegram checks:

- `/voice map`
- `/voice provider`
- `/voice dashboard`
- `/probe voice`
- `find me a natural geeky QA tester voice`
- `audition the voice`
- `make it warmer`
- `go back to the previous voice`

Avoid Telegram-facing replies like:

```text
Status: package install completed.
Python: C:\...
VOICE_TTS_KOKORO_MODEL_PATH=<path>
```

Keep those details in local operator docs, structured hook results, or redacted diagnostics.

## Guardrails

- Do not ask users to paste real API keys into Telegram chat.
- Do not claim voice is active until `voice.status` and the host runtime capability state agree.
- Do not store recordings, generated audio, transcripts, or provider credentials in this repo.
- If Telegram voice delivery fails, report the channel-format issue clearly instead of retrying blindly.
- If a provider rejects local credentials, explain the local config step in plain language. Do not echo raw provider JSON such as `invalid_api_key` into Telegram.
- If a voice tuning goes wrong, offer scoped rollback: `go back to the previous voice`.
