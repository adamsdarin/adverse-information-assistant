# Adverse Information Reporting Assistant — Architecture

A **model-agnostic** multi-agent assistant that helps security clearance holders and applicants prepare complete, candid adverse-information self-reports for their security office. It first determines what policy requires them to report — **SEAD 3** for every covered individual, plus **DCSA ISL 2021-02** and **32 CFR § 117.8** for cleared industry — then what criteria that report will be graded against under the **SEAD 4** adjudicative guidelines. It sources questions from the form the user must satisfy, the reporting requirements, per-guideline checklists, and published DOHA decisions held in a separately distributed DCSA Library; follows threads that open onto further reportable matters; and assembles a draft the user verifies and signs.

Runs in Claude Code/Cowork, OpenAI Codex, Cursor, Google Antigravity, or any assistant that can read a folder and run a script.

> **This tool does not adjudicate anything.** The U.S. Government — through DCSA and the relevant adjudicative authorities — makes all determinations regarding security clearance eligibility. This tool's sole purpose is to help the user provide the necessary, complete, and truthful information so adjudicators can apply the whole-person concept, based on publicly available information about the personnel vetting process. It is not legal advice, and it is not a substitute for consulting your FSO/SSO or a security clearance attorney.

---

## 1. Purpose and Non-Goals

### Purpose

- **Primary user: the covered individual**, running the tool privately before approaching their FSO/SSO. (An FSO-facing mode with DISS-field-structured output is a roadmap item, not v1.)
- **Reduce round-trips with federal agencies.** The design goal is first-time-right submissions: a report complete enough that DCSA/CAF follow-up requests (missing dispositions, vague dates, absent supporting documents) are the exception, not the norm.
- Reduce the anxiety and guesswork of self-reporting adverse information (e.g., an OWI/DUI, a delinquent debt, unauthorized foreign contact).
- Ensure the user's written narrative contains the elements adjudicators actually look for under the applicable SEAD 4 guideline(s), including the mitigating conditions the user may be able to speak to truthfully.
- Ground every reference to policy or precedent in files on disk — the repo's authored corpus or the downloaded DCSA Library — never in model memory.

### Non-Goals (enforced, not just stated)

- **No spin.** The assistant helps the user report completely and truthfully. It must refuse to help conceal, omit, minimize, or strategically time a disclosure. Candor is itself an adjudicative factor (Guideline E); a tool that coaches evasion would harm its users.
- **No outcome predictions.** The assistant never estimates the probability of a favorable adjudication.
- **No legal advice, and no legal deferral.** The assistant may summarize published decisions and public guidance; it may not advise on legal strategy. It also does not send people to lawyers *instead of* reporting: it never asks whether they want to consult an attorney and never offers to pause a disclosure pending legal advice, because a user of this tool has already decided to disclose and offering to wait reverses that decision under the cover of prudence. The sole unprompted exception is an issued SOR/LOI or an appeal — an adversarial proceeding rather than a self-report, and outside this tool's scope. If the user raises counsel, the assistant supports it without argument.
- **No classified or CUI processing.** The assistant instructs the user up front never to enter classified information, and that this is not an authorized system for such material.

---

## 2. Design Principles

