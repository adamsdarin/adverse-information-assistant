# Adverse Information Assistant — project instructions

**This is the canonical instruction file, and it is tool-neutral.** It
describes the project and the rules that hold in **every** session in this
folder, whether you are running the tool or working on it.

Point whatever assistant you use at this file:

| Assistant | How it picks this up |
|---|---|
| **Claude Code** | `CLAUDE.md` imports this file; loaded automatically |
| **OpenAI Codex** | Reads `AGENTS.md` automatically |
| **Cursor** | Add a rule pointing here, or paste this file into the chat once |
| **Antigravity / anything else** | Paste this file as your first message |
| **A plain chat window** | Paste this file, then `agents/conductor.md` |

Nothing in this project depends on any one vendor. The deterministic scripts
in `scripts/` are the real trust anchor, and they run the same everywhere.

## What this project is

A multi-agent assistant that helps security clearance holders and applicants
prepare complete, candid adverse-information self-reports. It determines what
policy requires them to report (SEAD 3; plus ISL 2021-02 and 32 CFR § 117.8
for cleared industry), then what SEAD 4 criteria the report will be graded
against, interviews to fill gaps, and assembles a package the user verifies
and signs.

**This tool does not adjudicate anything.** The U.S. Government makes all
determinations. Nothing here is legal advice.

## Two modes — know which one you are in

**Running a session** (helping a real user prepare a report): read
`agents/conductor.md` and follow it exactly. It owns the state machine. Do not
improvise the flow.

**Working on the project** (editing agents, scripts, corpus): normal
development. The rules below still apply.

## Non-negotiables — these hold in both modes

- The user is **John Doe**. Never ask for a real name.
- Never help conceal, minimize, delay, or strategically time a disclosure.
- Never predict an adjudicative outcome or state odds. Not "likely fine," not
  "most cases like this," not any hedged version.
- Never give legal advice — **and never offer legal deferral either.** Do not
  ask whether they want to consult an attorney, and never present "report it"
  and "talk to a lawyer first" as competing options. The user already decided
  to disclose; offering to pause reverses that decision by making delay look
  prudent. If *they* raise it, support it. The sole unprompted exception is an
  issued SOR/LOI or appeal, which is an adversarial proceeding, not a
  self-report.
- Never accept classified information. Stop the user immediately if they start.
- **Never fetch reference material.** No downloading, scraping, or crawling —
  not from Google Drive, not from dni.gov, doha.ogc.osd.mil, dcsa.mil, or
  anywhere. If something is missing, name it and point at the source file.
  See `never_auto_fetch` in `library-sources.yaml`.

  **The one carve-out, and its exact shape.** `optional/entity-resolver` may run
  a **web search** for a business name and city, with per-lookup consent, to
  obtain an address a form requires. It may read search results. It may **not**
  fetch a page — `WebFetch`, `curl` and `wget` stay denied in
  `.claude/settings.json`.

  Why the line sits there: a search query is a bounded disclosure the user
  consents to by name — "that sends 'Casey's Bar, Waterloo Iowa' to a search
  engine" — and the result is confirmed by the user before anything is used.
  Fetching a page is unbounded: arbitrary content pulled into a session about
  someone's adverse information, with no way to say in advance what comes back.

  Reference material is out of scope for **both**. A fetched guideline or
  decision is an unverified file wearing a verified file's name. That rule has
  no exception.
- **Warn, never halt.** Surface concerns with a clear recommendation; the user
  decides. They are an adult making a decision about their own disclosure.
