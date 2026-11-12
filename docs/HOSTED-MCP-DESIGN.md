# Hosted MCP server — phase 1 design

Status: design only. No Worker code, no corpus files, no deploy. Written
2026-10-30 against commit `d2c0e25`.

This document designs a hosted, **stateless** Model Context Protocol (MCP)
server for the Adverse Information Assistant at `https://fsotools.ai/adverse/mcp`.
It follows the Adjudication Atlas server (`doha-guidelines-nexus/mcp/`, Worker
`doha-atlas-mcp`, live at `/atlas/mcp` since 2026-10-29) wherever the two
problems are the same, and departs from it where this tool's privacy promise
requires.

## Terms

- **Corpus** — everything the hosted server serves: the Government text it
  quotes, the maintainer-authored analysis files, and the published DOHA
  decision text. Two authorship halves, as in `ARCHITECTURE.md` §5.1:
  - the **maintainer-authored files**, which are the repo's `corpus/`
    directory (checklists, reporting tables, form maps, courts, privacy tiers);
  - the **Government text**, which comes from an approved DCSA Library release
    (SEAD 3, SEAD 4, ISL 2021-02, 32 CFR Part 117, DOHA decisions).
- **Repository** — only DOHA's own site (doha.ogc.osd.mil) or a Git repository.
- **Release** — one hash-checked, human-approved snapshot of the corpus that a
  Worker deployment pins. Two release ids travel together: the library release
  (`doha-robot-lf-20260929` today) and the maintainer corpus version
  (`corpus/VERSION`, `0.1.0-scaffold` today).
- **Client** — the user's own AI assistant (Claude Desktop, Claude Code,
  Cursor, Codex, a plain MCP client). It holds the session, runs the agents,
  and runs the deterministic gates. The server never sees the session.

## 0. The one constraint that shapes everything

`DEPLOYMENT.md` Mode 1 promises that the narrative is not stored, logged or
transmitted by this project. A server that holds sessions is Mode 2, with
operator disclosure duties the owner does not want to take on, and a
materially different product.

So the hosted server is a **reference service**, not a session service. It
answers the same questions the local scripts answer from disk —
`sead_lookup.py`, `doha_retrieval.py`, `court_lookup.py`, `check_library.py`,
and the agents' reads of `corpus/` — and nothing else. Three rules follow:

1. **No tool accepts a string the user could have typed.** Every input is a
   categorical value from a closed set the server itself publishes: a
   guideline letter, an access tier, a population, an event id, a form name, a
   state code, a decision id the server returned earlier. No narrative, no
   free-text search, no county names, no business names.
2. **No request leaves a trace in the Worker.** Observability off, no logs,
   no storage bindings that can be written, no cookies, `cache-control:
   no-store` on tool responses.
3. **The reasoning stays in the client.** The agent prompts are served as MCP
   prompts so a client can run the conductor's flow against the hosted
   reference layer, but the server never runs an agent, never classifies,
   never drafts, never verifies a package.

The result is a new deployment sub-mode, **Mode 1b: local session, hosted
reference**, which `DEPLOYMENT.md` must gain in the same commit as the Worker
(its "rule for maintainers" already requires this). What leaves the user's
machine in Mode 1b, stated for the Stage 1 disclosure:

- the categorical queries themselves (for example "Guideline G and J", "ts_q",
  "industry"), which do reveal the *shape* of the matter to the server — a
  client that wants to disclose nothing at all can fetch the whole maintainer
  corpus and directive text in one call (`get_corpus_bundle`, §2.2) and query
  decisions only if it chooses to;
- the client's IP address, which Cloudflare sees at the edge and the rate
  limiter keys on, and which Cloudflare's own zone analytics may count outside
  the Worker's control. The Worker itself records nothing.

Suggested Stage 1 language for Mode 1b, to be finalised in `DEPLOYMENT.md`:

> "Running locally. Nothing you type is stored or transmitted by this tool.
> When I need reference material — a guideline's text, a reporting table, a
> published decision — I ask fsotools.ai for it by category (a guideline
> letter, an event type), never in your words, and that server keeps no logs.
> Your words do go to the model provider you've configured, under their
> terms."

## 1. Corpus parts and where each lives on Cloudflare

### 1.1 Decision text — reuse the Atlas D1 shards

The full text of all published DOHA decisions already sits in three D1 FTS5
shards built by `doha-decision-search` from the approved library release:
`doha-text-doha-robot-lf-20260929-s1`, `-s2`, `-s3`. The adverse Worker binds
them read-only as `S1`, `S2`, `S3`, exactly as `doha-atlas-mcp` does, and
**builds nothing of its own for decisions**.

Each shard carries two tables the adverse tools need:

- `decisions` (`decision_id`, `document_id`, `case_id`, `decision_level`,
  `decision_family`, `outcome`, `guideline_codes`, `case_year`,
  `decision_date`, `era`, `source_url`, `content_sha256`, …) — enough to port
  `doha_retrieval.py` (select by guideline overlap, prefer the post-SEAD 4
  era, alternate outcomes) and `--verify-case` (the citation allowlist) with
  no asset of our own.
- `passages` (FTS5; `body`, `decision_id`, `part`, `first_page`,
  `last_page`, …) — the text the precedent miner reads, fetched **by decision
  id and part**, never by a search string (§2.2).