1. **Privacy is the architecture.** All personal narrative content stays in the local session. The repo ships no user data, writes no user data to disk by default, and the assistant operates on a pseudonym.
2. **Pseudonymity by construction, and privacy by consent.** The user is **"John Doe"** throughout and is never asked for a real name. For *other* people, the user chooses a tier at intake — high (Person 1, Person 2, role only), medium (names, no contact details), or low (contact details collected) — defaulting to high. Social Security numbers and dates of birth are collected at no tier: a floor, not a tier property. Organizations are exempt at every tier, because the form requires them and they are not private individuals.
3. **Deterministic retrieval, zero generated citations.** Any SEAD 4 text or DOHA decision the assistant cites must resolve to a file on disk. `verify_output.py` rejects any package containing a case number absent from the DCSA Library's manifest — and rejects a citation outright when no citation source is available at all, because an unverifiable citation is indistinguishable from a fabricated one. This is the primary hallucination control. Case *selection* is likewise deterministic: `doha_retrieval.py` picks decisions from the library's manifest by adjudicated guideline, era, and outcome, so a model never chooses which precedent exists.
4. **Split by authorship.** The repo carries what the maintainer wrote (checklists, reporting tables, form maps); the DCSA Library carries what the Government published (directives, ISLs, 32 CFR, 10,658 DOHA decisions). The tool works offline once both are on disk, and the deliverable footer records the corpus version so a draft can be traced to the guidance it was built against.
5. **Form-aware.** The user is asked early which questionnaire governs their situation — the **SF-86 (via eApp)** or the **Personnel Vetting Questionnaire (PVQ)** — because section mappings and reporting thresholds differ, and both are in circulation during the Trusted Workforce 2.0 transition.
6. **Whole-person framing.** Question generation is driven by SEAD 4's disqualifying *and* mitigating conditions, so the narrative gives adjudicators the context the whole-person concept requires (recency, frequency, age/maturity at the time of conduct, voluntariness, rehabilitation, likelihood of recurrence).
7. **Requirement-aware for industry.** For users in cleared industry (NISP contractors), the assistant determines *whether* the matter is reportable, *to whom*, and *on what timeline* from the ISL 2021-02 reporting tables (baseline "all covered individuals" vs. Top Secret/"Q" additional requirements), as structured data in `/corpus/reporting/` — never from model memory. It always errs toward "discuss it with your FSO" when a matter falls near a table boundary.
8. **Timeliness beats polish.** When a matter is reportable the assistant says so *immediately and out loud* — the obligation runs from the event, not from a finished narrative — and tells the user to contact their security office today even if the session is unfinished. It produces one complete package, not a stub followed by a supplement; the warning is spoken, not a document. The tool must never become the reason a report was late.

9. **The floor is not the ceiling.** What the tables require is a minimum. The assistant says so, helps with anything else the user feels they should disclose, and tells them that volunteering something before being asked is itself a recognized mitigating consideration.

---

## 3. Session Flow

**`agents/conductor.md` is the generative source of the flow** — it is what
the agents actually execute, so documentation follows execution, never the
reverse. `PROCESS.md` renders it as diagrams; a drift check in
`tests/run_tests.py` fails when the two stage orders diverge, so neither can
become wrong silently. This document covers *why* the design is shaped the
way it is; conductor.md says *what happens*, and PROCESS.md shows it.

The shape, in one paragraph: locate the corpus and the DCSA Library → orient the user and take a
privacy tier → capture their account in their own words → **determine what
policy requires them to report** → determine **what criteria that report will
be graded against** → source questions from three streams → interview → detect
new threads and loop → check consistency → draft → verify deterministically →
hand off.

Two ordering decisions carry most of the design:

**Reportability precedes classification.** SEAD 3 creates the obligation;
SEAD 4 is the lens applied to what is disclosed. The reporting tables key on
event type, not adjudicative category, so reportability never needs a
classification — and a guideline the classifier cannot map confidently must
never make a matter unreportable.

**The session loops.** A matter rarely arrives alone: an OWI mentions
court-ordered therapy, the therapy mentions an assault, the assault mentions
cocaine. Accepted threads re-enter as new matters with their own reportability
determination and required fields. Two limits keep that from becoming an
interrogation — the detector follows only what the user actually said, and
every expansion is consented to before scope widens.

---

## 4. Agent Architecture

A **conductor** owns the state machine; stateless specialists do the work.
Nothing depends on a vendor's subagent feature: an assistant with no subagent
mechanism runs each agent as a separate turn using its prompt file. Contracts
are JSON Schemas in `/schemas/`.

### Core — always run

| Agent | Job |
|---|---|
| `intake` | Corpus location, orientation, privacy tier, context, narrative capture |
| `triage` | **Runs on every user message.** Escalation and safety. Warns, never halts |
| `requirements-advisor` | What policy requires. SEAD 3 always; ISL 2021-02 for industry |
| `classifier` | What it will be graded against. SEAD 4 A–M; auto-attaches E |
| `thread-detector` | Did that answer open a new reportable matter? |
| `gap-analyst` | What is still missing, and whether it is required or optional |
| `interviewer` | Turns gaps into answerable questions, tier- and sensitivity-aware |
| `narrative-writer` | The first-person statement, in the user's own voice |

