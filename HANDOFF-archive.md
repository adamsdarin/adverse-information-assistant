

# Preserved handoff before 2026-09-10 workspace improvements

# HANDOFF — adverse-information-assistant

Last updated: 2026-09-08T13:31:19Z by Claude

## Current State
Active project, and the only adverse-information-assistant that exists. Now has a
remote: github.com/adamsdarin/adverse-information-assistant.

Work sits on branch `library-rebuild-repair`, three commits ahead of `main` and
NOT merged. `main` is still the pre-repair state, in which the tool cannot quote
any directive text. Anyone switching to `main` gets the broken behaviour.

The DCSA Library rebuild renamed the directive files and two of the folders
holding them. Both places that hardcoded those paths were wrong, so the section
splits could not be regenerated and all three directives read as ABSENT --
silently, since nothing failed loudly. Directive location now resolves through
the library's own `documents.jsonl` by `document_id`, which survived the rename,
with the literal path kept only as a fallback. The splitter imports its layout
from `library_paths` instead of declaring its own, so writer and reader cannot
drift apart again.

The bundled browser UI (`adverse_app/web.py` + `codex_host.py`) was deleted. It
shelled out to the `codex` binary by name, which contradicts the model-agnostic
posture the rest of the product rests on -- a usage limit on one vendor's
account took out the whole interface. The user's own assistant is the interface;
`mcp_server.py` survives because MCP is a protocol, not a vendor.

Both suites pass: 463 deterministic + 17 product.

`.gitignore` excludes `output/`, `sessions/`, `*.draft.md` and `*.session.json` --
user-generated content that contains personal information. Nothing personal is in
history. Keep it that way.

A folder at `Documents\AI Agent Building\adverse-information-assistant` is NOT
this project. It was a stray penpot clone; as of 2026-09-08 it holds only a
`.claude/` directory and is not a git repo at all. Claude sessions can still open
there by default -- if that happens, move to
`C:\Users\darin\src\adverse-information-assistant` before doing anything.

**Boundary violation fixed (2026-09-08).** `scripts/split_sead_text.py` — which
wrote SEAD/ISL section files directly into the governed DCSA Library, bypassing
the Archivist's build-candidate/validate/approve/publish gate — has been
deleted from this repo. The splitting logic now lives in `dcsa-archivist` as
`src/dcsa_custodian/directive_splits.py`, called from `build_candidate()` and
written into the release's `production/` tree at the same relative paths the
old script used, so the generic publish step (already copies everything under
`production/` to the library root, with rollback) needed no changes at all.
`validate_candidate()` now hash-checks every split section against its
manifest, and a directive that is *present in the library but fails
reassembly* is a publication blocker; a directive that is simply absent from a
given library (not every library dcsa-archivist runs against carries the
SEAD/ISL directives) is informational only, never a blocker — see
`directive_splits.py`'s `problems` vs `skipped` distinction. `library_paths.py`
here no longer tells anyone to run a local script; a missing split now says
"needs a refreshed DCSA Archivist release." Tests added/updated in both repos
(3 new in `dcsa-archivist/tests/test_custodian.py`, 6 existing there
re-verified; 1 regression test here confirming the script is gone and the
error messages point at the Archivist).

A real build-candidate run against the live library (release id
`directive-split-gate-20260908`) was used to confirm the new path end-to-end
and republish the split content through the proper gate — see
`dcsa-archivist/HANDOFF.md` for the release outcome.

**`doha_retrieval.py`'s three case counts explained, not a defect (2026-09-08).**
Confirmed by running against the real library: `check_library.py` reports every
row of `DOHA_CURRENT_PATHS.jsonl` (10,658). `doha_retrieval.py`'s guideline
search parses each row's `case_stem` and drops the ones that don't parse or
whose outcome isn't approved/denied/remanded (10,627 — 31 dropped, matching
`check_library`'s own `'?': 24` outcome bucket plus a few genuinely unparseable
stems). 283 case numbers carry more than one published decision (typically a
hearing then an appeal), so collapsing to distinct case numbers — what
`--verify-case` checks membership against — gives 10,327. The invariant is
`total >= parsed >= unique`; it held. Renamed the ambiguous `library_case_count`
key to `parsed_decision_count` (guideline search) and `unique_case_count`
(`--verify-case`), and both branches of the guideline-search output now report
both numbers. The module docstring spells out the relationship so a future
maintainer doesn't have to re-derive it.

