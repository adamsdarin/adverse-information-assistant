# Process Map

How a session actually runs, what grounds each decision, and where the
guarantees are enforced.

> **`agents/conductor.md` is the generative source of the flow** — it is what
> the agents actually execute. This file renders and explains it. If the two
> disagree, conductor.md wins and this file is wrong;
> `tests/run_tests.py` includes a drift check that fails when the stage
> orders diverge.

---

## 1. Session flow

```mermaid
flowchart TD
    START(["User runs the tool"]) --> LOC

    LOC["<b>0 · Locate reference material</b><br/>corpus/ ships in the repo<br/><b>DCSA Library is a separate download</b><br/><i>says what's found and what it costs<br/>· NEVER fetches · missing = instructions only</i>"]
    CAN["<b>0b · Capability canary</b><br/>model answers a known scenario,<br/>then checks itself<br/><i>fail = warn the user, don't halt</i>"]
    LOC --> CAN --> INTAKE

    INTAKE["<b>1 · Intake</b><br/>You are John Doe · deployment mode disclosed<br/><b>privacy tier chosen</b> — high / medium / low<br/>checkpoint file disclosed · no classified information"]
    CTX["<b>Context</b><br/>Applicant or holder? Industry or federal?<br/>Baseline or TS/Q? National security, public trust, low risk?"]
    NARR["<b>Open narrative</b><br/>'Tell me, in your own words,<br/>what you feel you have to report'<br/><i>stamped with a hash — never edited after</i>"]
    INTAKE --> CTX --> NARR --> REQ

    REQ["<b>① Requirements Advisor — WHAT MUST BE REPORTED</b><br/>matched on <i>event type</i>, needs no guideline tags<br/>Returns YES or CONSULT SECURITY OFFICE — never 'no'"]
    LAY{"Population?"}
    REQ --> LAY
    LAY -->|"cleared industry"| L1["<b>SEAD 3 + ISL 2021-02</b><br/>channel: FSO → DISS · DCSA CISA"]
    LAY -->|"federal civilian<br/>or military"| L2["<b>SEAD 3 only</b><br/>+ their agency's own implementation<br/>channel: servicing security office<br/><i>never DISS — they can't access it</i>"]
    L1 --> RDEC
    L2 --> RDEC
    RDEC{"Reportable?"}
    RDEC -->|yes| WARN
    RDEC -->|unclear| FSO

    WARN["<b>⚠ IMMEDIATE SPOKEN WARNING</b><br/>'The clock started at the event, not here.<br/>If you can't finish today, call your security office today.'<br/>No stub document — the session continues"]
    FSO["'Raise this with your security office'<br/>with the ambiguity explained<br/><i>verified table threshold may be quoted,<br/>never as advice not to report</i>"]

    FLOOR["<b>The floor is not the ceiling</b><br/>'That's what policy requires. If there's anything else<br/>you feel you should disclose, you should —<br/>volunteering it counts in your favor.'<br/><i>voluntary matters are treated identically</i>"]
    WARN --> FLOOR
    FSO --> FLOOR
    FLOOR --> APPQ
    APPQ{"Still an applicant?"}
    APPQ -->|no| CLASS
    APPQ -->|yes| APP
    APP["<b>Additionally for applicants</b><br/>which PVQ / SF-86 items now need an affirmative answer<br/><i>an in-process applicant IS a covered individual —<br/>reportability was determined above, never skipped</i>"]
    APP --> CLASS

    CLASS["<b>② Classifier — WHAT IT'S GRADED AGAINST</b><br/>SEAD 4 guidelines A–M<br/><i>what adjudicators will look at, never a verdict</i>"]
    EDEC{"Concealment indicator,<br/>or merely late?"}
    EATT["<b>Concealment</b> — auto-attach Guideline E<br/>and explain why to the user"]
    EDEL["<b>Late only</b> — no E<br/>delay explanation becomes REQUIRED<br/><i>a self-corrector is not a concealer</i>"]
    CLASS --> EDEC
    EDEC -->|"false statement made"| EATT --> PACE
    EDEC -->|"no false statement"| EDEL --> PACE

    PACE["<b>Pace choice</b><br/>essentials only · or thorough<br/><i>switchable any time — required fields never skipped</i>"]
    PACE --> SRC
    SRC["<b>Question sourcing</b><br/>see diagram 3"]
    SRC --> LOOP

    LOOP["<b>Gap → Interview loop</b><br/>progress shown each round: 'Matter 2 of 3 — 6 required left'<br/>Gap Analyst finds what's missing · Interviewer asks<br/><i>doesn't know the court? → court_lookup nudge,<br/>user confirms, THEIR answer is recorded</i>"]
    LDEC{"Required fields answered<br/>or marked to-follow?"}
    LOOP --> LDEC
    LDEC -->|no| LOOP
    LDEC -->|yes| THREAD

    THREAD["<b>Thread Detector</b><br/>Did that answer open a NEW reportable matter?<br/><i>follows what was said — never fishes</i>"]
    TDEC{"New thread?"}
    THREAD --> TDEC
    TDEC -->|"yes — user consents"| REQ
    TDEC -->|"yes — user declines"| NOTE["Recorded · told it's still reportable<br/>· never raised again"]
    TDEC -->|"none, or depth 5"| CONS
    NOTE --> CONS

    CONS["<b>Consistency Checker</b><br/>Contradictory dates · impossible sequences<br/>conflicts with the filed form<br/><i>surfaces to the user, never resolves</i>"]
    DOCS["<b>Documents Advisor</b><br/>THREE records, with timing:<br/>court disposition · arrest report · driver record<br/><i>the driver record recovers forgotten dates fastest</i>"]
    WRITE["<b>Narrative Writer</b><br/>First person · active voice · the user's own register<br/>numbered placeholders — never names"]
    CAND["<b>Candor Reviewer</b><br/>Compare draft against raw intake<br/>Catch dropped facts, softened quantities,<br/>and paraphrased outcome/concealment language"]
    CONS --> DOCS --> WRITE --> CAND --> GATE

    GATE["<b>Deterministic gates</b><br/>see diagram 4"]
    GATE --> HANDOFF

    HANDOFF(["<b>Handoff</b><br/>Replace John Doe with your legal name<br/>Complete the Person N template<br/><b>Run the verifier yourself and match the SHA-256</b><br/>Verify every fact — you sign it"])

    TRIAGE["<b>Triage</b><br/>standing rules on every message<br/><b>+ mandatory checkpoints, logged to the state file</b><br/>after narrative · each gap round · before any thread<br/>expansion · before assembly<br/><i>warns, recommends, never halts</i>"]
    TRIAGE -.->|monitors| NARR
    TRIAGE -.->|monitors| LOOP
    TRIAGE -.->|monitors| THREAD
    TRIAGE -.->|monitors| GATE

    classDef warn fill:#5a2d2d,stroke:#c66,color:#fde
    classDef gate fill:#2d3a5a,stroke:#68c,color:#def
    classDef monitor fill:#4a3a1a,stroke:#ca6,color:#fed
    classDef step fill:#2d4a2d,stroke:#6a6,color:#dfd
    class WARN warn
    class GATE,CAND,CAN gate
    class TRIAGE monitor
    class REQ,CLASS,PACE step
    class FLOOR step
    class L2 warn
    class THREAD monitor
    class EDEL step
    class LOC gate
```