### Optional — skip to reduce cost and latency

`precedent-miner` (cases → questions) · `answer-integrator` (free text →
checklist slots) · `consistency-checker` (contradictions) ·
`documents-advisor` (records to obtain) · `candor-reviewer` (imported
minimization) · `entity-resolver` (business addresses; the **only** agent with
network access)

Skipping any of these degrades quality, never correctness. The deterministic
gates run regardless.

### Deterministic scripts — the actual trust anchor

`check_corpus.py` · `build_index.py` · `validate_corpus.py` ·
`assemble_package.py` · `verify_output.py` · `tests/run_tests.py`

**This is the load-bearing consequence of being model-agnostic.** In an
SDK-specific design, tool restrictions enforce that an agent only reads
approved sources. Across arbitrary platforms nothing enforces that —
prompt-level restrictions are requests. So the guarantees relocate into code
that runs regardless of which model produced the draft: assembly is
template-driven so the disclaimer and crosswalk cannot be dropped, and
verification is a hard stop.

**One platform gets more, and that is documented rather than depended on.**
The repo ships a Claude Code configuration whose permission deny-list blocks
`WebFetch`, `WebSearch`, `curl`, and `wget` — so on that platform the
never-fetch rule is enforced by the runtime, not merely requested. That is a
strictly stronger guarantee for those users and changes nothing for anyone
else. Nothing in `scripts/` or `agents/` may depend on it; `tests/run_tests.py`
asserts that no script or agent prompt so much as references `.claude/`, and
the release checklist requires one full scenario run in a non-Claude assistant
before publishing.

The rules themselves live in `AGENTS.md`, which is tool-neutral and which
`CLAUDE.md` imports rather than copies — two files stating the same rules would
drift the moment either was edited.

Two things the scripts explicitly cannot check, stated rather than hidden:
tonal minimization with no factual anchor in the source, and whether a
capitalized word is a person's name. The user's own review is the backstop,
and they are told so.

---

## 5. Repository Layout

```
adverse-information-assistant/
├── README.md · GET-STARTED.md · USAGE.md · PUBLISHING.md · BETA-TESTING.md
├── PROCESS.md            # authoritative flow, as diagrams
├── ARCHITECTURE.md       # this file — rationale
├── DEPLOYMENT.md         # local vs hosted, and what each can promise
├── DISCLAIMER.md · LICENSE · CONTRIBUTING.md
├── corpus-sources.yaml   # where to get the corpus; never auto-fetched
├── agents/
│   ├── conductor.md
│   ├── core/             # 8 agents
│   └── optional/         # 6 agents
├── corpus/               # EXTERNAL — see §5.1
├── schemas/              # 6 JSON Schemas
├── scripts/              # the trust anchor
└── tests/run_tests.py    # regression suite for the scripts
```

### 5.1 Two dependencies, split by authorship

**`corpus/` ships in the repo.** It holds what the maintainer *wrote*:
per-guideline checklists, reporting tables, form maps, authority layers. Small,
version-controlled alongside the agents that consume it, and meaningless
without them.

**The DCSA Library is downloaded separately.** It holds what the Government
*published*: SEAD directives, ISLs, 32 CFR, and 10,658 DOHA decisions with
retrieval indexes. Gigabytes, updated on its own cadence, and useful outside
this tool. The user puts it wherever they like; `check_library.py` finds it,
identifies which distribution bundle they have, and states what each gap costs
a session.

The library declares its own root — any folder containing
`START_HERE_FOR_ROBOTS.json`, with every path inside relative to it — so no
drive letter, account name, or folder name is ever assumed. Path resolution is
deliberately case-insensitive: the library's entry point currently names some
files in a different case than they appear on disk, which is harmless on
Windows and fatal on macOS and Linux. `check_library.py` reports the mismatch
and works around it.

**Distribution is tiered.** Essentials (~55 MB) is everything the tool needs:
decisions are indexed by number, era, outcome, and adjudicated guideline in a
5 MB manifest, so precedent retrieval and citation checking work without the
364 MB full-text index. Search (~460 MB) adds full-text. Complete (~2.3 GB)
adds source PDFs for human reading. A manifest entry pointing at a file the
user's bundle omits is a normal tier fact, not corruption.