- `meta` — the shard's own `release_id` and `metadata_release_id`. The Worker
  reports these, not a number copied into documentation; today the database
  *names* say `doha-robot-lf-20260929` while `meta.metadata_release_id` says
  `voi-20260930-v3` (links and dates were patched from that release). Both are
  surfaced in `get_release` so a mismatch is visible rather than papered over.

Two things the local script has that the shards do not:

- **Explicit ineligibility.** The library manifest marks some decisions
  `answer_eligible: false`, and since 2026-09-16 the local retrieval excludes
  them from default precedent selection. The `decisions` table has no such
  column. The release build (§1.4) therefore publishes a small
  `doha-exclusions.json` asset — the `document_id`s the current library
  release marks ineligible — and `find_decisions` applies it. If the Custodian
  later adds the flag to the shard schema, the asset goes away.
- **The three counts.** `doha_retrieval.py` documents that total, parsed and
  unique-case counts legitimately differ. The hosted tool computes all three
  from the shards at load and reports them in `get_release`; nothing hardcodes
  a count.

### 1.2 Government text — a hash-checked release in Worker assets

These are the directive sections the local tool reads **one section at a
time** through `sead_lookup.py`, straight from the approved library release's
section splits. They are small (tens of files, well under a megabyte in all),
fetched by key, never searched — so they go in **Worker static assets**, not
D1. Every file is copied byte-for-byte from the library release at build time,
and its SHA-256 is recorded in the release manifest (§1.4).

| Directive | Library source (relative to the library root) | Files | Selected by |
|---|---|---|---|
| SEAD 4 | `ROBOT_READABLE_DIRECTORY/TEXT/PERSONNEL_VETTING/SECURITY_EXECUTIVE_AGENT_DIRECTIVES_SEAD/SEAD-4_Adjudicative-Guidelines/` | 17: overview, Appendix A (adjudicative process — **always attached**), Guidelines A–M, Appendix B (Bond Amendment), Appendix C (exceptions) | guideline letter |
| SEAD 3 | `…/SEAD-3_Reporting-Requirements/` | 6: overview (always), all covered individuals (always), Secret/Confidential/L, Top Secret/Q, responsibilities, Appendix A required data elements | access tier; the additive rule (F + G *or* F + H, never a ladder) is computed server-side exactly as `library_paths.py` does |
| ISL 2021-02 (v2, May 2024) | `ROBOT_READABLE_DIRECTORY/TEXT/INDUSTRIAL_SECURITY/INDUSTRIAL_SECURITY_LETTERS_ISL/CURRENT/2021-02_SEAD-3_rev-2024/` | 5: overview and adverse-information guidance (always), Tables 1–4 | table number, or the corpus reporting table it is source of record for (`--verifies`) |
| 32 CFR Part 117 | `ROBOT_READABLE_DIRECTORY/TEXT/AUTHORITIES/CFR/32 CFR 117 … 2025-07-01.txt` | 1 unsplit file; **§117.8 is the only section this tool needs** | section `117.8` |

Each directory's `manifest.json` from the library release is copied too; the
Worker uses it to map a guideline letter or table number to a file rather than
parsing filenames.

Only ISL 2021-02 is in scope among DCSA letters: it is the source of record
for the corpus reporting tables. Other ISLs, VOIs and agency implementations
of SEAD 3 are the Question Bot's domain and are not served here (decision D5).

Why assets and not D1 for this text: a D1 row would be fetched by the same
key, with a query round-trip the asset fetch avoids, and D1 invites the
free-text search this design forbids. Should the Government text ever exceed
what assets handle comfortably (it will not for four directives), R2 is the
next store, not D1.

### 1.3 Maintainer-authored files — the repo's `corpus/` as JSON assets

The files the agents read from `corpus/` today, converted YAML to JSON at
build time, served as Worker assets, each stamped with the SHA-256 of the
YAML it was built from, the repo commit, and `corpus/VERSION`. Their
`maintainer_verified` flags are **served as they are**; the build never flips
one, and every tool that returns one of these files returns its flag, so a
client degrades to "consult your security office" exactly as the local agents
do. Today every one of them is `false`; §6 is the plan for changing that.

| Group | Files | Served through |
|---|---|---|
| Reporting | `reporting/authority-layers.yaml`, `reporting/tables/{all-covered-individuals,adverse-information,top-secret-q,channels}.yaml` | `get_reporting_tables` (§2.2) |
| Guideline checklists | `checklists/guideline-{A..M}.yaml`, `checklists/_UNIVERSAL.yaml`, `checklists/_COVERAGE.yaml` | `get_checklists` |
| Event checklists | `checklists/events/event-*.yaml` (13), `checklists/events/_INDEX.yaml` | `get_checklists`, `list_event_types` |
| Incident development | `checklists/_INCIDENT_CHRONOLOGY.yaml`, `checklists/_INCIDENT_PROFILES.yaml` | `get_corpus_file` / resources |
| Depth and documents | `checklists/_SEVERITY_LADDERS.yaml`, `checklists/_DOCUMENT_EVIDENCE.yaml` | `get_severity_ladder`, `get_document_evidence` |
| Forms | `forms/collection-policy.yaml`, `forms/sf86-map.yaml`, `forms/pvq-map.yaml`, `forms/incident-report-map.yaml`, `forms/entity-capture.yaml`, `forms/diss-incident-types.yaml`, `forms/pvq-preambles.md` | `get_form_map`, `get_corpus_file` |
| Courts | `courts/state-courts.yaml` | `court_lookup` |
| Session policy | `privacy-tiers.yaml`, `checks/plausibility.yaml` | `get_corpus_file` / resources |
| Version | `VERSION` | `get_release` |

