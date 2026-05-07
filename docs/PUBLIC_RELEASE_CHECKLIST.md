# Public Release Checklist

License: AGPL-3.0-only.

Use this before making the repo public.

## Required

- [ ] `python -m pytest -q` passes.
- [ ] No `.env` files are tracked.
- [ ] No recordings, generated audio, transcripts, or private runtime state are tracked.
- [ ] No local absolute paths remain in public docs.
- [ ] No token-shaped fake keys remain in tests or docs.
- [ ] Git history has been scanned for real provider keys, token-shaped examples, local absolute paths, and provider voice ids.
- [ ] If history scan finds anything sensitive or private, publish from a fresh scrubbed repo or rewrite history before making the repo public.
- [ ] The public README says voice activation depends on the host Spark runtime.
- [x] The repo has an intentional license decision: AGPL-3.0-only.
- [ ] GitHub Actions test workflow is green on the first public branch.
- [ ] GitHub secret scanning and push protection are enabled once the repo is public.

## Recommended

- [ ] Add one short demo payload for `voice.transcribe`.
- [ ] Add one short demo payload for `voice.speak` that uses fake credentials and mocked provider calls.
- [ ] Add a release tag only after the host Builder contract is stable.
- [ ] Keep Telegram, provider, and human identity tokens outside this repo.

## Release Positioning

Recommended public description:

> Drop-in voice communications hooks for Spark agents: STT, TTS, voice profiles, provider checks, and Telegram-friendly voice-note output behind explicit operator activation.

Avoid claiming:

- that any specific private Spark bot has live voice enabled
- that installing the chip grants microphone, Telegram, or provider access
- that the chip owns identity, memory, or approval state