**No agent may fetch either one.** Not from dni.gov, not from doha.ogc.osd.mil, not
from anywhere. Government sites block automated access, so a scraping design
works until it silently doesn't — and more fundamentally, auto-fetched content
is unverified content wearing a verified file's name. That is worse than an
empty corpus, because an empty corpus announces itself.

A **partial** corpus is a supported, common state: the tool proceeds and
discloses what is missing. A **wrong folder** is refused outright, because
"running at reduced capability" and "running against nothing" are
indistinguishable to a user unless something says otherwise.

### 5.2 Everything ships unverified

Every corpus file carries `maintainer_verified: false` until a human checks it
against its official source. Agents treat unverified files as uncitable, and
reportability degrades to "check with your security office." The scaffold is
honest about being a scaffold.


## 6. Privacy and Security Model

1. **Session-local by default.** User narrative content exists only in the running session. Nothing is transmitted anywhere except to the model API serving the session, and nothing is written to disk unless the user explicitly requests the output file.
2. **Pseudonym enforcement.** The assistant never requests the user's real name, SSN, case numbers tied to their identity, employer, agency, or any program/SCI access specifics. One deliberate exception to data minimization: the coarse access tier (**baseline vs. Top Secret/"Q"**) *is* requested for clearance holders on the industry path, because ISL 2021-02's reporting tables differ by tier and the tool cannot determine reportability without it. The Verifier flags drafts containing apparent real-name patterns the user may have typed, and prompts the user to confirm substitution back to "John Doe."
3. **No telemetry, no logging.** The repo ships no analytics. `README.md` documents this and warns that forks may differ — users should read the code of any fork they run.
4. **Data minimization.** Age is optional and coarse (Stage 3). Every intake field must justify itself against a mitigating/disqualifying condition or a form field; anything that can't is not collected.
5. **Explicit system-boundary warning.** Stage 1 states: this is not a Government system, not authorized for classified information, and the user's eventual submission goes through their SSO/FSO — not through this tool.
6. **`.gitignore` ships covering `output/` and any session artifacts**, so a user who clones the repo and generates a draft cannot accidentally commit their adverse-information narrative back to a public fork.

---

## 7. Ethical Guardrails (encoded in agent prompts and Verifier checks)

- **Duty of candor is load-bearing.** If a user asks "do I have to report this?" the assistant explains the applicable reporting requirement and the Guideline E consequences of concealment; it does not weigh odds of getting caught. If a user asks how to phrase something to hide a fact, the assistant declines and explains why complete disclosure with mitigation context serves the user better.
- **No legal deferral, offered or implied.** The assistant never asks whether the user wants to consult an attorney and never presents "report it" against "talk to a lawyer first" as competing options. Someone using this tool has already decided to disclose; offering to pause reverses that decision by dressing delay as prudence, and if self-reporting routinely routed through counsel almost nobody would self-report. The assistant states facts about a situation; it does not recommend a course of action that competes with reporting. When the *user* raises counsel, it supports that without argument and leaves the session resumable. The single unprompted exception is an issued **SOR/LOI or appeal** — a formal adversarial proceeding with deadlines, not a self-report, and outside what this tool is built for; that gets said once, plainly.
- **Escalation that remains:** classified spillage stops the description immediately and routes to the security office; coercion or elicitation re-runs the requirements advisor for the CI channel; distress sets the paperwork aside.
- **Wellbeing-aware.** Adverse-information narratives can involve substance abuse, financial crisis, or mental health. The Interviewer's `sensitivity: high` questions are asked one at a time, with an explicit "you may skip this" and — where relevant — a note that SEAD 4 explicitly states that seeking mental health care is not itself disqualifying.
- **Every deliverable carries the disclaimer block** (§1 quote) verbatim. The Verifier fails any draft without it.

---

## 8. Corpus Maintenance

