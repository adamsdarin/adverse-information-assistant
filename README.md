# Adverse Information Assistant

## Local product runner (Phase 1–2 preview)

The repository includes a small local product shell over the existing workflow
and deterministic gates. It does not replace `agents/conductor.md` or the
specialist agents.

```powershell
python scripts/adverse.py --session output/session.json start
python scripts/adverse.py --session output/session.json resume
python scripts/adverse.py --session output/session.json answer "industry"
python scripts/adverse.py --session output/session.json status
python scripts/adverse.py --session output/session.json validate
```

These commands handle safe local intake and checkpointing. Your own assistant
continues the specialist workflow against the same validated state — see
[`AGENTS.md`](AGENTS.md). The optional `mcp` command exposes a narrow allowlist
of status, intake, validation, assembly, and verification tools when the MCP
Python SDK is installed; it never exposes unrestricted filesystem access.

The working session is plaintext and unencrypted. Never enter classified
information, a Social Security number, or a date of birth, and delete the
working file after submission.

A multi-agent assistant that helps security clearance holders and applicants
prepare **complete, candid adverse-information self-reports** for their
security office — with the goal of first-time-right submissions that minimize
back-and-forth with federal agencies.

**Model-agnostic.** Runs in Claude Code/Cowork, OpenAI Codex, Cursor, Google
Antigravity, or any assistant that can read a folder and run a script. Clone
it and point your assistant at it — see [`USAGE.md`](USAGE.md).

> ⚠️ **Not affiliated with, endorsed by, or reviewed by DCSA, DOHA, ODNI, or any
> agency of the U.S. Government.** The Government makes all adjudicative
> determinations. This tool ensures nothing. **Use at your own risk.**
> Read [`DISCLAIMER.md`](DISCLAIMER.md) before use — all of it.

## What it does

