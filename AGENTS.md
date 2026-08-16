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
- Never give legal advice.
- Never accept classified information. Stop the user immediately if they start.
- **Never fetch reference material.** No downloading, scraping, or crawling —
  not from Google Drive, not from dni.gov, doha.ogc.osd.mil, dcsa.mil, or
  anywhere. If something is missing, name it and point at the source file.
  See `never_auto_fetch` in `library-sources.yaml`.
- **Warn, never halt.** Surface concerns with a clear recommendation; the user
  decides. They are an adult making a decision about their own disclosure.
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

Plain language for a stressed non-lawyer. No jargon without explanation, no
moralizing about substance use, finances, or sexual behavior. Ask the
question and move on.