**The session is a loop, not a line.** A matter rarely arrives alone: an OWI
mentions court-ordered therapy, the therapy mentions an assault, the assault
mentions cocaine. Each is separately reportable, and each surfaced only
because the one before it was explored. So an accepted thread re-enters at ①
as a new matter with its own reportability determination, timeliness warning,
classification, and required fields.

Two limits keep that from becoming an interrogation. The detector **follows
only what the user actually said** — "you mentioned therapy" is a thread,
"any other crimes?" is fishing — and **every expansion is consented to** before
the scope widens. A declined thread is recorded, honestly flagged as still
reportable, and never raised again.

**Order matters.** SEAD 3 creates the obligation; SEAD 4 is the lens applied
to what gets disclosed. Reportability is settled before anything is
classified, and never depends on the classification — the tables key on event
type, not adjudicative category. A guideline the classifier can't map
confidently does not make a matter unreportable.

**Two layers of authority, and they are not the same document.** SEAD 3 is
the Security Executive Agent's directive and binds **every** covered
individual — contractor, federal civilian, military. ISL 2021-02 is DCSA's
implementation of it for NISP contractors only, layered on top. A federal
employee is not exempt from reporting analysis; they are exempt from DCSA's
version of it. "Not industry" must never become "no obligation."

Channels follow the same split. FSO → DISS and the DCSA CI Special Agent are
the industry mechanism; a federal employee reports through their servicing
security office. Naming a system the user cannot access reads as
authoritative and sends them nowhere useful.

