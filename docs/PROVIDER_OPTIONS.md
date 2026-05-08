# Provider Options

License: AGPL-3.0-only.

Use this page to help users choose a voice setup.

## Quick Recommendation

| User Goal | STT | TTS | Why |
| --- | --- | --- | --- |
| First local smoke | deterministic fallback or faster-whisper | pyttsx3 | no provider key, lowest friction |
| Private/offline testing | faster-whisper | Kokoro or pyttsx3 | local execution, no network calls |
| Best free local voice quality | faster-whisper | Kokoro | local neural TTS without a hosted provider key |
| Production Telegram bot | OpenAI-compatible STT | ElevenLabs | simpler quality bar and Telegram-friendly audio output |
| Lowest operational complexity | OpenAI-compatible STT | ElevenLabs | hosted providers own model/runtime reliability |
| Realtime voice agent feel | local or OpenAI-compatible STT | GPT Realtime 2 | expressive OpenAI speech model over a server-side Realtime socket |
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

Runtime selection:

- default `VOICE_TRANSCRIBE_PROVIDER=auto` uses local faster-whisper first when it is installed
- `VOICE_TRANSCRIBE_PROVIDER=local` requires local faster-whisper and will not call hosted STT
- `VOICE_TRANSCRIBE_PROVIDER=openai` deliberately uses hosted OpenAI-compatible transcription, with local fallback available if installed

Tradeoffs:

- model download and CPU/GPU performance vary by machine
- accuracy depends on chosen model size
- host runtime still needs to allow local model execution

### Local TTS: Kokoro

Kokoro is the preferred local quality path when users want private/free voice replies that sound better than operating-system voices. It runs locally through `kokoro-onnx` and requires local model assets.

Install:

```bash
python -m pip install -e ".[local-kokoro]"
```

Configure local paths in the Builder env file or secret/config layer:

```text
VOICE_TTS_PROVIDER=kokoro
VOICE_TTS_KOKORO_MODEL_PATH=C:\path\to\kokoro-v1.0.onnx
VOICE_TTS_KOKORO_VOICES_PATH=C:\path\to\voices-v1.0.bin
VOICE_TTS_KOKORO_VOICE=af_sarah
VOICE_TTS_KOKORO_SPEED=1.0
VOICE_TTS_KOKORO_LANG=en-us
```

Payload:

```json
{
  "text": "Kokoro local TTS smoke test.",
  "tts": {
    "provider_id": "kokoro"
  }
}
```

Useful when:

- users want a no-key voice path with stronger voice quality
- privacy and provider spend matter
- the host machine can run local ONNX inference

Tradeoffs:

- users must install optional packages and model files locally
- output is WAV, so Telegram voice-note delivery may still need channel-side conversion
- first-run performance depends on CPU/GPU and model asset placement

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

### TTS: OpenAI GPT Realtime 2

GPT Realtime 2 is a hosted OpenAI voice model for realtime speech interactions. In this chip, it is exposed as a server-side `voice.speak` provider that opens a Realtime WebSocket, asks for audio output, and returns WAV audio for the channel adapter to deliver or convert.

Install the optional WebSocket dependency:

```bash
python -m pip install -e ".[openai-realtime]"
```

Configure secrets locally, not in Telegram:

```text
OPENAI_API_KEY=<your OpenAI API key>
VOICE_TTS_PROVIDER=openai-realtime
VOICE_TTS_OPENAI_REALTIME_MODEL_ID=gpt-realtime-2
VOICE_TTS_OPENAI_REALTIME_VOICE=coral
VOICE_TTS_OPENAI_REALTIME_REASONING_EFFORT=low
```

Payload:

```json
{
  "text": "Say one warm sentence with GPT Realtime 2.",
  "tts": {
    "provider_id": "openai-realtime"
  }
}
```

Useful when:

- users already use OpenAI and want a higher-end voice-agent path
- the agent's spoken style matters as much as raw TTS quality
- server-side Realtime access is acceptable for the deployment

Tradeoffs:

- provider spend
- requires the optional `websocket-client` package
- output is WAV, so Telegram voice-note delivery may still need channel-side conversion
- this is a realtime model path, not a drop-in OpenAI-compatible `/audio/speech` clone

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

Until those adapters land, use OpenAI-compatible or local STT plus Kokoro, ElevenLabs, or pyttsx3 TTS.
