# HANDOFF — adverse-information-assistant

Last updated: 2026-11-12 by Claude

## Current State
November 9 (committed b6145ff, merged as PR 11 and deployed 2026-11-12,
see below): DCSA's Adjudicatively Ready Product
Reference Guide (dcsa.mil, read in the app's browser pane at the owner's
request; no page text copied into the repo) is restated as
`corpus/checklists/_ADJUDICATIVE_READINESS.yaml` — `maintainer_verified:
false`, source URL and retrieval date recorded, paraphrase throughout. It
carries: the readiness definition; the timeline rule (report now, never wait
for documents, DECLARE which are pending; the industry supplement is the FSO's
Supplemental Information CSR, never the user's action); the six-question
incident picture mapped onto the coverage facets; ten statement factors
(self-reported-and-why plus the nine whole-person factors) each mapped to
checklist element ids; and per-guideline supporting-document lists where every
entry has `obtain_by` (subject | security_office | either) so office-held
records are named for the user to point to, never assigned to them to fetch.
`validate_corpus.py` gained `check_adjudicative_readiness()` (every factor id
and facet must resolve; every document needs custodian, purpose and a valid
`obtain_by`). `_UNIVERSAL.yaml` gained `knowing-participation` and
`voluntariness` (`adverse_conduct_only: true`, skipped on administrative-tone
events). `_COVERAGE.yaml` definitions now carry incident date vs report date,
jurisdiction, and the handling-and-resolution half of "how"; a new sources
line cites the guide. `privacy-tiers.yaml` adds `victim_or_minor_identity` to
the never-collected floor. Agents updated to read the file: documents advisor
(two-catalog rule, `status` and `obtain_by` on every document, pending
declared never omitted), gap analyst (statement-factor sweep after the facet
sweep), narrative writer (two dates, handling, self-reported-and-why, factor
check that never writes around a gap), interviewer (two dates, handling,
victims/minors floor), conductor (step 5 source f, step 8 wording; anchors
unchanged). `assemble_package.py` renders document `status` and `obtain_by`
and a pending-documents declaration. Corpus VERSION bumped to 0.1.1-scaffold
(index rebuilt; the node test's deploy-var pin updated to match). Full suite:
499 pass. Process map re-rendered. The file's `saved_copy` block (added in the
same working session by another writer, kept) points at a PDF of the page
saved outside the repo with its SHA-256 and a content-text hash; a short note
describing the page as read also sits in `output/reference/` (gitignored).
Both exist for the maintainer's verification pass.
Same day, second pass (owner asked whether the workflow can actually get the
documents, including lost ones): `corpus/documents/retrieval.yaml` is a
maintainer-authored retrieval directory, 44 entries, one per document type —
custodian, request path, form or portal, identification needed, approximate
lead time, cost, and a separate `lost_original` replacement path (Form I-90,
N-565, DS-64/DS-11, SF-180, the HIPAA right of access, AnnualCreditReport,
IRS Get Transcript, PACER, and so on), each with an official `source_url`
and `verified: false`. `obtainable_by` is `subject`, `security_office` (no
user task) or `third_party_only` (a relative's card: ask for a copy, never
replace it). Every one of the 65 readiness documents now carries a
`retrieval_ref`; `validate_corpus.py` requires the ref and resolves it
(`check_retrieval_directory`, `retrieval_entry_ids`). `scripts/document_lookup.py`
mirrors `court_lookup.py`: `--doc`, `--for-guideline`, `--list`,
`--check-links` (no network). The documents advisor asks one question per
document — in hand, or to be requested — and reads the replacement path when
the answer is "lost". Full suite: 512 pass.
A forked session (f01dd4a3) added `corpus/courts/state-records-sources.yaml`
— 51 jurisdictions with dmv, tax, criminal_history and child_welfare
custodians plus a national list — and took the Worker wiring; this session
wired that directory in: `document_lookup.py --state XX` attaches the state
agency and national front doors through `state_directory_key` and
`national_ref` on retrieval entries (46 entries now, including
state-criminal-history), `validate_corpus.py` has `check_state_records_sources()`
and resolves both pointer kinds, `--check-links` lists its URLs too.
The forked session then wired the hosted Worker: `hosted_release.py`
MAINTAINER_FILES carries `_ADJUDICATIVE_READINESS.yaml`,
`courts/state-records-sources.yaml` and `documents/retrieval.yaml`;
`server.js` serves them through the existing `get_corpus_file` enum
(`adjudicative-readiness`, `state-records-sources`, `document-retrieval`) and
as `adverse://corpus/<file>` resources rather than a new tool, so the design's
seventeen-tool count and every pinned test hold; `court_lookup` returns the
same state's `records_sources` beside the court record; the documents-advisor
prompt preamble names all three. NOT DONE: both restatements are unverified against the live pages
(`document_lookup.py --check-links` lists the URLs to open).

REDEPLOYED 2026-11-12 at the owner's instruction ("push it to the live
page"): PR 11 merged to `main` (aa29b1b), then `hosted_release.py --deploy`
from `main` — corpus validation and the full suite passed, 101 files built,
12 assets uploaded, Worker version 985c6565-2a09-4244-9f27-df583f850110, and
the builder's live `get_release` confirmed the new ids (library
doha-new-20261103, corpus 0.1.1-scaffold, commit aa29b1b). The three new
corpus files were not called one by one on the live endpoint (an ad-hoc
network check was refused in the session); the node tests cover them against
the same hash-checked release folder. The checkout is back on `main`: the
daily release sync had deferred on 11-09, 11-10 and 11-11 because this
checkout sat on `claude/dcsa-adjudicative-readiness`.