**Applicants are covered individuals too.** "Covered individual" includes a
person *in process for* eligibility, so an applicant with a new reportable
matter has a SEAD 3 obligation while their case is in flight — they get the
full reportability pass, with the channel adjusted (sponsoring FSO for
industry, hiring agency security office for federal; unverified entries
degrade to "confirm with the office sponsoring your case"). Their extra step
is the form-question mapping: which of the form's own questions now require
an affirmative answer.

---

## 2. Privacy tiers

```mermaid
flowchart TD
    ASK["<b>Intake asks</b><br/>after disclosing where the text goes"] --> T

    T{"How much do you want<br/>to share about other people?"}
    T -->|"HIGH — default"| H["Person 1, Person 2 — role only<br/>user keeps the mapping on paper"]
    T -->|MEDIUM| M["Names only<br/>no phone / email / address"]
    T -->|LOW| L["Names, phones, emails, addresses"]

    FLOOR["<b>FLOOR — no tier relaxes this</b><br/>never SSN · never date of birth<br/>never classified information"]
    H --- FLOOR
    M --- FLOOR
    L --- FLOOR

    ENT["<b>Organizations are exempt at EVERY tier</b><br/>bar · court · arresting agency · employer · clinic<br/><i>the form requires them; they aren't private individuals</i>"]

    ENT --> LOOK{"Need an address?"}
    LOOK -->|yes| CONSENT["<b>entity-resolver</b> asks consent<br/>'That sends the business name to a search engine'"]
    CONSENT -->|declined| SUPPLY["User supplies it on the template"]
    CONSENT -->|granted| FOUND["Search → show result →<br/><b>user confirms before use</b>"]
    FOUND -->|ambiguous or empty| SUPPLY
    FOUND -->|confirmed| REC["Entity record<br/><i>verifier uses this to tell an allowed<br/>business address from a personal one</i>"]

    SOLE["<b>Sole practitioner?</b><br/>practice named after a person<br/>= natural person, follows the tier"]

    classDef floor fill:#5a2d2d,stroke:#c66,color:#fde
    classDef ent fill:#2d4a2d,stroke:#6a6,color:#dfd
    class FLOOR,SOLE floor
    class ENT,REC ent
```

Upgrading tier mid-session is free and redacts retroactively. Downgrading
takes one confirmation, because it means re-entering what the user chose to
withhold — and the tool never suggests a downgrade to speed up the interview.
Interview fatigue is not consent.

---

## 3. Where questions come from, and which are optional

```mermaid
flowchart LR
    subgraph REQUIRED["REQUIRED — not skippable"]
        FF["<b>Form fields</b><br/>pvq-map.yaml ∪ sf86-map.yaml<br/><i>PVQ is the collection standard<br/>for every user</i>"]
        RD["<b>Reporting data elements</b><br/>ISL 2021-02 / SEAD 3 App. A<br/><i>per matched table entry</i>"]
    end

    subgraph OPTIONAL["OPTIONAL — declinable"]
        CL["<b>Guideline checklists</b><br/>corpus/checklists/guideline-X.yaml"]
        UN["<b>Universal elements</b><br/>How many know · coercion exposure<br/>delay · pattern · changes made"]
        PM["<b>Precedent Miner</b><br/>denials → what absence looks like<br/>grants → what completeness looks like"]
    end

    FF --> GA["<b>Gap Analyst</b><br/>assigns criticality<br/>by source"]
    RD --> GA
    CL --> GA
    UN --> GA
    PM --> GA

    GA --> INT["<b>Interviewer</b>"]

    INT --> R1["Required unanswered →<br/><b>marked to-follow</b><br/>appears in STILL REQUIRED"]
    INT --> R2["Optional declined →<br/><b>narrative stays silent</b><br/>never filled with filler"]

    SEV["<b>Severity</b><br/>from severity_default"] -.->|"scales depth of"| OPTIONAL
    SEV -.->|"CANNOT downgrade"| REQUIRED

    classDef req fill:#5a2d2d,stroke:#c66,color:#fde
    classDef opt fill:#2d4a2d,stroke:#6a6,color:#dfd
    class FF,RD req
    class CL,UN,PM opt
```

A minor-in-possession is low severity and still needs the court, the date, the
disposition, the fine amount, and whether it was paid in full. **Severity buys
brevity on context, never on the form.**

Sensitivity is a separate axis: Section 19's counseling questions are both
sensitive *and* required. Sensitivity governs how gently it's asked;
criticality governs what happens if it's absent.

---

## 4. Trust gates

