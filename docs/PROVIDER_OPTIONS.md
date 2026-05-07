# Provider Options

License: AGPL-3.0-only.

Use this page to help users choose a voice setup.

## Quick Recommendation

| User Goal | STT | TTS | Why |
| --- | --- | --- | --- |
| First local smoke | deterministic fallback or faster-whisper | pyttsx3 | no provider key, lowest friction |
| Private/offline testing | faster-whisper | pyttsx3 | local execution, no network calls |
| Production Telegram bot | OpenAI-compatible STT | ElevenLabs | simpler quality bar and Telegram-friendly audio output |
| Lowest operational complexity | OpenAI-compatible STT | ElevenLabs | hosted providers own model/runtime reliability |
| Existing Z.ai account | OpenAI-compatible or local STT | Z.ai GLM-TTS after adapter support lands | Z.ai is useful for GLM voice output, but not wired yet |
| Existing MiniMax account | OpenAI-compatible or local STT | MiniMax Speech after adapter support lands | MiniMax is useful for expressive voice, but not wired yet |

## Free / Local Options

### Local STT: faster-whisper

Install:

```bash
python -m pip install -e ".[local-stt]"
```

Useful when:

- privacy matters
- provider spend should be zero
- degraded mode should still be testable

Tradeoffs:

- model download and CPU/GPU performance vary by machine
- accuracy depends on chosen model size
- host runtime still needs to allow local model execution

### Local TTS: pyttsx3

Install:

```bash
python -m pip install -e ".[local-tts]"
```

Payload:

```json
{
  "text": "Local TTS smoke test.",
  "tts": {
    "provider_id": "pyttsx3",
    "voice_name": "optional local voice name",
    "rate": 175,
    "volume": 0.9
  }
}
```

Useful when:

- users want a no-key voice test
- desktop/local playback is enough
- quality is less important than getting started

Tradeoffs:

- voice quality depends on OS voices
- output is WAV, not Telegram Opus voice-note media
- channel adapters may need conversion before sending as Telegram voice notes

## Paid / Hosted Options

### STT: OpenAI-compatible transcriptions

The chip targets an OpenAI-compatible `/audio/transcriptions` endpoint for hosted STT.

```text
OPENAI_API_KEY=<your OpenAI API key>
VOICE_TRANSCRIBE_PROVIDER=openai
VOICE_TRANSCRIBE_SECRET_ENV_REF=OPENAI_API_KEY
VOICE_TRANSCRIBE_BASE_URL=https://api.openai.com/v1
```

### TTS: ElevenLabs

The chip targets ElevenLabs `/text-to-speech/{voice_id}` for hosted TTS.

```text
ELEVENLABS_API_KEY=<your ElevenLabs API key>
VOICE_TTS_ELEVENLABS_VOICE_ID=<your ElevenLabs voice id>
VOICE_TTS_ELEVENLABS_MODEL_ID=eleven_turbo_v2_5
```

Useful when:

- voice quality matters
- Telegram voice-note delivery should be easier
- provider latency/reliability is preferable to local model setup

Tradeoffs:

- provider spend
- provider account setup
- users must keep credentials out of Telegram chat and git

## Planned Provider Adapters

These providers should be configured with explicit adapters, not by pretending they are OpenAI-compatible transcription providers.

### Z.ai / GLM

Z.ai is the provider; GLM is the model family. The intended first voice path is GLM-TTS.

Planned env shape:

```text
VOICE_TTS_PROVIDER=zai
ZAI_API_KEY=<your Z.ai API key>
VOICE_TTS_ZAI_MODEL=glm-tts
VOICE_TTS_ZAI_VOICE=<your Z.ai voice id or name>
```

### MiniMax

MiniMax is a strong hosted TTS candidate for expressive Spark character voices.

Planned env shape:

```text
VOICE_TTS_PROVIDER=minimax
MINIMAX_API_KEY=<your MiniMax API key>
VOICE_TTS_MINIMAX_MODEL=speech-2.8-hd
VOICE_TTS_MINIMAX_VOICE_ID=<your MiniMax voice id>
```

Until those adapters land, use OpenAI-compatible or local STT plus ElevenLabs or pyttsx3 TTS.