**Not published:** `corpus/sead4/*.md` and `corpus/reporting/{sead-3,isl-2021-02,32cfr117-8}.md`.
They are placeholders; the local tool already quotes directive text from the
library split, not from these files, and `tests/run_tests.py` fails the build
if Government text appears in them. The hosted server quotes the same library
text (§1.2). `corpus/doha/` (the retired hand-curated case folder, now just a
template and naming note) is not published either; decisions come from §1.1.
`corpus/checklists/_TEMPLATE.yaml` and `sead4/_TEMPLATE.md` are templates,
not content.

### 1.4 The release bundle and its manifest

A build script (phase 2; this design names it `scripts/hosted_release.py`)
produces one directory, `mcp/release/`, holding §1.2 and §1.3 plus
`manifest.json`:

```json
{
  "corpus_version": "0.1.0-scaffold",
  "repo_commit": "d2c0e25",
  "library_release": "doha-robot-lf-20260929",
  "library_approval": { "approved_by": "...", "approved_utc": "..." },
  "doha_shards": ["doha-text-doha-robot-lf-20260929-s1", "..."],
  "built_utc": "...",
  "files": {
    "government/sead-4/09_Guideline_G_Alcohol_Consumption.md": {
      "sha256": "...",
      "source": "library:ROBOT_READABLE_DIRECTORY/TEXT/.../09_Guideline_G_Alcohol_Consumption.md",
      "verified": true, "verified_by": "custodian-release" },
    "corpus/reporting/tables/adverse-information.json": {
      "sha256": "...", "source_sha256_yaml": "...",
      "source": "repo:corpus/reporting/tables/adverse-information.yaml",
      "verified": false, "verified_by": null }
  }
}
```

Build rules, all of which refuse rather than warn:

- The library release must pass the same contract `release_contract.py`
  enforces locally (published, approved, no blockers, metadata hashes match).
  An unapproved library is not a source.
- Every Government file's SHA-256 must match what the library's own manifests
  record, where they record one; the build computes and stores it either way.
- The build **fetches nothing**. Inputs are the library root on disk and the
  repo checkout. `never_auto_fetch` applies to the build exactly as it applies
  to agents.
- The build never changes a `maintainer_verified` value. A maintainer-authored
  file is `verified: true` in the manifest only when its YAML carries
  `maintainer_verified: true` with the provenance `validate_corpus.py`
  demands (`source_url`, `source_sha256`, `verified_date`).
- `validate_corpus.py` and `tests/run_tests.py` must pass on the checkout
  being built.

The Worker loads `manifest.json` once per isolate, verifies the SHA-256 of
every asset it serves on first use (`crypto.subtle.digest`; the set is small),
and fails closed on a mismatch — the tool returns an error naming the file,
never the file. This is the hosted equivalent of the local readiness check.

"Human-verified" therefore means two different, both-true things: Government
text is verified by the Custodian's release approval and its hash chain;
maintainer-authored files are verified file by file by a human, and until one
is, every tool says so.

## 2. Tool list for the JavaScript Worker

### 2.1 Mapping from what exists today

The local MCP facade (`adverse_app/mcp_server.py`) has six tools:
`session_status`, `next_intake_question`, `answer_intake_question`,
`validate_session`, `assemble_package`, `verify_package`. **All six operate on
`output/session.json` and none is hosted.** They stay exactly where they are,
in the user's client, because each one either reads or writes the session.
The hosted server replaces the *other* thing the local tool depends on: the
disk reads behind the agents and the retrieval scripts.