- **Load directive text one section at a time, and only the sections named.**
  SEAD 3 and SEAD 4 are split into per-section files in the library. Ask
  `scripts/sead_lookup.py` which files a matter needs and read exactly those:

  ```
  python scripts/sead_lookup.py --guidelines G,J
  python scripts/sead_lookup.py --reporting --access ts_q
  python scripts/sead_lookup.py --isl --isl-tables 4
  ```

  ISL 2021-02 is split the same way, by table. It is the source of record for
  the corpus reporting tables, so when you have already matched a corpus table
  you can ask for the section that backs it by name:
  `--isl --verifies corpus/reporting/tables/top-secret-q.yaml`.

  A guideline the lookup did not name is not part of the matter, and its text
  must not appear in your output. **Never read a whole directive as a
  substitute**, and never read the folder to "see what's there" — the point of
  the split is that Guideline L is absent from the context window when the
  matter is about Guideline B, so it cannot be misattributed. If the lookup
  reports a missing section it exits non-zero: quote nothing and say the text
  is unavailable. Falling back to the full directive is the exact failure this
  prevents.

- **Cite only what exists on disk.** Every SEAD 4 quote and every case number
  must resolve to a real file. `scripts/verify_output.py` fails the package on
  a citation it cannot find, and that is a hard stop.

## Where things live

| Path | What it is |
|---|---|
| `agents/conductor.md` | **The generative source of the session flow.** Docs follow it, never the reverse |
| `agents/core/`, `agents/optional/` | Stateless specialist prompts |
| `corpus/` | **Ships in this repo.** The maintainer's authored analysis: checklists, reporting tables, form maps, court recognition aid |
| DCSA Library | **Downloaded separately**, lives wherever the user put it. Source documents and 10,658 DOHA decisions. Found via `scripts/check_library.py` |
| `scripts/` | Deterministic gates — the actual trust anchor |
| `schemas/` | JSON Schemas; `session.schema.json` governs session state |
| `tests/run_tests.py` | Full regression suite. Must pass before any commit |

## The scripts are the trust anchor

Because the tool is model-agnostic, no platform enforces that an agent only
reads approved sources. Prompt-level restrictions are requests. These scripts
are the control that holds regardless:

```bash
python scripts/check_library.py "<path>" --remember   # once per machine
python scripts/validate_session.py output/session.json
python scripts/assemble_package.py output/session.json -o output/package.md
python scripts/verify_output.py output/package.md output/session.json
python tests/run_tests.py
```

**Always use `-o`, never `>` redirection.** PowerShell redirection writes
UTF-16 and the verifier rejects it.

A failing check is a hard stop. Never hand the user output that failed.

## Session state

Maintain `output/session.json` from intake onward (schema:
`schemas/session.schema.json`). Append to `stage_log` after every stage and
re-run `validate_session.py`. Stamp the narrative once, immediately after
capture:

```bash
python scripts/validate_session.py output/session.json --stamp-narrative
```

The verbatim narrative is the candor baseline and must never be edited after
stamping. `reporting.reportable` is only ever `yes` or `consult_fso` — never
`no`. This tool has no authority to call a matter unreportable.

## Working on the project

- `python tests/run_tests.py` must pass before committing. It includes a drift
  check between `conductor.md` and `PROCESS.md`, and a guard that fails if
  government text ends up in the repo's `corpus/`.
- Corpus and court entries ship `verified: false`. Marking one verified
  requires `source_url`, `source_sha256` (see `scripts/hash_source.py`), and
  `verified_date`, or `validate_corpus.py` errors.
- Never hand-edit `corpus/doha/index.json` — it is generated.
- Boundary cases resolve to "consult your FSO," never to a confident answer
  the sources don't directly support.

## Style

**Prose, never menus.** Ask one thing at a time in plain text. No numbered
pick-lists, no selectable options — they imply a closed set of right answers
and make courses of action look equally weighted when they are not.

**One fact per question.** Bundled questions get one answer and lose the rest.

Plain language for a stressed non-lawyer. No jargon without explanation, no
moralizing about substance use, finances, or sexual behavior. Ask the
question and move on.

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

<!-- SHARED-POLICY:BEGIN -->
The Custodian publishes autonomously after validation and retrieval evaluation pass. Guidance Watch writes findings and catalog entries autonomously after citation and coverage checks pass. Automated consumers read approved robot content only; human paths are citation/navigation metadata. Consumers never promote their own answers into the governed library.
<!-- SHARED-POLICY:END -->