Because the tool is model-agnostic, no platform enforces that an agent only
read `/corpus`. Prompt restrictions are requests. **The scripts are the
control.**

```mermaid
flowchart TD
    M["<b>Model-authored</b><br/>narrative only"] --> ASM

    ASM["<b>assemble_package.py</b><br/>template-driven — a model never touches these:<br/>substitution checklist · crosswalk · STILL REQUIRED<br/>Information You Will Need · Person N template<br/>disclaimer · corpus version"]

    ASM --> VER["<b>verify_output.py</b>"]

    VER --> C1{"Case number not<br/>in index.json?"}
    VER --> C2{"SSN or DOB anywhere?<br/>Person data beyond tier,<br/>unmatched by an entity record?"}
    VER --> C3{"Person N with no<br/>template entry?"}
    VER --> C4{"Template field<br/>pre-filled?"}
    VER --> C5{"Outcome prediction or<br/>concealment language?"}
    VER --> C6{"Disclaimer or version<br/>missing?"}
    VER --> C7{"Unanswered required field<br/>not shown in package?"}

    C1 & C2 & C3 & C4 & C5 & C6 & C7 -->|any yes| FAIL

    FAIL["<b>HARD STOP</b><br/>exit 1 — do not deliver<br/>fix and re-run"]
    PASS(["<b>Deliver</b><br/>+ standing reminder: no script detects<br/>tonal minimization. The user must read it."])

    C1 & C2 & C3 & C4 & C5 & C6 & C7 -->|all no| PASS

    classDef fail fill:#5a2d2d,stroke:#c66,color:#fde
    classDef ok fill:#2d4a2d,stroke:#6a6,color:#dfd
    class FAIL fail
    class PASS ok
```

---

## 5. What grounds each agent

Every citation resolves to a file. Nothing is recalled from model memory.

```mermaid
flowchart LR
    subgraph CORPUS["/corpus — ships in the repo (authored)"]
        RP["reporting/<br/>structured tables · authority-layers"]
        FM["forms/<br/>pvq-map · sf86-map<br/>collection-policy · preambles"]
        CK["checklists/<br/>13 guidelines + _UNIVERSAL"]
    end

    subgraph LIB["DCSA Library — downloaded separately (published)"]
        S4["SEAD 3 · SEAD 4 · ISLs · 32 CFR<br/>ROBOT_READABLE_DIRECTORY/TEXT"]
        DH["10,658 DOHA decisions<br/>DOHA_CURRENT_PATHS.jsonl<br/><i>era · outcome · guidelines in case_stem</i>"]
    end

    RP --> RA["Requirements Advisor"]
    S4 --> CLS["Classifier"]
    CK --> GAP["Gap Analyst"]
    FM --> GAP
    DH --> PM["Precedent Miner"]
    DH --> VFY["verify_output.py<br/><i>citation check</i>"]

    UNV["<b>maintainer_verified: false</b>"] -.->|"forces"| DEGRADE["Requirements Advisor<br/>returns CONSULT FSO<br/>Agents may not cite"]

    classDef unver fill:#4a3a1a,stroke:#ca6,color:#fed
    class UNV,DEGRADE unver
```

**Everything ships unverified.** Until a human checks a corpus file against
its official source, agents treat it as uncitable and reportability degrades
to "ask your FSO." The scaffold is honest about being a scaffold.

---

## 6. Case retrieval

```mermaid
flowchart LR
    Q["Guidelines G, J<br/>+ fact summary"] --> IDX["index.json<br/><i>generated, never hand-edited</i>"]
    IDX --> FLT["Filter by guideline tag"]
    FLT --> RNK["Rank by facts_tags overlap"]
    RNK --> SPL{"Split by outcome"}
    SPL -->|denials| D["What was <b>absent</b><br/>→ questions that close gaps"]
    SPL -->|grants| G["What was <b>established</b><br/>→ questions that invite substance"]
    D --> OUT["Candidate questions<br/><i>criticality: mitigation only</i>"]
    G --> OUT

    FN["Filename<br/>ISCR-24-01234_GJ_denied_hearing.md"] -.->|"must agree with"| FMT["frontmatter<br/>guidelines: [G, J]"]
    FMT -.->|"disagreement =<br/>build failure"| VAL["validate_corpus.py"]
```

Precedent never creates a **required** element — only the form and the
reporting tables do that. And no rate, tendency, or likelihood ever reaches
the user: the corpus is contested SOR cases, a selection-biased sample that
says nothing about how ordinary reports resolve.
