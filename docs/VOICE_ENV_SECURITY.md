# Voice Environment Security

License: MIT.

Use this page when helping users configure voice provider credentials.

## Recommended Storage

Use one of these secure local paths:

1. Builder's local env file for the active Spark home.
2. Spark's supported secret layer when the runtime exposes one.
3. A deployment secret manager in hosted environments.

Do not ask users to paste provider keys into Telegram, chat logs, issue trackers, screenshots, or public docs.

## Local Env Pattern

Start from `.env.example`, then copy only the keys the user needs into the local Builder env file.

For ElevenLabs:

```text
VOICE_TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=
VOICE_TTS_ELEVENLABS_VOICE_ID=
VOICE_TTS_ELEVENLABS_MODEL_ID=eleven_turbo_v2_5
```

For OpenAI GPT Realtime 2:

```text
VOICE_TTS_PROVIDER=openai-realtime
OPENAI_API_KEY=
VOICE_TTS_OPENAI_REALTIME_SECRET_ENV_REF=OPENAI_API_KEY
VOICE_TTS_OPENAI_REALTIME_MODEL_ID=gpt-realtime-2
VOICE_TTS_OPENAI_REALTIME_VOICE=coral
```

For local/private voice:

```text
VOICE_TTS_PROVIDER=kokoro
VOICE_TTS_KOKORO_MODEL_PATH=
VOICE_TTS_KOKORO_VOICES_PATH=
```

MiniMax and Z.ai slots may be present in env templates, but they should remain planned-provider slots until dedicated adapters and smoke tests land.

## Agent Guidance

When a user asks for voice setup, Spark should:

- ask whether they want local/private, hosted quality, or the fastest working path
- recommend Kokoro when privacy and no spend matter
- recommend GPT Realtime 2 when they already use OpenAI and want a voice-agent feel
- recommend ElevenLabs when they want a simpler hosted TTS path
- treat MiniMax and Z.ai as explicit future adapters, not generic OpenAI-compatible guesses
- explain that Codex CLI can run missions and coding agents, but is not a voice STT/TTS provider for this chip
- keep all secret handling outside Telegram
- explain provider failures in local-config language, not raw provider JSON
- recommend scoped rollback when a tuning change feels wrong: `go back to the previous voice`

## Public Repo Hygiene

The repo should include `.env.example` but never a real `.env` file.

Before release, run a secret scan over docs, source, tests, logs, and generated configs. The scan should look for provider key shapes, local absolute paths, Telegram ids, private usernames, and voice ids copied from a real account.

The visual dashboard must follow the same rule. It can show provider labels, masked voice IDs, readiness, and Telegram delivery proof, but it must not include provider keys, Telegram tokens, raw env values, local private paths, recordings, transcripts, or unmasked hosted voice IDs.
