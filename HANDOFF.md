# HANDOFF — adverse-information-assistant

Last updated: 2026-09-16T19:47:19.937753+00:00 by Codex

## Current State
September 16: shared release integrity now verifies hashes for newly published
DOHA stores. Standalone rebuilt cases and directive sections are compatible;
explicitly ineligible cases are excluded from default precedent selection.

Canonical disclosure assistant; deterministic scripts remain the delivery gates. Pre-existing uncommitted directive lookup/DOHA count fixes and deletion of the consumer-side splitter were preserved. Directive splitting is owned by the Archivist. Added the canonical shared release contract to CLI retrieval/quotation preflight and separate readiness capabilities. Interviews can continue without approved evidence; quotations and case retrieval cannot.

Live Git state: run `python ../workspace_health.py status` from this repository.
Branch, commit, dirty files and last-fetched upstream comparison are generated,
not copied into this document. See `HANDOFF-archive.md` for prior decisions.

## Next
1. Use the approved-release readiness result at the next session; deterministic and product regressions are complete.
2. Commit/review the pre-existing fixes together with the current scoped changes when ready.
3. Use a refreshed approved Custodian release when a missing or inconsistent library prevents evidence access.

## Open Questions
No new decision needed for the authorized implementation. Prior source-acquisition
and migration questions remain scoped separately as noted above.

## Log
2026-09-16 Codex — Consumer now honors explicit reviewed-case eligibility, while preserving requested
pre-SEAD-4 research. Actual case/section retrieval from a standalone synthetic build
passes; 464 deterministic checks pass. No private case records were read or changed.
2026-09-15 Claude — Made the GitHub repository public at the user's request. Before flipping, scanned all pushed history (8 commits, `main` only) for credentials, personal data and case narratives: none found — fixtures are synthetic, `output/` was never committed, committed handoffs are decision-level. Only pushed commits are exposed; the uncommitted work here is not. Still open from `PUBLISHING.md`: `corpus-sources.yaml` distribution link and contact are `TODO` placeholders. Workspace `CLAUDE.md` backup note updated to match.
2026-09-10 Codex — Completed authorized implementation. 464 deterministic tests and 17 product tests pass. Temporary published fixture exercises the real readiness gate; unapproved fixture retrieval and quotation are rejected. Live library was not modified. Changes remain uncommitted, including preserved prior edits.
2026-09-10 Codex — Implementing the five authorized workspace improvements and accepted-answer wiki. Preserved the entire prior handoff in the archive, including pre-existing edits. Validation is in progress; do not interpret implementation as a live library release.
