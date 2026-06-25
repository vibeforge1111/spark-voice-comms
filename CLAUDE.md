# Spark Voice Comms Agent Ruleset

## Repo Role

`spark-voice-comms` owns Spark's speech I/O chip: voice onboarding, voice status, local/provider compatibility checks, speech-to-text, text-to-speech, voice profiles, and Telegram-friendly audio output helpers.

Canonical truth owned here:

- voice chip command surface: `voice.status`, `voice.plan`, `voice.onboard`, `voice.install`, `voice.transcribe`, `voice.speak`
- provider/profile metadata needed for voice setup and smoke checks
- local/free and hosted voice adapter behavior implemented in this chip
- voice artifact contracts that this repo explicitly emits

This repo does not own:

- Spark identity, memory, personality, or route confidence
- Telegram bot tokens, chat routing, or final-answer policy
- Builder AOC, authority verdicts, or durable memory decisions
- CLI installer registry pins or secret storage
- raw transcript/audio retention policy outside the chip boundary

## Start-of-Work Protocol

1. Run `git status --short --branch`.
2. Read this file plus `README.md` and any voice provider docs touched by the change.
3. Identify whether the behavior belongs in the voice chip or in Builder, Telegram, CLI, or Cockpit.
4. Define the smallest voice behavior and stop-ship gate.
5. Add or update focused tests/smokes before broad docs claims.
6. Keep provider keys and private audio/transcript data out of tests and fixtures.
7. Commit one logical checkpoint with verification notes.

## One Truth Rules

- Voice may report capability and provider/profile metadata, but Builder decides whether speech is allowed in context.
- Telegram may deliver voice, but this repo does not own Telegram routing or chat identity.
- CLI may install/configure the chip, but this repo owns the voice command behavior it exports.
- Do not duplicate Builder memory, route, AOC, or authority logic in voice code.
- Generated audio, transcripts, local smoke outputs, and provider probes are evidence, not durable truth.

## Privacy Red Lines

Do not export, commit, or pass into projections:

- provider API keys, env values, credentials, private keys
- raw chat ids, user ids, or non-redacted account identifiers
- raw transcript bodies unless the user explicitly requested a local artifact and the boundary is documented
- raw audio payloads unless the command is explicitly an audio artifact writer
- provider output bodies beyond required metadata
- memory bodies
- private `spark-intelligence-systems` strategy

Prefer metadata-only evidence: provider name, model/voice id when safe, capability status, file type, duration, trace/request refs, and blockers.

## Authority and Route Rules

- Voice activation is a capability gate, not permission for the agent to speak whenever it wants.
- Builder owns RouteConfidenceGateV1 and AOC route judgment; voice adapters may expose metadata but must not fork the gate.
- External provider use, microphone capture, Telegram voice delivery, memory writes from transcripts, and publication of audio artifacts require source-owned authority and user intent.
- If voice state is stale or missing, report the missing proof instead of claiming readiness.

## Anti-Spaghetti Rules

- Do not move conversation policy, memory policy, or Telegram reply composition into this repo.
- Do not add hidden network calls to status checks; provider checks should be explicit and bounded.
- Do not save raw transcripts/audio as default behavior.
- Do not silently fall back to hosted providers when local/private mode was requested.
- Do not add new provider abstractions until at least one concrete adapter and smoke path justify them.

## Verification Menu

- Focused tests for changed voice command or adapter behavior.
- Local smoke with deterministic fallback fixtures for degraded/offline paths.
- Provider smoke only when explicitly configured and safe.
- Build/typecheck commands used by this repo.
- Privacy scan for docs, fixtures, generated artifacts, and provider serializers.
- `git diff --check`.
- `git status --short --branch`.

<!-- SPARK FLEET STANDARD BLOCK v1 — canonical source: spark-compete/fleet/AGENT_GUIDE.md.
     This same block is mirrored into every repo's AGENTS.md and CLAUDE.md. Keep in sync. -->
## How agents work in this repo (Claude, Codex, Gemini — every LLM)

Many agents and sessions work these repos at the same time. There is a tiny **automatic**
workflow that keeps you from colliding. **There are no human-review steps — CI is the only
gate, and it is automatic.** This is coordination, not bureaucracy: claim, work, PR.

### Start of work — one command, then just work normally
```
python3 ~/spark-compete/scripts/fleet.py claim <this-repo-path> <area> <task>
```
You get your **own private worktree + branch + a lease** on `<area>`, so no other agent
edits the same files. It prints the folder to `cd` into. Work there and commit as usual —
a pre-commit hook **auto-checks and renews your lease**; you never manage it by hand.

- `fleet board` — see who's working on what, right now
- `fleet handoff <agent> --note "..."` — pass your work to another agent (with context)
- `fleet release --here` — done (frees the area + removes the worktree)

### Landing work — fully automatic, no human approval
1. Open a PR to the default branch.
2. **CI is the gate.** When it's green, the PR merges. No human reviews anything.
3. Never push directly to the protected branch; never commit from the shared checkout —
   always from your worktree.

### The rules (enforced by CI, not by people)
Full ruleset: **`spark-cli/docs/harness-discipline/`** — `01_RULESET.md` (7 Prime
Directives · Red Lines RL-01..21 · Rules R-01..28) and `07_FLEET_DISCIPLINE.md` (this
workflow). The day-to-day essentials:
- A real fix targets the **root cause**, not a symptom (R-05).
- No regex / keyword / canned answer **owns authority** — it is evidence only (RL-01).
- A failure **surfaces** with a clear reason; it never becomes a fake success (RL-08).
- One worktree per task; PRs only; nothing bypasses the CI gate (F-01 / F-09).

That's the whole contract. The system handles coordination and the gate for you —
automatically, with no human in the loop.
<!-- END SPARK FLEET STANDARD BLOCK v1 -->
