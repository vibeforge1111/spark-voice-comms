# Support

License: AGPL-3.0-only.

## Getting Help

Start with:

- [Getting started with voice](./docs/GETTING_STARTED_WITH_VOICE.md)
- [Deployment runbook](./docs/DEPLOYMENT_RUNBOOK.md)
- [Provider options](./docs/PROVIDER_OPTIONS.md)
- [Agent onboarding playbook](./docs/AGENT_ONBOARDING_PLAYBOOK.md)

## Safe Support Requests

When asking for help, include:

- hook name, such as `voice.status` or `voice.speak`
- command output with secrets redacted
- provider type, such as local/free or paid/provider
- operating system and Python version

Do not include:

- API keys
- Telegram bot tokens
- private recordings
- transcripts containing private user data
- generated audio containing private content

## Fast Checks

```bash
python -m pytest -q
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.onboard --home "<spark-home>"
python -m spark_intelligence.cli attachments run-hook spark-voice-comms voice.status --home "<spark-home>"
```