- **Guideline texts** change rarely; update on SEAD 4 amendment, bump `corpus_version`.
- **Reporting requirements** track three sources with different change cadences: SEAD 3 (rare), 32 CFR Part 117 (rulemaking), and DCSA ISLs (the bundled ISL 2021-02 is the **May 2024 v2** revision — ISLs get revised, and ISL 2021-02 itself rescinded ISL 2011-04). Each release records the exact ISL version in `corpus/reporting/`, and the deliverable footer cites it so a report can be traced to the guidance it was built against. A maintainer check for new ISLs/VOIs belongs in the release checklist.
- **Case curation criteria:** published DOHA ISCR decisions only (hearing and appeal), selected for factual diversity per guideline, with both favorable and unfavorable outcomes represented so the tool never implies a predictable result. Every case links to its official published source.
- **Form maps** are reviewed when eApp/PVQ content changes; the PVQ is still displacing the SF-86 under Trusted Workforce 2.0, so `sf86-map.yaml` and `pvq-map.yaml` are both first-class and Stage 2 selects between them.
- **Versioned releases.** Each GitHub release pins a corpus snapshot; the deliverable footer records the corpus version used, so a draft can be traced to the guidance it was built against.

---

## 9. Validation Posture

V1 is reviewed by a single subject-matter expert (the maintainer, an FSO) and then published. That is a deliberate, acknowledged trade-off — no peer or attorney review gates the release. The design compensates structurally:

- **Conservative defaults.** Every boundary case in reportability, channel, or timeline resolves to "consult your FSO," never to a confident answer the corpus doesn't directly support.
- **Fixture-based tests** (`tests/fixtures/`): synthetic narratives with expected classifications, expected reportability determinations, and expected gap lists, runnable in CI without a model where possible. Every bug found in the wild becomes a fixture.
- **README "Known Limitations" section** stating plainly: single-maintainer review, policy-derived checklists (§5.2), corpus snapshot date, and that the tool's determinations are informational — the user's FSO and the U.S. Government are the authorities.
- **Community correction path.** Issue templates for practitioners to report wrong-channel/wrong-table errors and agency-asked-for-X-again patterns, prioritized above feature work.

---

## 10. Roadmap (post-V1)

- **FSO/SSO mode:** a second entry path for security officers preparing submissions, with output structured to DISS incident-report fields (identity known, pseudonym model off). Deferred from v1 because the covered individual is the primary user.
- Optional live check against doha.ogc.osd.mil for decisions newer than the bundled corpus (opt-in, clearly disclosed as a network call).
- SEAD 3 continuous-reporting mode as a fully mapped flow (foreign travel, foreign contacts, financial anomalies).
- Maintainer tooling: semi-automated case ingestion (fetch → draft frontmatter → human review gate before merge).
- Localization of the interview layer for readability (plain-language rewrite pass), keeping corpus text verbatim.

---

## 11. Glossary

| Term | Meaning |
|------|---------|
| SEAD 3 / SEAD 4 | Security Executive Agent Directives: reporting requirements (3) and National Security Adjudicative Guidelines (4) |
| Guidelines A–M | The 13 adjudicative guidelines in SEAD 4 (Allegiance; Foreign Influence; Foreign Preference; Sexual Behavior; Personal Conduct; Financial; Alcohol; Drugs; Psychological Conditions; Criminal Conduct; Handling Protected Information; Outside Activities; Use of IT) |
| DOHA / ISCR | Defense Office of Hearings and Appeals; Industrial Security Clearance Review cases, published at doha.ogc.osd.mil |
| SF-86 / eApp | Questionnaire for National Security Positions and the online system that hosts it |
| PVQ | Personnel Vetting Questionnaire — the Trusted Workforce 2.0 form replacing the SF-86 |
| SOR / LOI | Statement of Reasons / Letter of Intent — formal notice of intent to deny/revoke |
| SSO / FSO | Special Security Officer / Facility Security Officer |
| DCSA | Defense Counterintelligence and Security Agency |
| NISP / NISPOM | National Industrial Security Program / its Operating Manual, codified at 32 CFR Part 117 |
| ISL | Industrial Security Letter — DCSA implementing guidance for industry (here, ISL 2021-02 v2, May 2024, implementing SEAD 3 reporting under §117.8) |
| DISS | Defense Information System for Security — DoD system of record where FSOs submit incident and foreign-travel reports |
| CISA (DCSA) | The contractor's assigned DCSA Counterintelligence Special Agent — direct reporting channel for suspected foreign-intelligence-entity contact |
| Covered individual | A person with, or in process for, eligibility for access to classified information under the NISP |
