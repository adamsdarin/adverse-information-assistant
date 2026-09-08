# Using This Tool

## Local runner commands

`scripts/adverse.py` provides the Phase 1–2 product boundary:

- `start` creates a new validated checkpoint and refuses to overwrite an
  existing session unless the exact target is explicitly forced.
- `resume` and `status` show compact progress without printing narrative text.
- `answer` records one intake fact and validates immediately.
- `validate`, `assemble`, and `verify` invoke the existing deterministic gates.
- `mcp` starts an optional narrow stdio MCP server; no arbitrary file tool is
  exposed.

Run `python tests/run_product_tests.py` to exercise the product shell. The
existing `python tests/run_tests.py` remains the full deterministic safety
suite.

Works with any AI coding assistant that can read files in a folder and run
scripts. No account, no server, no signup — you clone the folder and point
your assistant at it.

> **Don't have an AI assistant set up yet?** Start with
> [`GET-STARTED.md`](GET-STARTED.md) instead — it covers picking and
> installing one, from zero. This page assumes you already have one.

> ⚠️ Read [`DISCLAIMER.md`](DISCLAIMER.md) first. This is not affiliated with
> DCSA, DOHA, ODNI, or any U.S. Government agency, and the Government makes
> all adjudicative determinations. Use at your own risk.

---

## Get a copy

**With GitHub Desktop** — on the repository page click **Code → Open with
GitHub Desktop**, pick a folder, click Clone.

**With the command line** —

```bash
git clone https://github.com/<owner>/adverse-information-assistant
cd adverse-information-assistant
```

**Without either** — click **Code → Download ZIP** and unzip it.

Then install the one dependency the checking scripts need:

```bash
pip install pyyaml
```

---

## Populate the corpus first

**The tool ships deliberately empty of official text.** No SEAD 3, no SEAD 4
guideline language, no DOHA decisions. That is not an oversight — text
generated from a model's memory is exactly the failure this design exists to
prevent, so the corpus contains templates a human fills from official sources.

Until you populate it, agents treat corpus files as uncitable and reportability
degrades to "ask your security office" rather than guessing. The tool is still
useful in that state; it just won't cite anything.

See [`corpus/README.md`](corpus/README.md). Then:

```bash
python scripts/build_index.py
python scripts/validate_corpus.py
```

---

## Run it

Open the folder in your assistant. If it reads `AGENTS.md` automatically
(Codex) or imports it (Claude Code), the rules are already loaded and you can
just say `/report` or "start a reporting session." Otherwise paste
`AGENTS.md` first, then this:

```
Read agents/conductor.md and run the session it describes, exactly as written.
Follow the stage order. Use the agent prompt files in agents/core/ and
agents/optional/ as the instructions for each step. Only cite things that
exist as files in corpus/. Before showing me any final package, run
scripts/verify_output.py and do not give me output that fails it. When we
finish, give me the exact verify_output.py command to run myself and the
SHA-256 it printed, so I can confirm the file I have is the file that passed.
```

That's the whole invocation. The conductor drives everything else.

### Platform notes

| Assistant | How |
|---|---|
| **Claude Code / Cowork** | `cd` into the folder, start Claude, paste the prompt. Subagents map directly onto the roster in `conductor.md`. |
| **OpenAI Codex** | Open the folder as your working directory, paste the prompt. |
| **Cursor** | Open the folder as a project. Paste the prompt in chat with the folder in context. |
| **Google Antigravity** | Open the folder as the workspace, paste the prompt. |
| **A plain chat model** | Workable but degraded: paste `agents/conductor.md` as your first message, then paste each agent file when the conductor calls for it. You will have to run the verification scripts yourself. |

Nothing here depends on a specific vendor's subagent feature. If your assistant
has no subagent mechanism, run each agent as a separate turn using its prompt
file as the instructions.

---

## What a session looks like

1. It calls you **John Doe** and never asks your real name.
2. It tells you where your text is going, then asks what **privacy level** you
   want — high (nobody named), medium (names only), or low (contact details
   too). High is the default. It never collects a Social Security number or
   date of birth at any level.
3. It asks whether you're an applicant or a clearance holder, industry or
   federal, and your access level.
4. It asks, in your own words, what you feel you have to report.
5. It works out **what policy requires you to report** — and tells you if the
   clock is already running, so you contact your security office today rather
   than after you finish.
6. It works out **what criteria the report will be graded against**.
7. It asks a lot of questions. Some are required by the form and can't be
   skipped; the rest you can decline.
8. **It follows threads.** Mention court-ordered therapy while describing an
   OWI and it will ask whether you want to cover the therapy too — because
   that's separately reportable. It asks before widening, and a "no" is
   final.
9. It checks your account for contradictions and tells you which documents to
   go get.
10. It writes a first-person statement in your voice, assembles the package,
    and runs deterministic checks on it before you see it.
11. It tells you to put your real name in and verify every fact, because you
    sign it.

---

## What it will not do

- Predict or improve your odds. Adjudication is the Government's alone.
- Help you conceal, minimize, or time a disclosure.
- Give legal advice.
- Accept classified information.
- Look up a person on the internet. It will look up a *business* address, but
  only after asking, and only inserts what you confirm.

---

## Before you submit anything it produces

Read it yourself, all of it. The automated checks catch fabricated citations,
prohibited language, and structured personal data. They **cannot** catch a
sentence that quietly understates what happened. You are the last check, and
you're the one signing it.