1. Greets you pseudonymously ("for the purposes of this conversation, your name
   is **John Doe**") — it never asks for your real name.
2. Asks whether you're completing the **SF-86 (eApp)** or the **PVQ**, or
   self-reporting as a current clearance holder, and (for cleared industry)
   whether your access is Secret, Top Secret, Q, or not applicable. Internally,
   Secret maps to the baseline reporting table and Top Secret/Q share the
   additional-access table.
3. Listens to what you feel you have to report, in your own words.
4. Determines **what policy requires you to report** — the threshold question.
   **SEAD 3** binds every covered individual; for cleared industry, **DCSA ISL
   2021-02** and **32 CFR § 117.8** layer on top. If it's reportable it tells
   you *immediately*, because the clock starts at the event, not when you
   finish writing. It never tells you something isn't reportable — only "yes"
   or "check with your security office" — and it reminds you the list is a
   floor, not a ceiling.
5. Determines **what criteria the report will be graded against** — the
   **SEAD 4** adjudicative guidelines. What adjudicators will look at, never
   a verdict.
6. Retrieves relevant **published DOHA decisions** from the DCSA Library — a
   separate download holding 10,658 decisions. It can only cite a case that
   exists in that library, and every citation is checked before delivery.
7. Compares your account against per-guideline checklists and the form's
   required data elements, then asks targeted questions to fill the gaps —
   including what controls failed last time and what your intent is going
   forward, which is what adjudicators are actually assessing.
8. **Follows threads.** Matters rarely arrive alone: an OWI mentions
   court-ordered therapy, the therapy mentions an assault, the assault
   mentions cocaine. Each is separately reportable. The tool notices, asks
   whether you want to cover it too, and treats an accepted thread as a new
   matter with its own requirements. It follows only what you actually said,
   and it never widens the session without asking.
9. Assembles a draft package for your FSO/SSO: narrative, form-section
   crosswalk, reporting channel/timeline, and supporting-documents checklist.
10. Verifies its own output: every citation checked against the corpus index,
   pseudonym intact, disclaimer attached, no advice to conceal anything —
   this tool helps you report **completely and truthfully, period**.
11. Tells you to replace "John Doe" with your legal name at submission time.

| I want to… | Read |
|---|---|
| **Build, publish, and beta-test this** | [`BUILD-GUIDE.md`](BUILD-GUIDE.md) — the one document |
| **Run this, and I have nothing set up** | [`GET-STARTED.md`](GET-STARTED.md) |
| Run it, and I already use an AI assistant | [`USAGE.md`](USAGE.md) |
| Put my own copy on GitHub, never used GitHub | [`PUBLISHING.md`](PUBLISHING.md) |
| Test it before trusting it | [`BETA-TESTING.md`](BETA-TESTING.md) |
| Understand how it works | [`PROCESS.md`](PROCESS.md) · [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Know what it does with my data | [`DEPLOYMENT.md`](DEPLOYMENT.md) · [`DISCLAIMER.md`](DISCLAIMER.md) |

See [`PROCESS.md`](PROCESS.md) for the process map — session flow, question
sourcing, trust gates, and corpus grounding, as diagrams that render here on
GitHub. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design and
[`DEPLOYMENT.md`](DEPLOYMENT.md) for what each deployment mode can honestly
promise.

## What it will not do

- Predict or improve your odds. Adjudication is the Government's alone.
- Help you conceal, minimize, or time a disclosure. Candor is a Guideline E
  issue; a tool that coached evasion would hurt you.
- Give legal advice — or nudge you toward a lawyer instead of reporting. If
  you've decided to disclose, this tool helps you do that; it won't offer to
  pause while you get legal advice, because that quietly makes waiting look
  like the safe choice. If *you* want counsel, that's your call and it says so
  without argument. An issued SOR/LOI or an appeal is the exception — that's a
  formal adversarial process, not self-reporting, and this isn't built for it.
- Accept classified information. It is not an authorized system.

## Two pieces, and only one is in this repo

| | In this repo | Downloaded separately |
|---|---|---|
| **What** | Agents, scripts, schemas, tests, and the maintainer's authored analysis — checklists, reporting tables, form maps | The **DCSA Library**: SEAD directives, ISLs, 32 CFR, and 10,658 published DOHA decisions with retrieval indexes |
| **Size** | A few hundred KB | ~55 MB (Essentials) to ~2.3 GB (with source PDFs) |
| **Where it goes** | Wherever you cloned it | Wherever *you* put it — the tool asks, then remembers |

The tool **never downloads the library**. If it's missing or incomplete, the
tool names what's absent and points you at the link. See
[`library-sources.yaml`](library-sources.yaml).

## Privacy model

Privacy here is a property of **how you deploy this**, not of the software.
Read [`DEPLOYMENT.md`](DEPLOYMENT.md) — it defines local vs hosted modes and
what each can honestly promise. The tool states its own mode before it
collects anything.

Running locally, which is what this repo describes:

- **Nothing you type is stored or transmitted by this project.** Files are
  written only when you ask, only to `output/`, which is gitignored.
- **Your text does go to whatever model provider you've configured**, under
  their terms. This project has no control over that and doesn't pretend to.
- **No telemetry, no logging.** Read the code — and read the code of any fork
  before running it, because forks may differ.
- **You choose the privacy level.** At the start, after the tool tells you
  where your text goes, you pick how much to share about *other people*:

  | Tier | Other people | Contact details |
  |---|---|---|
  | **High** *(default)* | Person 1, Person 2 — role only | You keep the mapping; template at the end |
  | **Medium** | Named | Template at the end |
  | **Low** | Named | Collected |

  **Never at any tier:** Social Security numbers and dates of birth. Those go
  directly on the form, never here.

- **Organizations are exempt at every tier.** The bar, the court, the
  arresting agency, your employer, the clinic — the form requires them and
  they aren't private individuals. The tool can look up a business address
  for you, but it **asks first every time** (the search itself discloses the
  venue) and never inserts an address you haven't confirmed. It will never
  look up a person.

- **You are "John Doe" at every tier**, and swap your legal name in at
  submission.

## Model-agnostic by design

Runs in any agentic environment with filesystem and shell access — Claude
Code/Cowork, Codex, Antigravity, Cursor, or a hosted build. No vendor-specific
features. The consequence: **no platform enforces that an agent only read
`/corpus`**, so prompt-level restrictions are requests, not controls. The
deterministic scripts are the real trust anchor:

```bash
python scripts/check_library.py "<path to DCSA Library>" --remember   # once
python scripts/validate_session.py output/session.json          # the state file is gated too
python scripts/assemble_package.py output/session.json -o output/package.md
python scripts/verify_output.py output/package.md output/session.json   # hard gate
```

Use `-o`, not shell redirection — PowerShell redirection writes UTF-16 and the
verifier rejects it. On pass, the verifier prints the package's SHA-256 and
writes a `.sha256` sidecar. **Run the verifier yourself as the last step** and
compare the hash the assistant quoted: the scripts are only a trust anchor if
a human confirms they actually ran.

Assembly is a script so the substitution checklist, contact template,
disclaimer, and corpus version cannot be dropped or reworded by a model — the
narrative is the only model-authored part. Verification fails the package on a
fabricated case citation, any phone/email/SSN pattern anywhere, a `Person N`
reference with no template entry, a pre-filled template field,
outcome-prediction or concealment language, a missing disclaimer, or a missing
corpus version. A failure means do not deliver — regardless of which model
wrote the draft.

## Point your assistant at `AGENTS.md`

The project's rules live in one tool-neutral file. However you run this, that
file is the entry point:

| Assistant | How to load it |
|---|---|
| **OpenAI Codex** | Reads `AGENTS.md` automatically |
| **Claude Code** | `CLAUDE.md` imports it automatically. Adds `/report` and `/checkup`, and a settings file that **denies web access outright** |
| **Cursor** | Add a rule pointing at `AGENTS.md`, or paste it once |
| **Anything else** | Paste `AGENTS.md` as your first message |

Nothing here depends on a particular vendor. Claude Code gets one genuine
extra — the never-fetch rule is enforced by its permission system rather than
by a prompt — but the deterministic scripts are the real trust anchor
everywhere, and `tests/run_tests.py` checks that no script or agent prompt
depends on any vendor's features.

## Quickstart

```bash
git clone https://github.com/<you>/adverse-information-assistant
cd adverse-information-assistant
pip install pyyaml

# 1. Get the DCSA Library — it is NOT in this repo. See library-sources.yaml
#    for the download link. The Essentials bundle is ~55 MB and is all the
#    tool needs. Unzip it anywhere, then:
python scripts/check_library.py "C:\path\to\DCSA Library" --remember
python scripts/validate_corpus.py
```

**Without the library the tool still runs** — it just cannot quote guideline
text or cite a decision, and it says so at the start of every session rather
than guessing.

2. Open the folder in your AI assistant and give it:

```
Read agents/conductor.md and run the session it describes, exactly as written.
Follow the stage order. Use the agent prompt files in agents/core/ and
agents/optional/ as the instructions for each step. Only cite things that
exist as files in corpus/. Before showing me any final package, run
scripts/verify_output.py and do not give me output that fails it. When we
finish, give me the exact verify_output.py command to run myself and the
SHA-256 it printed, so I can confirm the file I have is the file that passed.
```

Never used GitHub? [`PUBLISHING.md`](PUBLISHING.md) walks through it from
zero, on Windows, assuming no IT background.

## Known limitations (read these)

- **Single-maintainer review.** V1's design and corpus are reviewed by one
  subject-matter expert (an FSO). No peer or attorney review gates releases.
- **Everything ships unverified.** Every corpus file is
  `maintainer_verified: false` until a human checks it against the official
  source. `validate_corpus.py` warns on each one, and agents treat unverified
  files as unciteable — reportability degrades to "ask your FSO" rather than
  guessing. The scaffold is honest about being a scaffold.
- **Policy-derived checklists.** The gap-analysis checklists are derived from
  SEAD 4 conditions, ISL 2021-02 / SEAD 3 Appendix A data elements, and
  published DOHA decisions — **not** validated against actual DCSA/CAF
  request-for-information data. This is the component most likely to be wrong.
  If you are a practitioner and know what agencies actually ask for twice,
  please file a [bounce report](.github/ISSUE_TEMPLATE/bounce-report.md).
- **Minimization detection is weak.** The candor reviewer catches dropped
  facts and degraded quantities. It cannot reliably catch softening that
  never had a factual anchor in what you originally said. You must read your
  own statement before signing it; no automated check substitutes for that.
- **DOHA cases inform questions, never predictions.** The corpus is contested
  SOR cases — a selection-biased sample that says nothing about how ordinary
  reports resolve. It shapes what you get asked. It never produces a rate, a
  tendency, or a forecast.
- **Corpus snapshot.** Guidance changes (ISLs get revised — the bundled ISL
  2021-02 is the May 2024 v2). Check the corpus version in each release and
  verify anything load-bearing against the official source.
- Boundary cases deliberately resolve to "consult your FSO," not to answers.

## Contributing

Corrections beat features. Wrong channel, wrong table, wrong timeline, or
"the agency always asks for X on this event type" reports are prioritized
above everything else. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

[MIT](LICENSE). Provided as-is, no warranty, use at your own risk.
