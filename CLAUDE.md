# Claude Code entry point

The project's rules live in one tool-neutral file so they cannot drift into two
versions. Read it:

@AGENTS.md

Everything in that file applies here. What follows is only the part specific to
Claude Code.

## What this repo adds for Claude Code

| File | What it does |
|---|---|
| `.claude/settings.json` | Pre-approves this project's scripts so a session isn't interrupted, and **denies `WebFetch`, `WebSearch`, `curl`, and `wget`** |
| `.claude/skills/report/` | `/report` — start a reporting session, following the conductor exactly |
| `.claude/skills/checkup/` | `/checkup` — run the health check and give a verdict |

Those files are not committed by the remote tooling and are created locally —
see `BUILD-GUIDE.md` §3.5. If they are missing, everything still works; you
just get permission prompts and no slash commands.

## The one real difference

The deny list makes the **never-fetch rule platform-enforced here**, not merely
requested. On other assistants that rule is a prompt-level instruction and the
deterministic scripts are the backstop.

This is a stronger guarantee, not a different one. Do not write anything that
depends on it — the project must behave identically for someone running Codex
or Cursor, and `tests/run_tests.py` is what proves it does.

<!-- HANDOFF-PROTOCOL:BEGIN -->
## Session handoff — read this first

This project is worked on by both Claude and Codex, which cannot see each
other's conversations. **`HANDOFF.md` in this directory is the shared state.**

- **At the start of a session:** read `HANDOFF.md`. Take its `Last updated`
  timestamp as a watermark and check what changed since — `git log --since=`,
  `git status --short`, and Codex session files under `~/.codex/sessions`
  newer than that watermark. Record anything you find that is not already in
  the log, then begin.
- **While working:** append a log entry after each meaningful unit of work, not
  at the end of the session. A session that runs out of context never reaches
  the end.
- **Overwrite** the `Current State` block. **Append** to the `Log`, and trim it
  to roughly 15 entries.
- Summarise decisions and the reasoning behind them. Never paste transcripts.
- Keep entries at decision level — no case detail, no personal data.

Full rules: `C:\Users\darin\src\HANDOFF-PROTOCOL.md`
Pre-restructure path translation: `C:\Users\darin\src\path-map.json`
<!-- HANDOFF-PROTOCOL:END -->