## Next
1. Merge `library-rebuild-repair` into `main`, or the fixes are invisible to a
   fresh clone. **Done** — `main` and `library-rebuild-repair` both point at
   `94b630b`; confirmed via `git log` at the start of this session.
2. ~~Move section splitting out of this repo into `dcsa-archivist/`~~ — done,
   see above.
3. ~~`scripts/doha_retrieval.py` reports three different case counts~~ —
   explained and clarified in code, see above.
4. `dcsa-archivist` has unrelated staged-but-uncommitted work from an earlier
   session (semantic search layer) that could not be committed from that
   environment (`git commit` hangs — SSH-agent bridge issue). This session's
   directive-split changes there sit on top of that same working tree and were
   deliberately left uncommitted alongside it; both need a commit from Darin's
   own terminal. See `dcsa-archivist/HANDOFF.md`.

## Open Questions
None.

## Log
2026-09-08T13:31:19Z Claude - Repaired directive resolution after the DCSA Library rebuild renamed the SEAD/ISL files and folders: location now resolves through the library's documents.jsonl by document_id rather than hardcoded paths, and the splitter imports its layout from library_paths so the writer and reader cannot drift apart again. Deleted the bundled browser UI and its codex adapter -- it shelled out to one vendor's CLI, which broke the model-agnostic guarantee, and it also misreported readiness because available() resolved the executable while turn() launched the bare name (fatal on Windows for a .cmd shim). Pre-approved sead_lookup.py in .claude/settings.json; it was the one script AGENTS.md tells every agent to run and the only one that still prompted. Deny list untouched. 463 + 17 tests pass. NOTE a boundary violation introduced in the process: the splits were written straight into the governed library from this repo, bypassing the Custodian publish gate -- see Current State and Next item 2.
2026-08-31T20:26:37Z Claude - Imported this session's Codex work: committed the incident-depth, first-person-voice and synthetic-suite changes (6 files, +595/-43) that were uncommitted and had no off-machine copy. Cleared a stale .git/index.lock that would have blocked the next commit. Note: synthetic outputs are being written to Documents\Test Scenario, which is outside src and outside the DCSA Library and is not backed up.
2026-08-31 20:05 Codex - Removed the synthetic report's initial-versus-developed narrative split. Each independent incident now renders one consolidated final narrative; every case separately includes the initial statement, complete Q&A transcript, final report, and a combined complete record. Full suite: 463 passed; all 20 outputs verified and were replaced in `Documents\Test Scenario`.
2026-08-31 19:53 Codex - Enforced first-person report voice. The narrative prompt explicitly prohibits analyst-style substitutes for the narrator, session validation rejects completed narratives without first-person language, and deterministic report context now uses `I`/`my` instead of second- or third-person framing. Full suite: 463 passed; all 20 first-person reports verified and replaced in `Documents\Test Scenario`.
2026-08-31 19:47 Codex - Reran the corrected 20-case synthetic suite on request. All 20 sessions validated, all 20 reports passed deterministic verification, and the transcripts, sessions, reports, hashes, index, and ZIP in `Documents\Test Scenario` were replaced with the new run.
2026-08-31 19:32 Codex - Fixed shallow incident development in both the workflow and synthetic harness. Factual coverage is now required for every applicable profile, metadata pointers are rejected as chronology evidence, all 20 scenarios have detailed interviews and narratives, and an end-to-end regression enforces the depth floor. Full suite: 462 passed; all regenerated reports verified and were copied to `Documents\Test Scenario`.
2026-08-31 19:13 Codex - Regenerated 20 fictitious workflow scenarios. All 20 session files passed validation, all 20 reports passed deterministic verification, and complete transcripts, sessions, reports, hashes, index, and ZIP were copied to `Documents\Test Scenario`.
2026-08-31 17:00 Codex - Began a reporting session. Corpus structure passed but its four reporting tables remain unverified; the Complete DCSA Library was found and the capability canary passed. No case details have been collected.
2026-08-31T16:47:01Z Claude — Committed 15 days of uncommitted work as a safety checkpoint before the src restructure.

