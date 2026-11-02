# HANDOFF — adverse-information-assistant

Last updated: 2026-11-01 by Claude

## Current State
November 1: phase 2 of the hosted MCP design is implemented on branch
`claude/pensive-sutherland-5a809b` (pull request against `main`; nothing
deployed). `mcp/` holds the Cloudflare Worker `adverse-information-assistant`
(wrangler.jsonc, worker.js, server.js, http.js, d1.js, release.js, guide.js):
17 tools as design §2.2 enumerates them (the task brief said sixteen; the
design lists seventeen and all are built), three resource families, the 16
agent prompts served verbatim behind a hosted-mode preamble, closed-enum input
validation whose errors never echo a value, `cache-control: no-store` on every
response, and a guide page carrying `DISCLAIMER.md` verbatim.
`scripts/hosted_release.py` builds `mcp/release/` (gitignored: it holds
Government text copied from the approved library release) and passes the
release ids as deploy-time vars; it refuses an unapproved release, re-verifies every section against
the Archivist's body hashes, never flips a verified flag, fetches nothing, and
runs validate_corpus.py and run_tests.py first. The Worker verifies every asset
against manifest.json once per isolate and fails closed per file. 32 CFR §117.8
is reported `unavailable` with the reason because the library carries Part 117
unsplit (D5 default kept). `doha-exclusions.json` carries the 19,502 document
ids the current release marks ineligible (1,161 of them post-SEAD 4).
Verified: dry run against the local approved release `doha-v9-exceptions-20261003`
exits 0 with all checks; `tests/run_tests.py` passes (478, including a guard
that nothing under `agents/` or `scripts/` references `mcp/`, Worker bundle
hygiene, the wrangler posture, the fixture build, and 32 node tests);
`wrangler dev` with the existing Cloudflare login served tools/list,
get_release (counts computed from the live shards: 31,495 / 31,447 / 27,336;
shard meta shows `doha-robot-lf-20260929` beside metadata release
`voi-20260930-v3`, surfaced as designed), find_decisions, verify_case,
get_decision_text and the guide. `DEPLOYMENT.md` gained Mode 1b in the same
commit as the Worker; README links it. Deploy is the owner's call:
`npm run mcp:worker:deploy` (or `hosted_release.py --library … --deploy`).

October 30: phase 1 design for a hosted, stateless MCP server is written at
`docs/HOSTED-MCP-DESIGN.md` (branch `claude/hosted-mcp-design-5ebc3a`; design
only, no Worker code, no corpus files, no deploy). Shape: a reference service at
`fsotools.ai/adverse/mcp` that reuses the Atlas D1 decision shards, serves the
directive sections and the repo's `corpus/` as a hash-checked release in Worker
assets, takes only categorical inputs (never narrative or free text), serves the
agent prompts as MCP prompts so reasoning and session state stay in the client,
and copies the Atlas privacy posture (no logs, no sessions, 60/min). The six local
MCP tools and the deterministic gates stay client-side. It names the redeploy
command for the release-sync agent (`scripts/hosted_release.py`, phase 2) and
records the seven owner decisions (D1-D7) as answered on October 30: Worker
`adverse-information-assistant`; no hosted package verification, ever, the
connector runs in the user's own harness; the site presents it on an MCP
directory page (built in `fsotools-website`, branch `claude/mcp-directory-page`);
shared 60/min limit; exclusions asset now, shard column at the next rebuild. D2
(ship before the reporting tables are verified) and D5 (Part 117 split) stay open
with defaults. Mode 1b ("local session, hosted reference") must be added to
`DEPLOYMENT.md` in the same commit as any Worker.

September 18: Conductor steps 3-6b trimmed from 174 to 79 lines (471 to 376 overall).
They restated rules the requirements advisor, classifier, gap analyst, interviewer
and thread detector already own; the conductor now keeps orchestration, the two
order-changing checklists and the progress line. Interviewer left whole: its rules
are needed at question time. 464 tests pass. All prior Codex work committed.

September 16: shared release integrity now verifies hashes for newly published
DOHA stores. Standalone rebuilt cases and directive sections are compatible;
explicitly ineligible cases are excluded from default precedent selection.

Canonical disclosure assistant; deterministic scripts remain the delivery gates. Pre-existing uncommitted directive lookup/DOHA count fixes and deletion of the consumer-side splitter were preserved. Directive splitting is owned by the Archivist. Added the canonical shared release contract to CLI retrieval/quotation preflight and separate readiness capabilities. Interviews can continue without approved evidence; quotations and case retrieval cannot.

Live Git state: run `python ../workspace_health.py status` from this repository.
Branch, commit, dirty files and last-fetched upstream comparison are generated,
not copied into this document. See `HANDOFF-archive.md` for prior decisions.