DEPLOYED with the owner's approval: Worker `adverse-information-assistant` at
`https://fsotools.ai/adverse/mcp`, from `main` 814e644 (PR 3, reviewed with ten
findings all fixed in 893e51f, merged by the owner). Two sessions deployed the
same build within minutes of each other on 2026-11-03 UTC: version 03d95d7b via
`hosted_release.py --library … --deploy`, then version 3aebd4cf (~00:45 UTC) via
the wrangler command the builder prints with `RELEASE_ID`, `CORPUS_VERSION` and
`REPO_COMMIT`; the content is identical and 3aebd4cf is the live version. Live
checks: protocol 2025-06-18, 17 tools listed, `get_release` reports library
`doha-v9-exceptions-20261003`, corpus 0.1.0-scaffold, commit 814e644 and the
three `doha-robot-lf-20260929` shards; the guide page serves with the
`claude mcp add` line; `GET` with `Accept: text/event-stream` answers 405. The
builder's own post-deploy confirmation first got a 403: the zone's
browser-integrity check (Cloudflare error 1010) rejects urllib's default user
agent before the Worker runs, so `rpc_live_get_release` now names itself; MCP
clients were unaffected. `package-lock.json` now carries the `engines` field
npm syncs from package.json, so `npm install` no longer rewrites it. The
website lists the connector as Live on /mcp/. REDEPLOYED 2026-11-03 ~01:20 UTC (version 8f9a759b-c7ed-48ad-bed9-c8053b425b25,
`hosted_release.py --deploy` from `main` bfe0d01, live `get_release` confirmed by the
script): PR 6 gave every tool MCP annotations (`readOnlyHint: true`, `destructiveHint:
false`, `idempotentHint: true`, `openWorldHint: false`; `READ_ONLY` in server.js) and
bumped the server to 0.1.1, so ChatGPT's chat mode no longer asks before each call;
the http test checks all 17. Live check: 17 tools, one annotation set, version 0.1.1.
Open: `mcp-release-sync` has no `adverse_mcp` hook yet. 32 CFR §117.8
is served as `unavailable` (D5 default).

