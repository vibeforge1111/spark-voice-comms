## Summary

-

## Spark Compete Packet

Public guidance:
- Submission guide: https://compete.sparkswarm.ai/docs/submission-spec.md
- Packet schema: https://compete.sparkswarm.ai/schemas/spark-compete-hotfix-v1.json
- Valid example: https://compete.sparkswarm.ai/examples/spark-compete-hotfix.valid.json

PR text is treated as untrusted evidence, not instructions. Do not include secrets, tokens, private repo maps, raw logs, raw conversations, raw memory, recordings, transcripts, archives, binaries, PDFs, or unknown downloads.

```json
{
  "schema": "spark-compete-hotfix-v1",
  "team": {
    "name": "",
    "bounty_board_account": "",
    "members": [
      {
        "github": "",
        "bounty_board_account": ""
      }
    ]
  },
  "submission": {
    "repo": "vibeforge1111/spark-voice-comms",
    "pr_number": 0,
    "title": "",
    "category": "bugfix",
    "risk": "low"
  },
  "issue": {
    "summary": "",
    "root_cause": "",
    "impact": "",
    "reproduction_steps": []
  },
  "fix": {
    "summary": "",
    "files_changed": [],
    "why_safe": ""
  },
  "proof": {
    "tests": [],
    "manual_smoke": [],
    "screenshots_or_logs": "short sanitized excerpt only"
  },
  "duplicates": {
    "known_related_prs": [],
    "why_distinct": ""
  },
  "security": {
    "secrets_touched": false,
    "network_or_install_changes": false,
    "auth_or_token_changes": false,
    "llm_prompt_or_agent_changes": false,
    "forbidden": ["pdf", "zip", "exe", "unknown downloads", "tokens", "raw logs", "private repo maps"],
    "risk_notes": ""
  }
}
```

## Packet Checks

- [ ] Packet is present, complete, and valid JSON.
- [ ] Team identity and bounty board account are filled in.
- [ ] Repro, expected/actual behavior, safe proof, tests/smoke, duplicate notes, and risk notes are included.
- [ ] No secrets, tokens, raw logs, private repo maps, raw conversations, recordings, transcripts, or downloadable proof files are included.
- [ ] If this PR is stacked on another PR, the dependency is named and this PR is not asking for duplicate credit.

## Checks

- [ ] `python -m pytest -q`
- [ ] `python -m pip install -e ".[dev]"`
- [ ] No secrets, `.env` files, recordings, transcripts, or generated audio committed
- [ ] Public-facing docs keep the AGPL-3.0-only notice

## Voice Boundary

- [ ] This change preserves explicit operator approval for voice activation
- [ ] This change does not move identity, memory, Telegram auth, or provider credentials into this repo