| Local behaviour | Where it lives | Hosted tool(s) |
|---|---|---|
| `check_corpus.py`, `check_library.py`, intake stage 0 | scripts | `get_release` |
| `sead_lookup.py --guidelines` (classifier, narrative writer quoting) | script | `get_guideline_text` |
| `sead_lookup.py --reporting --access` (requirements advisor) | script | `get_reporting_requirements` |
| `sead_lookup.py --isl --isl-tables` / `--verifies` | script | `get_isl_section` |
| 32 CFR §117.8 (requirements advisor, industry) | library | `get_cfr_section` |
| requirements advisor reading `corpus/reporting/` | agent read | `get_reporting_tables`, `list_event_types` |
| gap analyst sources 1–3 (event, guideline, universal, coverage) | agent read | `get_checklists` |
| gap analyst source 4, conductor crosswalk | agent read | `get_form_map` |
| incident developer (chronology, profiles) | agent read | `get_corpus_file`, resources |
| interviewer depth (`_SEVERITY_LADDERS`) | agent read | `get_severity_ladder` |
| documents advisor (`_DOCUMENT_EVIDENCE`) | agent read | `get_document_evidence` |
| `court_lookup.py` | script | `court_lookup` |
| `doha_retrieval.py --guidelines` (precedent miner selection) | script | `find_decisions` |
| `doha_retrieval.py --verify-case` (verifier's citation allowlist) | script | `verify_case` |
| precedent miner reading decision text | agent read | `get_decision_text` |
| privacy tiers, plausibility checks, collection policy | agent read | `get_corpus_file`, resources |
| entity resolver web search | agent, network | **not hosted** — stays a consent-gated client-side search; the Worker makes no outbound requests |
| `validate_session`, `assemble_package`, `verify_output` | scripts | **not hosted** — they need the session |

### 2.2 Tool definitions

Every tool: read-only, idempotent, categorical inputs validated against a
closed enum (anything else is a JSON-RPC invalid-params error, not a best
guess), and a `release` block in every result:
`{corpus_version, library_release, doha_release, file_sha256[]}` so a client
can write the deliverable footer the local `assemble_package.py` writes.
Every result that carries a maintainer-authored file carries its
`maintainer_verified` flag and, when false, `citable: false` with the same
sentence the local agents use.

**Reference and status**

- `get_release()` → release ids and approval receipt, counts computed from the
  shards (total / parsed / unique-case), the list of directive sections
  present (the hosted `sead_lookup.py --status`), verified and unverified file
  counts, rate limit, and the Mode 1b disclosure text. Intake stage 0 calls
  this first and relays what it says, as it relays `check_library.py` today.

**Directive text (the `sead_lookup.py` port)**

- `get_guideline_text(guidelines: [A–M])` → the named guideline sections plus
  Appendix A (adjudicative process), always; nothing else. A missing section
  is an error for the whole call ("quote nothing"), never a partial answer and
  never the full directive.
- `get_reporting_requirements(access: baseline | ts_q | not_applicable,
  include_data_elements: bool = true)` → SEAD 3 overview + all-covered
  section + the one additive section for the tier + Appendix A data elements.
  `not_applicable` returns the overview and all-covered sections only.
- `get_isl_section(table: 1 | 2 | 3 | 4)` and
  `get_isl_section(verifies: all-covered-individuals | adverse-information |
  top-secret-q | channels)` → the overview section plus the requested table
  section. The `verifies` form resolves through the ISL manifest's
  `source_of_record` entries, as `library_paths.isl_text` does.
- `get_cfr_section(section: "117.8")` → the §117.8 text (the enum has one
  value in phase 1, which is the point: it cannot be asked for anything else).

**Maintainer-authored files**

- `get_reporting_tables(population: industry | federal_civilian | military |
  applicant | in_process, access: baseline | ts_q | not_applicable,
  event_ids?: [enum])` → `authority-layers` resolved to the layers that apply,
  the applicable table entries (adds `top-secret-q` for `ts_q`), the channel
  family for that population from `channels.yaml`, `attribution_status`, and
  every file's verified flag. The matching of a narrative to an event id is
  the client's job; the server only filters by ids the client already chose.
- `list_event_types()` → every table entry id with its `event` description,
  `applies_to`, `reportable` value, `channel_ref`, `required_data_elements`
  and the event checklist that claims it (from `events/_INDEX.yaml`). This is
  the closed set `event_ids` draws from.
- `get_checklists(guidelines?: [A–M], event_ids?: [enum])` → the guideline
  checklists, the event checklists claiming those ids, `_UNIVERSAL` and
  `_COVERAGE`, plus an index of element ids with the files each appears in so
  the gap analyst can deduplicate by id. At least one of the two inputs is
  required.
- `get_form_map(form: sf86 | pvq | incident_report, sections?: [enum])` → the
  map file (with `populated`, `lookback`, `scope_notes`,
  `third_party_data_required`), `collection-policy`, `entity-capture`, and
  for `incident_report` also `diss-incident-types`. Section ids are the keys
  the map files define.
- `get_severity_ladder(guideline: A–M)` → that guideline's ladder (or its
  `fact_dimensions` for `ladder: false` guidelines) with `case_refs`.
- `get_document_evidence(guidelines: [A–M])` → the per-guideline document
  entries and `bare_claim_pattern`s.
- `court_lookup(state: [two-letter enum from state-courts.yaml], offense?:
  dui | owi | dwi | felony | misdemeanor)` → that state's record: court names,
  `unit_label`, lower courts, `dui_note`, custodian, `verified` flag and the
  `ask_first` sentence. **County is not an input** (it is a string the user
  typed); the client composes the nudge from `unit_label` and the court
  names, which is a template fill, not reasoning the server needs.
