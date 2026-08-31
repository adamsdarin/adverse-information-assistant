# HANDOFF — adverse-information-assistant

Last updated: 2026-08-31T20:26:37Z by Claude

## Current State
Active project, and the only adverse-information-assistant that exists. Git repo, no remote. Incident development now requires factual, profile-specific coverage rather than accepting references to a transcript as evidence. Completed narratives are deterministically required to use the reporting individual's first-person voice. Synthetic reports now consolidate initial and developed facts into one final narrative per independent incident; initial input and all interview questions/answers remain in the transcript, and each case also ships a `complete-record.md` containing the full audit trail plus final report. The 20-case suite was regenerated and copied to `C:\Users\darin\Documents\Test Scenario`. The separate real reporting session remains paused at intake awaiting a privacy-tier choice; no case details have been collected.

Commit `8eb10c7` on 2026-08-31 captured 15 days of previously uncommitted work — 130 files across corpus checklists and forms, `adverse_app`, agent definitions, scripts, tests and docs. Before that the last commit was `ba8efee` (Aug 16). The working tree contains the uncommitted incident-depth and synthetic-suite changes from this session.

`.gitignore` excludes `output/`, `sessions/`, `*.draft.md` and `*.session.json` — user-generated content that contains personal information. Nothing personal is in history. Keep it that way.

A folder at `Documents\AI Agent Building\adverse-information-assistant` is NOT this project — it is a clone of github.com/penpot/penpot that landed in an empty folder on Aug 24. Ignore it.

## Next
1. Push to a private GitHub remote. No off-machine copy exists.
2. Compare `agents/conductor.md` here against `src\adverse-action-workflow` — the two projects share filenames and may share lineage.

## Open Questions
None.

## Log
2026-08-31T20:26:37Z Claude - Imported this session's Codex work: committed the incident-depth, first-person-voice and synthetic-suite changes (6 files, +595/-43) that were uncommitted and had no off-machine copy. Cleared a stale .git/index.lock that would have blocked the next commit. Note: synthetic outputs are being written to Documents\Test Scenario, which is outside src and outside the DCSA Library and is not backed up.
2026-08-31 20:05 Codex - Removed the synthetic report's initial-versus-developed narrative split. Each independent incident now renders one consolidated final narrative; every case separately includes the initial statement, complete Q&A transcript, final report, and a combined complete record. Full suite: 463 passed; all 20 outputs verified and were replaced in `Documents\Test Scenario`.
2026-08-31 19:53 Codex - Enforced first-person report voice. The narrative prompt explicitly prohibits analyst-style substitutes for the narrator, session validation rejects completed narratives without first-person language, and deterministic report context now uses `I`/`my` instead of second- or third-person framing. Full suite: 463 passed; all 20 first-person reports verified and replaced in `Documents\Test Scenario`.
2026-08-31 19:47 Codex - Reran the corrected 20-case synthetic suite on request. All 20 sessions validated, all 20 reports passed deterministic verification, and the transcripts, sessions, reports, hashes, index, and ZIP in `Documents\Test Scenario` were replaced with the new run.
2026-08-31 19:32 Codex - Fixed shallow incident development in both the workflow and synthetic harness. Factual coverage is now required for every applicable profile, metadata pointers are rejected as chronology evidence, all 20 scenarios have detailed interviews and narratives, and an end-to-end regression enforces the depth floor. Full suite: 462 passed; all regenerated reports verified and were copied to `Documents\Test Scenario`.
2026-08-31 19:13 Codex - Regenerated 20 fictitious workflow scenarios. All 20 session files passed validation, all 20 reports passed deterministic verification, and complete transcripts, sessions, reports, hashes, index, and ZIP were copied to `Documents\Test Scenario`.
2026-08-31 17:00 Codex - Began a reporting session. Corpus structure passed but its four reporting tables remain unverified; the Complete DCSA Library was found and the capability canary passed. No case details have been collected.
2026-08-31T16:47:01Z Claude — Committed 15 days of uncommitted work as a safety checkpoint before the src restructure.