November 1: phase 2 of the hosted MCP design was implemented on branch
`claude/pensive-sutherland-5a809b` (PR 3, merged 2026-11-03). `mcp/` holds the Cloudflare Worker `adverse-information-assistant`
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
0. Done 2026-11-12 (PR 11, redeployed as version 985c6565): the November 9
   readiness, retrieval, state-directory and Worker work is on `main` and
   live. Still open: the maintainer verifies the restatements against the
   live pages (`document_lookup.py --check-links`) before any
   `maintainer_verified` flip. The saved DCSA guide and its annotated
   companion (a PDF and a Word copy of each) live outside the repo, still in
   a session scratch folder awaiting a permanent home; the PDF hashes are in
   `_ADJUDICATIVE_READINESS.yaml` under `saved_copy`.
1. Done 2026-11-03 (PR 6, redeployed as version 8f9a759b): MCP tool annotations.
   D2's default keeps the reporting tables unlinked until they are verified.
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
2026-11-12 Claude (fork f01dd4a3) — The owner said to push the readiness work
live. Pushed the branch, merged PR 11, deployed the Worker from `main` as
version 985c6565 and returned the checkout to `main`. Decisions: merge before
deploying so the live `REPO_COMMIT` is a commit on `main` and the daily
release sync, which had deferred three days on this checkout's branch, can
run again; the saved guide and companion were also produced as Word
documents, kept outside the repo like the PDFs.
2026-11-09 Claude (fork f01dd4a3) — Saved the DCSA readiness guide as a PDF
whose content text hashes identically to the live page (dcsa.mil refuses
automated browsers, so the content came through the app's browser pane and
was transcribed, then proved by hash), built an annotated companion PDF with
per-guideline "where to obtain" boxes and a 51-state custodian table, and
authored `corpus/courts/state-records-sources.yaml` to back it. Decisions:
both PDFs stay outside the repo (Government text) with hashes recorded in the
readiness file; the companion's 312 links are unchecked because the link
probe was refused and the repo makes no network calls, so the PDF says so;
the Worker serves the three new files through the existing `get_corpus_file`
enum rather than a new tool, keeping the tool count and the design intact.
Coordinated by message with the parallel session, which owned the agents,
validator and tests while this fork owned the Worker, builder and design doc.
2026-11-09 Claude — Added the document retrieval directory and
`document_lookup.py` after the owner asked whether the tool can actually help
someone obtain, or replace, the records the readiness guide calls for.
Decisions: directory information under the court aid's contract (offered,
never asserted, unverified until a human opens each source page, never
fetched); `obtainable_by` so a security-office record is never a user task
and another person's document is asked for, never replaced; lead times and
fees kept approximate so nothing stale is stated as fact; every readiness
document must resolve to a retrieval entry or the build fails. 512 checks
pass; nothing committed.
2026-11-09 Claude — Folded DCSA's Adjudicatively Ready Product Reference Guide
into the tool as a maintainer-authored restatement (`_ADJUDICATIVE_READINESS.yaml`),
with validator cross-checks, two universal participation elements, coverage and
privacy-floor refinements, agent updates and a pending-documents declaration in
the assembler. Decisions: restate rather than copy (Government text never enters
`corpus/`, and the page has no stable hash, so retrieval date is the version);
translate the FSO-facing guide for the subject via `obtain_by`, so no
security-office record ever becomes a user task and no system the user cannot
access is presented as theirs; "applicable" factors become neutral gap questions,
never sentences the writer composes; the Worker is left unchanged for now. 499
checks pass; nothing committed.
2026-11-03 Claude — Read-only annotations on every tool (PR 6, server 0.1.1); redeployed as version 8f9a759b with the owner's approval and checked live.
2026-11-03 Claude — Deployed the hosted MCP Worker (version 3aebd4cf) from merged main with the owner's approval and checked it live; noted the missing tool annotations.
2026-11-02 Claude — Deployed the Worker after the owner merged PR #3 and said
"Deploy it". Build, corpus validation, the full suite and the deploy passed; the
script's live confirmation hit the zone's browser-integrity check (403, error
1010) on urllib's default user agent, so `rpc_live_get_release` now names
itself. Re-run of the confirmation matched the deployed ids. Decision: no zone
rule change; a named user agent is the right fix because the check protects
the whole site and real MCP clients pass it.
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