- `get_corpus_file(file: enum)` → one of the standalone files:
  `privacy-tiers`, `plausibility`, `collection-policy`, `entity-capture`,
  `diss-incident-types`, `incident-chronology`, `incident-profiles`,
  `coverage`, `pvq-preambles`, `events-index`, `adjudicative-readiness`
  (DCSA's adjudicatively-ready standard restated, added 2026-11-09) and
  `state-records-sources` (per-state custodians beside the court aid;
  `court_lookup` also returns that state's entries as `records_sources`) and
  `document-retrieval` (how each supporting document is requested or
  replaced). Also exposed as MCP resources
  (`adverse://corpus/<file>`) for clients that prefer them, as the Atlas does
  for its reference data.
- `get_corpus_bundle()` → every §1.2 and §1.3 file in one response (expected
  well under 2 MB). Exists so a privacy-maximising client can fetch the whole
  reference layer once, at intake, and reveal nothing about the matter in
  later calls. Rate-limited like every other call.

**Decisions (the `doha_retrieval.py` port, over the Atlas shards)**

- `find_decisions(guidelines: [A–M], limit: 1–12 = 6, include_pre_sead4: bool
  = false)` → decisions ranked by guideline overlap, post-SEAD 4 era first,
  outcomes alternated denied/approved exactly as `select()` does, exclusions
  from `doha-exclusions.json` applied. Each hit: `decision_id`, `case_no`,
  `level`, `outcome`, `guidelines`, `era`, `decision_date`, `source_url`
  (official DOHA PDF), `parts` (how many passages `get_decision_text` can
  page through). **No counts by outcome, no rates, no "similar cases"** — the
  Atlas offers statistics for people studying the system; this tool serves a
  person preparing a disclosure, and its non-goals forbid anything that reads
  as odds.
- `verify_case(case_number: /^\d{2}-\d{4,5}$/)` → whether the case exists in
  the shards and which decisions sit under it. A case number is an identifier
  from the server's own output or a published decision, not narrative; the
  pattern check rejects anything else. This is what a client-side verifier
  uses when the library is not on disk.
- `get_decision_text(decision_id: /^\d{2}-\d{4,5}\.[ah]\d$/, part_from: int =
  1, part_to: int = part_from + 9)` → the passages for that decision in order,
  capped at 10 parts per call, with page numbers and the decision's
  `source_url`. The precedent miner's "read the top files (max 5)" becomes at
  most five of these calls.

**Deliberately absent**

- Free-text search over decisions. The Atlas has `search_decision_text` at
  `/atlas/mcp`; a client that wants it can use that endpoint knowingly. On
  this endpoint a search string is the one input that could carry the user's
  own words, so it does not exist here.
- Anything that accepts, scores, drafts, or verifies narrative. See §3.3.
- Any write. There is no binding the Worker can write to.

### 2.3 Resources and prompts summary

Resources: `adverse://release` (the manifest), `adverse://corpus/<file>` for
the §1.3 standalone files, `adverse://government/<directive>/<section>` for
§1.2 sections (so a client can also read them by URI). Prompts: §3.

## 3. Which agent behaviour becomes MCP prompts

MCP `prompts/list` serves text to the client; the client decides whether to
run it. That is exactly the shape the agents already have: stateless
specialist prompts the conductor invokes one turn at a time, on any platform.
So the server publishes the agent files **verbatim from the release commit**,
each with a short hosted-mode preamble, and the client runs them.

### 3.1 Prompts served

| Prompt | Source file | Hosted-mode preamble adds |
|---|---|---|
| `conductor` | `agents/conductor.md` | the Mode 1b Stage 1 disclosure; the tool-for-script table below; "the gates still run on your machine" (§3.3) |
| `intake` | `agents/core/intake.md` | stage 0 calls `get_release` instead of the two check scripts; what to say when the client cannot run scripts |
| `triage` | `agents/core/triage.md` | none |
| `requirements-advisor` | `agents/core/requirements-advisor.md` | `get_reporting_tables` + `list_event_types` for the corpus reads; `get_reporting_requirements` / `get_isl_section` / `get_cfr_section` for the lookups |
| `classifier` | `agents/core/classifier.md` | `get_guideline_text` for the lookup |
| `incident-developer` | `agents/core/incident-developer.md` | `get_corpus_file(incident-chronology \| incident-profiles)` |
| `gap-analyst` | `agents/core/gap-analyst.md` | `get_checklists`, `get_form_map` |
| `interviewer` | `agents/core/interviewer.md` | `get_severity_ladder` |
| `thread-detector` | `agents/core/thread-detector.md` | none |
| `narrative-writer` | `agents/core/narrative-writer.md` | `get_guideline_text` when quoting |
| `precedent-miner` | `agents/optional/precedent-miner.md` | `find_decisions` + `get_decision_text`; the retired `corpus/doha/index.json` step is replaced by the tool |
| `answer-integrator`, `consistency-checker`, `candor-reviewer` | `agents/optional/…` | `get_corpus_file(plausibility)` for the checker; otherwise none |
| `documents-advisor` | `agents/optional/documents-advisor.md` | `get_document_evidence`, `court_lookup` |
| `entity-resolver` | `agents/optional/entity-resolver.md` | a note that the hosted server does **not** search; the agent's own consent-gated client-side search is unchanged |

Prompt arguments are categorical too (for example `population` on
`requirements-advisor`) and only select preamble text; no argument is
interpolated into the agent body. A prompt never receives the session.

The script-to-tool table, included once in the `conductor` preamble:

```
python scripts/check_corpus.py / check_library.py      → get_release
python scripts/sead_lookup.py --guidelines G,J          → get_guideline_text(["G","J"])
python scripts/sead_lookup.py --reporting --access ts_q → get_reporting_requirements("ts_q")
python scripts/sead_lookup.py --isl --isl-tables 4      → get_isl_section(table=4)
python scripts/sead_lookup.py --isl --verifies <table>  → get_isl_section(verifies=<table>)
python scripts/doha_retrieval.py --guidelines G,J       → find_decisions(["G","J"])
python scripts/doha_retrieval.py --verify-case 24-01234 → verify_case("24-01234")
python scripts/court_lookup.py --state IA --offense owi → court_lookup("IA","owi")
```

### 3.2 What stays in the client, by design

- **State.** `output/session.json`, the stage log, the stamped narrative, the
  privacy tier, Person-N mapping — all of it. The server has no session id,
  issues none, and ignores `mcp-session-id` if a client sends one.
- **Judgement.** Reportability, classification, gap analysis, threads,
  drafting, candor review. These are the agents, and the agents run where the
  prompts are rendered: in the client.
- **The deterministic gates.** `validate_session.py`, `assemble_package.py`,
  `verify_output.py`. They read the session, so they cannot be hosted without
  becoming Mode 2. In Claude Code, Codex, Cursor and similar clients they run
  as today. The one new capability they gain is that `verify_output.py` can
  check citations through `verify_case` when no library is on disk (phase 2,
  decision D3).

### 3.3 The honest limitation

A client with no shell — a Claude.ai custom connector, a chat window — can
run the prompts and the tools but **cannot run the gates**. For such a client
the package is unverified, and the `conductor` preamble says so in the user's
first interaction and again at handoff: "I could not run the verification
script here. Before you use this, run it yourself from a checkout of the
tool, or treat every citation as unchecked." Offering a hosted
`verify_package` that receives the package would solve this and would also be
the first tool to receive the narrative. Phase 1 does not do it; decision D3
asks the owner whether phase 2 should, and under what disclosure.

## 4. Privacy posture — copied from the Atlas Worker, then tightened

Taken from `doha-guidelines-nexus/mcp/wrangler.jsonc` and `worker.js` as
deployed:

| Control | Atlas (`doha-atlas-mcp`) | Adverse (`adverse-information-assistant`) |
|---|---|---|
| Request logs | `observability.enabled: false` | same |
| `console.*` in handlers | none on the request path | none; a test greps the bundle for `console.` |
| Rate limit | `ratelimits` binding, 60/min keyed on `cf-connecting-ip`, JSON-RPC `-32000` + HTTP 429 + `retry-after: 60` | same binding shape, own namespace id, same error |
| Sessions | stateless Streamable HTTP; `mcp-session-id` allowed in CORS headers, not issued, not stored | same, and the server never echoes the header |
| Storage bindings | assets (read), D1 ×3 | assets (read), D1 ×3; **no KV, no Durable Objects, no R2 write, no queues** |
| D1 statements | prepared, parameterised, read-only SQL | same; only `SELECT`, with the statement list enumerated in one module so review is a diff |
| Outbound fetch | none except `env.ASSETS` | same; a test asserts no `fetch(` to a non-asset URL exists in the bundle |
| Batch cap | 20 JSON-RPC messages per POST | same |
| Caching | guide page `public, max-age=3600` | guide page the same; **every tool response `cache-control: no-store`** |
| Cookies, analytics on the guide page | none | none |
| CORS | `access-control-allow-origin: *` | same |
| `workers_dev`, `preview_urls` | both `false` (the only address is the route) | same |

Tightened beyond the Atlas because the inputs are about one person's matter:

- **No input echoes.** Error messages name the parameter, never its value
  (the Atlas's text-search error quotes the query; that pattern is excluded).
- **No free text** anywhere in the schema (§0), so there is nothing a log
  *could* have captured even if one existed.
- **The bundle tool** (§2.2) exists so a client can make the server blind to
  the matter entirely.

What the design cannot promise, and the Stage 1 text must not imply: that
Cloudflare the platform keeps nothing. Edge request counts, the rate limiter's
counters (which expire with the window) and zone analytics are outside the
Worker. The promise is scoped to "this server keeps no logs and no state",
which is checkable from the Worker's configuration and code.

## 5. Route, website, redeploy

### 5.1 Route and Worker

- Worker name: `adverse-information-assistant`, connector label "Adverse
  Information Assistant" (D1, decided 2026-10-30). Route: `{ "pattern": "fsotools.ai/adverse/mcp*", "zone_name":
  "fsotools.ai" }`, beside the Atlas's `fsotools.ai/atlas/mcp*`. A future
  Pages page at `/adverse/` does not collide: the route pattern claims only
  `/adverse/mcp` and below.
- `GET /adverse/mcp` with `Accept: text/html` → a guide page in the Worker,
  modelled on the Atlas's: the address, the Claude.ai connector steps,
  `claude mcp add --transport http adverse-information-assistant https://fsotools.ai/adverse/mcp`,
  the `mcp-remote` bridge for stdio-only clients, the tool and prompt lists,
  the Mode 1b statement, and the disclaimer block from `DISCLAIMER.md`
  verbatim. `POST` → MCP Streamable HTTP.
- Code lives in this repo under `mcp/` (`wrangler.jsonc`, `worker.js`,
  `server.js`, `http.js`, `release/` as built), with `npm run
  mcp:worker:dev` and `mcp:worker:deploy` mirroring the Atlas's scripts.
  `tests/run_tests.py` gains a guard that nothing under `agents/` or
  `scripts/` references `mcp/` — the hosted server is a convenience the way
  `.claude/` is, never a dependency, and the local tool must keep working
  with no network at all.

### 5.2 How the website presents it

The site repo (`fsotools-website`) follows its `/atlas/mcp` pattern exactly,
and only that:

- `site/robots.txt`: `Disallow: /adverse/mcp` in the one user-agent group,
  with a comment like the Atlas one (an endpoint for assistants, not a page).
- `test/build.test.js`: add `/adverse/mcp` to `WORKER_PATHS`, and extend the
  robots tests to assert `/adverse/mcp`, `/adverse/mcp/` and
  `/adverse/mcp?x=1` are blocked while the linking page stays allowed.
- The connect presentation lives on the site's **MCP directory page**, which
  lists every fsotools.ai connector with its status (D4, decided 2026-10-30;
  being built in `fsotools-website` on branch `claude/mcp-directory-page`).
  This connector appears there as *planned* until the Worker is deployed,
  then gains the same table shape as `site/atlas/index.html` lines 137–140:
  server address, Claude.ai steps, the `claude mcp add` line, and a "what it
  is" row that says: a read-only reference endpoint over the disclosure
  corpus, categorical queries only, no narrative accepted, no session kept,
  no logs, nothing predicted. A dedicated `/adverse/` product page is not
  required for phase 1.
- `llms.txt` untouched, as for the Atlas (its published-paths test would need
  an allow-list change).
- No new pages, no analytics, no CSP change. Product work stays in this
  repo; the site links.

### 5.3 The redeploy hook for the release-sync agent

A sibling session is building a release-sync agent at the workspace root that
redeploys MCP Workers when the library publishes a release. This repo gives
it one documented command and a contract (phase 2 implements it; the name is
fixed now so the agent can be written against it):

```
python scripts/hosted_release.py --library "<library root>" [--doha-shards s1,s2,s3] [--deploy] [--dry-run]
```

- Reads the approved release at `<library root>` through the same contract
  `release_contract.py` applies; refuses an unapproved or inconsistent one
  (exit 2) and prints why.
- Rebuilds `mcp/release/` from that release and the current checkout (§1.4),
  verifying every hash; refuses on any mismatch or a failing
  `validate_corpus.py` / `tests/run_tests.py` (exit 2).
- Rewrites `RELEASE_ID`, `CORPUS_VERSION` and `REPO_COMMIT` in
  `mcp/wrangler.jsonc` `vars`. *Implementation note (2026-11-02, from the
  phase 2 review): the ids are carried in `mcp/release/manifest.json` and
  passed as deploy-time `--var`s instead, so `wrangler.jsonc` stays unchanged
  and the checkout stays clean after a build.* **Does not** rebind the D1 shards on its own:
  those are built and uploaded by `doha-decision-search`, which names each
  database for its release (`doha-text-<release>-s<N>`); the agent passes
  `--doha-shards <name-s1>,<name-s2>,<name-s3>` after that upload, and the
  script rewrites the three bindings. Without the flag the existing bindings
  stay, and the script prints that decision text may be older than the
  reference text.
- With `--deploy`, runs `npx wrangler deploy --config mcp/wrangler.jsonc`
  and then checks the live `get_release` reports the new ids (exit 3 if it
  does not). Without `--deploy` it stops after the build and prints the
  diff of `vars`.
- Exit 0 means deployed, or nothing changed (idempotent). It never fetches
  from the internet, never flips a verified flag, never commits.

Order of operations on a library release, for the agent: decision-search
uploads shards → Atlas redeploys (`doha-guidelines-nexus`: `npm run
mcp:worker:deploy`) → this repo: `hosted_release.py --library … --doha-shards
… --deploy`. The reference text can be redeployed alone (no `--doha-shards`)
when only a directive or the maintainer corpus changed.

## 6. Corpus population checklist — the long pole

Everything below is **manual, human work**; the tool and the build fetch
nothing. Each row names the verification step that lets the file become
citable. Order follows `corpus/BUILDING.md`.

### 6.1 Government text — already verified by the Custodian's release

These need no maintainer action for the hosted server beyond what the
Archivist already does. The verification is the release approval and the
hash chain; the build re-checks it.

| Item | Source | Verification step | Status today |
|---|---|---|---|
| SEAD 4, 17 sections | library release, split by the Archivist | release approved; `manifest.json` hashes match; build records SHA-256 | present in `doha-v9-exceptions-20261003` (current local pointer) |
| SEAD 3, 6 sections | same | same | present |
| ISL 2021-02 v2 (May 2024), 5 sections | same | same; `source_of_record` entries present for all four corpus tables | present |
| 32 CFR Part 117 (2025-07-01 eCFR text) | library, unsplit | same; **§117.8 extraction** needs a section split or a build-time slice whose boundaries a human confirms once against ecfr.gov | present unsplit; split is decision D5 |
| DOHA decision text, all shards | D1 shards from release `doha-robot-lf-20260929` | every text hash checked by `doha-decision-search`'s build against the release manifest | live |
| `doha-exclusions.json` | derived from the library manifest's `answer_eligible: false` rows | build-time derivation, logged with the count; no human step | new |

### 6.2 Maintainer-authored files — each needs a human and provenance

Flipping `maintainer_verified: true` requires `source_url`, `source_sha256`
(`scripts/hash_source.py` on the exact official file read) and
`verified_date`, or `validate_corpus.py` errors. "Verify" below means that.

| Stage | File(s) | What verifying it means | Unlocks |
|---|---|---|---|
| 1 | `reporting/tables/adverse-information.yaml` | line-by-line against ISL 2021-02 Table 1 (PDF); every entry id, `reportable`, `channel_ref`, `required_data_elements` | `yes` answers for industry on adverse items |
| 1 | `reporting/tables/all-covered-individuals.yaml` | against ISL Tables 2 and 4; note `reportable: "no"` entries never become a "no" (polarity rule) | `yes` for all-covered events |
| 1 | `reporting/tables/top-secret-q.yaml` | against ISL Table 3 | `yes` at Top Secret / Q |
| 1 | `reporting/tables/channels.yaml` | industry channels against the ISL; federal/military entries against SEAD 3 §responsibilities (no agency system names); **applicant channels** against official guidance or left unverified with the degrade text | channel statements instead of "confirm with your office" |
| 1 | `reporting/authority-layers.yaml` | the attribution split: every table entry gets `authority: sead-3 \| isl-2021-02 \| both`, decided from the SEAD 3 text; then `attribution_status: complete` | federal and military users stop getting `consult_fso` on every match |
| 2 | `checklists/guideline-{A..M}.yaml` | FSO review of each element against the SEAD 4 section it cites (paragraph numbers), `maps_to` against the form maps; `severity_default` reviewed | guideline checklists citable; `why` text quotable |
| 2 | `checklists/_UNIVERSAL.yaml`, `_COVERAGE.yaml` | FSO review; SEAD 3 / ISL citations in `sources` resolved | universal elements citable |
| 2 | `checklists/events/*.yaml` (13), `_INDEX.yaml` | each `event_ids` entry re-read against the table entry it claims; `report_before_package` and pre-approval flags against the ISL text | event checklists citable |
| 2 | `checklists/_INCIDENT_CHRONOLOGY.yaml`, `_INCIDENT_PROFILES.yaml` | FSO review (maintainer-authored method, no external source) | incident development citable |
| 2 | `checklists/_SEVERITY_LADDERS.yaml`, `_DOCUMENT_EVIDENCE.yaml` | every `case_refs` / case citation resolved with `verify_case` (hosted) or `doha_retrieval.py --verify-case` (local); method statement kept; FSO review of tier wording | depth scaling and document advice citable |
| 3 | `forms/sf86-map.yaml` | every section's field list against the current SF-86 / eApp; item numbers only where confirmed (Sections 22, 23, 26 first) | field-level completeness checking |
| 3 | `forms/pvq-map.yaml` | populate from the PVQ (Final, Sept 2023); set `populated: true`; lookbacks and scope notes | PVQ-standard collection |
| 3 | `forms/collection-policy.yaml`, `entity-capture.yaml`, `incident-report-map.yaml` | against both forms' instructions | crosswalk and entity capture citable |
| 3 | `forms/diss-incident-types.yaml` | against the live DISS incident-entry screen (owner has a 2026-08-30 screenshot) | DISS labels asserted, not suggested |
| 3 | `forms/pvq-preambles.md` | against the PVQ | preamble text quotable |
| 4 | `courts/state-courts.yaml` | per state, against the state judiciary's official site (`source_url`, `verified_date`; `--check-links` for rot) | nudges asserted instead of offered as guesses, one state at a time |
| 4 | `checks/plausibility.yaml`, `privacy-tiers.yaml` | FSO review; no external source | — (policy files; already load-bearing unverified) |

Stage 1 is the whole value of the hosted server for most users: until the
tables are verified, every reportability answer is `consult_fso` with the
unverified note, hosted or not. Budget it first.

### 6.3 Gates the checklist runs through

1. `python scripts/validate_corpus.py` clean on the checkout.
2. `python tests/run_tests.py` passing (includes the "corpus stays a
   skeleton" guard, which this work must not trip: verified **analysis**
   files are fine in the repo; Government **text** is not).
3. Bump `corpus/VERSION` on any change; the deliverable footer and
   `get_release` both report it.
4. Rebuild and redeploy with `hosted_release.py` (§5.3). The release manifest
   turns the file's `verified: true` on; the Worker starts reporting
   `citable: true` for it the same minute.

## 7. Owner decisions

Recorded 2026-10-30 from the owner's answers. "Open" items keep the stated
default until the owner overrules it.

- **D1 — Worker name and connector label. Decided.** Worker
  `adverse-information-assistant`, connector label "Adverse Information
  Assistant", and the same short name in the `claude mcp add` line. The
  owner's words were "adverse information assistance"; the product name is
  used here and the owner can correct the spelling.
- **D2 — Ship before Stage 1 of §6.2 is done? Open.** The owner asked why
  the reporting tables are unverified. Answer: `corpus/BUILDING.md` makes
  verification a human act. Each table was drafted from ISL 2021-02 and
  ships `maintainer_verified: false`; flipping it requires a line-by-line
  read of every row against the ISL, with the ISL PDF's SHA-256 and the
  check date recorded, or `validate_corpus.py` errors. That read has not been
  done, and the corpus is still `0.1.0-scaffold`. Everything needed is on
  disk: the ISL text, split by table, in the library's robot-readable
  directory (`sead_lookup.py --isl --verifies <table>` names the exact
  files), and the PDF in the human-readable directory for the hash. Until it
  is done the tool returns `consult_fso` rather than asserting that anything
  is reportable, by design, and the hosted server inherits that behaviour
  unchanged. Default: build now, link from the site only after Stage 1.
- **D3 — Clients that cannot run the gates. Decided.** The connector runs
  inside the user's own harness; the server stores nothing and never
  receives a package, a narrative or any session state. A hosted
  `verify_package` tool is ruled out permanently, not deferred. A client
  with no shell is told plainly, by the served prompts, that its package is
  unverified, and is pointed at the local tool. A later verifier that runs
  in the user's own browser is still their harness and stays permitted as
  phase 2 work.
- **D4 — Where the site presents it. Decided.** An MCP directory page on
  fsotools.ai listing every connector with its status, instead of a product
  page per connector. This connector is listed as planned until deployed.
  See §5.2.
- **D5 — 32 CFR Part 117 split. Open; default is the Archivist split.** The
  owner's reply raised a different question, whether the DCSA Library
  release itself should be hosted on Cloudflare. That does not change this
  decision, which is about which text is served, not where the library
  lives. Default until overruled: the Archivist splits the Part by section,
  which also serves the Question Bot.
- **D6 — Rate limit and bundle size. Decided.** One shared 60/min limit, as
  the Atlas. No separate cap on the bundle tool; revisit only if the first
  build's measured size or observed traffic shows a problem.
- **D7 — Exclusions as an asset or a shard column. Decided.** The derived
  `doha-exclusions.json` ships with the release now. The owner will ask the
  decision-search build to carry `answer_eligible` into the shard schema at
  the next shard rebuild, after which the asset is dropped.