## Next
1. Owner reviews and merges the phase 2 pull request, then deploys from their
   machine: `python scripts/hosted_release.py --library "<library root>"` followed
   by `npm run mcp:worker:deploy` (or add `--deploy` to the build). The site's MCP
   directory entry moves from Planned to live only after that, and D2's default
   keeps it unlinked until the reporting tables are verified.
2. Hand the release-sync agent (`mcp-release-sync`) the deploy contract: the
   command, exit codes 0/2/3, and that `--doha-shards` needs `name=id` pairs or a
   logged-in `wrangler d1 list` to resolve database ids.
3. When the Archivist publishes a 32 CFR Part 117 section split, rebuild: the
   builder picks it up from a `manifest.json` under the CFR folder and
   `get_cfr_section` starts serving §117.8 with no code change.
4. When the decision shards carry `answer_eligible`, drop `doha-exclusions.json`
   (D7).

## Open Questions
No new decision needed for the authorized implementation. Prior source-acquisition
and migration questions remain scoped separately as noted above.

## Log
2026-11-02 Claude — Fixed the ten review items on PR #3: event-stream GETs now
get 405 and oversized bodies 413 before the read; a section without a library
body hash refuses the build instead of serving as verified; the Node >= 22.13
need is declared and older nodes skip the node tests visibly; reference tools no
longer wait on D1 (shard metadata is resolved only by get_release and the
decision tools, failures cached 60 s); find_decisions ranks and caps in SQL
per shard and outcome; a release that cannot supply a tool enum fails server
construction; the build no longer rewrites wrangler.jsonc vars (ids travel in
the manifest and as deploy-time --var); the dead env var is gone; the lockfile
is committed. The design's §5.3 carries an implementation note for the vars
change.
2026-11-01 Claude — Implemented hosted MCP phase 2 on a branch and opened a pull
request; nothing deployed. Decisions: the built release is gitignored because it
holds library Government text (the repo never carries it); the Worker loads and
hash-checks every asset eagerly once per isolate rather than lazily, so a bad file
is known before the first tool call; validation errors name only the parameter
and the server's own closed set, never the value; the exclusions asset stores
document ids as designed (1.2 MB) rather than a shorter key; the design's §2.2
tool count is seventeen and all seventeen were built; node tests run from
`run_tests.py` when node is present and print a visible SKIP otherwise, so the
Python-only suite still passes on a machine without node.
2026-10-30 Claude — Recorded the owner's answers to D1-D7 in the design (§7, §5).
Owner asked why the reporting tables are unverified: because `corpus/BUILDING.md`
requires a human line-by-line read against the ISL with the PDF hash recorded, and
that read has not been done. Owner ruled out any hosted verification permanently.
Site presentation becomes an MCP directory page rather than a product page.
2026-10-30 Claude — Wrote the hosted MCP phase 1 design (`docs/HOSTED-MCP-DESIGN.md`)
on a branch. Decisions: reference-only server so Mode 1 holds; categorical inputs
only, no free-text decision search on this endpoint (the Atlas has it); directive
text and `corpus/` as hash-checked Worker assets, decisions from the existing D1
shards plus a derived exclusions asset; prompts serve the agents verbatim with a
hosted-mode preamble; gates stay local and the design says so for shell-less
clients. Corpus population checklist by file is §6; owner decisions §7.
2026-09-18 Claude — Committed and pushed the Sept 10-16 work, then removed duplicated
specialist rules from the conductor, which every session loads in full. Added the
"never name a system the user cannot access" rule to the requirements advisor, the
one conductor rule not already there.
2026-09-16 Codex — Consumer now honors explicit reviewed-case eligibility, while preserving requested
pre-SEAD-4 research. Actual case/section retrieval from a standalone synthetic build
passes; 464 deterministic checks pass. No private case records were read or changed.
2026-09-15 Claude — Made the GitHub repository public at the user's request. Before flipping, scanned all pushed history (8 commits, `main` only) for credentials, personal data and case narratives: none found — fixtures are synthetic, `output/` was never committed, committed handoffs are decision-level. Only pushed commits are exposed; the uncommitted work here is not. Still open from `PUBLISHING.md`: `corpus-sources.yaml` distribution link and contact are `TODO` placeholders. Workspace `CLAUDE.md` backup note updated to match.
2026-09-10 Codex — Completed authorized implementation. 464 deterministic tests and 17 product tests pass. Temporary published fixture exercises the real readiness gate; unapproved fixture retrieval and quotation are rejected. Live library was not modified. Changes remain uncommitted, including preserved prior edits.
2026-09-10 Codex — Implementing the five authorized workspace improvements and accepted-answer wiki. Preserved the entire prior handoff in the archive, including pre-existing edits. Validation is in progress; do not interpret implementation as a live library release.
