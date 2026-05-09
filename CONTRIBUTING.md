# Contributing

License: MIT.

Thanks for helping improve Spark Voice Comms.

## Development Setup

```bash
git clone <repo-url>
cd spark-voice-comms
python -m pip install -e ".[dev]"
python -m pytest -q
```

Optional local voice dependencies:

```bash
python -m pip install -e ".[local]"
```

## Contribution Rules

- Keep provider credentials, Telegram tokens, recordings, transcripts, and generated audio out of git.
- Use fake placeholders in tests. Do not use token-shaped examples.
- Keep voice activation explicit. Installing a chip must not imply microphone, Telegram, or provider authority.
- Preserve the Builder boundary: Builder owns identity, approvals, memory, and channel transport; this repo owns speech I/O hooks.
- Add tests for hook behavior changes.

## Pull Request Checklist

- [ ] `python -m pytest -q` passes.
- [ ] `python -m pip install -e ".[dev]"` works.
- [ ] No `.env`, audio, transcript, recording, or generated voice artifact is committed.
- [ ] Docs mention MIT when adding a new public-facing document.
- [ ] New provider behavior has a safe failure mode and does not print secret values.

## Release Notes

For user-visible changes, update [CHANGELOG.md](./CHANGELOG.md).
