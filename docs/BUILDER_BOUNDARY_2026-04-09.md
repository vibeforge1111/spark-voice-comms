# Voice Chip x Builder Boundary

License: AGPL-3.0-only.

This repo owns speech transport and rendering, not the live conversational personality.

## This Repo Owns

- `voice.status`
- `voice.plan`
- `voice.transcribe`
- `voice.speak`
- STT provider logic
- TTS provider logic
- voice profiles
- fallback and compatibility logic

## Builder Owns

`spark-intelligence-builder` owns the live agent personality that Telegram users actually experience:

- saved persona state
- style training and feedback
- presets
- score/examples/compare
- undo
- savepoints

## How The Runtime Works

### Voice in

1. Builder receives Telegram audio.
2. Builder fetches the media bytes.
3. Builder calls this repo via `voice.transcribe`.
4. The transcript goes back into the normal Builder conversation runtime.

### Voice out

1. Builder finalizes the text reply in the current Builder persona.
2. Builder checks the host runtime's voice approval and channel policy.
3. Builder calls this repo via `voice.speak` only when spoken delivery is allowed.
4. This repo returns synthesized audio.
5. Builder sends the audio back to Telegram.

So the voice chip preserves the Builder-owned personality by rendering it, not by authoring it.

This repo does not own Telegram tokens, provider credentials, user identity, memory, or capability activation.

## Current Rule

Keep the split as:

- personality chip = baseline persona source
- Builder = living personality runtime
- voice chip = speech I/O around Builder personality
