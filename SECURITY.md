# Security Policy

## Supported Versions

This repo is pre-1.0. Security fixes target the current `main` branch unless a release branch is published later.

License: AGPL-3.0-only. Security reports and fixes should preserve the repository license.

## Reporting A Vulnerability

Please report suspected vulnerabilities privately to the repository owner before opening a public issue.

Include:

- the affected hook or file
- the provider or channel involved, if any
- reproduction steps using fake credentials
- whether any real secret, recording, transcript, or user data may have been exposed

Do not include real API keys, provider secrets, Telegram tokens, private recordings, or private transcripts in reports.

## Secret Handling Rules

- Provider credentials belong in local environment files or the host Spark secret layer.
- `.env` files must stay untracked.
- Tests must use placeholders that do not resemble real provider tokens.
- Hook outputs and error messages should identify missing secret references by environment variable name only, never by secret value.
- Public docs should show variable names and placeholder values only.

## Public Release Checklist

Before making a fork public:

- run the test suite
- scan the working tree and git history for token-shaped values
- remove local absolute paths
- remove recordings, generated audio, transcripts, and private runtime state
- publish from a fresh scrubbed repository or rewrite history if old commits contain private paths, token-shaped examples, or provider voice ids
- confirm the AGPL-3.0-only license file and package metadata are present
- enable GitHub secret scanning and push protection for the public repository
