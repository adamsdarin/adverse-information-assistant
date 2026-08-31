# Adverse Information Assistant — Product Requirements Document

**Status:** Draft for review  
**Research date:** August 29, 2026  
**Product posture:** Local-first, privacy-preserving, model-agnostic guided reporting assistant  
**Canonical workflow:** `agents/conductor.md`

## 1. Executive summary

The project already contains its most valuable and difficult intellectual property: a source-controlled reporting workflow, structured reporting and adjudicative checklists, privacy rules, resumable session state, and deterministic gates that stop unsafe or unverifiable output.

The fastest useful product is therefore not a large new application. Version 1 should package the existing workflow as a small local guided-session runner that:

- starts or resumes a session;
- asks one plain-language question at a time;
- saves and validates the session after every stage;
- shows progress and outstanding required facts;
- assembles and verifies the final Markdown package; and
- never bypasses the existing local corpus, DCSA Library controls, or deterministic scripts.

The research found strong reusable components, but no existing open-source product reproduces the whole system. `docassemble` is the closest functional analogue. SurveyJS and Form.io solve dynamic form rendering, LangGraph solves durable agent workflows, Microsoft Presidio adds defense-in-depth PII detection, and the MCP Python SDK can expose the project's deterministic functions to multiple AI hosts. These are candidates to borrow from or integrate later, not reasons to replace the existing trust architecture.

## 2. Problem statement

A clearance holder or applicant who has decided to disclose adverse or reportable information must navigate several separate problems:

- determine which reporting rules and channels apply;
- understand what facts the government will require;
- disclose complete facts without concealment or minimization;
- avoid exposing unnecessary third-party information;
- preserve progress through a stressful, potentially long interview;
- distinguish required facts from optional adjudicative context;
- produce a coherent package without fabricated authority or outcome predictions; and
- verify the result before signing or submission.

General-purpose chatbots, survey builders, legal interview tools, and agent frameworks each solve part of this. None identified in this research combines the project's clearance-specific rules, verified local source boundary, privacy-tier behavior, cyclical matter expansion, candor checks, citation verification, and hard delivery gate.

## 3. Product vision

Provide a calm, local-first guided workflow that helps John Doe prepare a complete, candid, source-grounded self-report for personal verification and submission to the appropriate security office.

The product does not adjudicate, predict outcomes, provide legal advice, or submit a report on the user's behalf.

## 4. Product principles

1. **Deterministic controls outrank model behavior.** The model may draft and converse; fixed code validates state, privacy rules, citations, and delivery readiness.
2. **Local sources are authoritative.** The application does not fetch government guidance or case material. Missing local sources produce a visible limitation, not a silent web fallback.
3. **One fact per question.** The interface is conversational prose, not a menu or a dense questionnaire.
4. **The user controls scope and privacy.** Thread expansion requires consent. Third-party data follows the selected privacy tier.
5. **Resume is a core feature.** A crash or context-window loss must not force the user to repeat the interview.
6. **Required and optional facts remain distinct.** A shorter interview may reduce optional depth, never required fields.
7. **Warn, never halt—except at delivery gates.** The workflow surfaces concerns and lets the user continue; invalid or unsafe output is not delivered.
8. **Model and host portability.** Core rules live in files, schemas, and scripts rather than one vendor's orchestration product.

## 5. Users

### Primary user

A clearance holder or applicant who has already decided to disclose and wants help preparing a complete, candid report.

### Secondary user

A maintainer who updates reporting tables, checklists, agent prompts, schemas, tests, and source-library compatibility.

### Future user

An FSO or security professional who may deploy the tool internally, subject to a separate security, records-management, and authorization review. This is not a Version 1 user.

## 6. Jobs to be done

- When I need to make a self-report, help me understand the applicable reporting path without predicting the outcome.
- Help me capture the complete account once and preserve it unchanged as the candor baseline.
- Ask only questions grounded in the applicable form, reporting requirement, or adjudicative criteria.
- Tell me what is required, what is optional, what remains unanswered, and how far I have progressed.
- Let me stop and safely resume later.
- Produce a package I can review, correct, complete, and verify before I sign or submit it.
- Prevent accidental inclusion of prohibited personal data, unsupported citations, or prohibited language.

## 7. Existing product assets to preserve

- `agents/conductor.md` as the generative workflow definition.
- Stateless specialist prompts and their schema contracts.
- `output/session.json` as the session source of truth.
- Narrative stamping and append-only `stage_log` behavior.
- Local corpus and separately installed DCSA Library.
- Section-scoped directive loading through `scripts/sead_lookup.py`.
- Deterministic validation, assembly, corpus, library, and output verification scripts.
- Privacy tiers and Person-N substitution model.
- Reporting-first, adjudicative-second sequencing.
- Checklist coverage across who, what, when, where, why, how, and future intent.
- Thread detection and consent before expanding into another matter.

## 8. Research landscape

| Candidate | Relevant capabilities | Fit | Recommendation |
|---|---|---|---|
| [docassemble](https://github.com/jhpyle/docassemble) | Python/YAML guided interviews, rule-based question flow, saved sessions, APIs, document assembly, CLI tooling | Closest end-to-end analogue; proven in legal self-help, but operationally large and opinionated | Use as a design reference and evaluate a prototype adapter in Phase 3; do not make it a V1 dependency |
| [Suffolk LIT Lab Document Assembly Line](https://github.com/SuffolkLITLab/docassemble-AssemblyLine) | Reusable guided-interview patterns, form automation, testing and document workflows on docassemble | Strong implementation reference for accessible legal interviews and automated tests | Borrow testing and UX patterns; avoid inheriting court-filing assumptions |
| [A2J Author](https://www.a2jauthor.org/content/welcome-a2j-author) | Guided interviews plus document templates for self-represented users | Useful precedent for plain-language, nontechnical authoring; not a natural fit for agentic, local-source reasoning | UX reference only |
| [SurveyJS](https://github.com/surveyjs/survey-library) | MIT-licensed JSON-defined multi-page forms, branching, validation, autosave, partial submission, accessible input types | Strong future browser renderer, but conventional forms can conflict with one-fact-per-question prose | Consider for Phase 2 only if configured as a single-question conversational surface |
| [Form.io](https://github.com/formio/formio.js) | Form renderer/builder, conditional logic, JSON Logic, APIs | Capable, but heavier and less aligned with the current local Python trust anchor | Do not adopt for V1; reconsider only if nontechnical form authorship becomes a priority |
| [Typebot](https://github.com/baptisteArno/typebot.io) | Self-hosted conversational flows, inputs, branching, embeds and APIs | Attractive conversational UI; AGPL and a separate runtime add operational and licensing complexity | UX inspiration; no near-term dependency |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Durable execution, checkpoints, human-in-the-loop interrupts, stateful long-running graphs | Maps well to the conductor's cyclical workflow and crash recovery | Evaluate in Phase 3 after the native state machine is stable; avoid coupling V1 to an agent framework |
| [transitions](https://github.com/pytransitions/transitions) | Lightweight Python finite and hierarchical state machines with conditional transitions | Small, local, testable match for an explicit conductor state machine | Good V1 candidate, but a plain typed transition table may be even simpler initially |
| [Pydantic](https://github.com/pydantic/pydantic) | Typed Python validation and JSON Schema generation | Useful typed boundary around the existing JSON Schema state | Adopt selectively; retain standards-based schema validation as the canonical compatibility gate |
| [python-jsonschema](https://github.com/python-jsonschema/jsonschema) | Standards-based JSON Schema validation | Direct fit with current schema contracts | Continue or adopt as the canonical runtime schema validator |
| [Microsoft Presidio](https://github.com/microsoft/presidio) | Customizable PII detection, redaction and anonymization for text and structured data | Useful additional warning layer; cannot guarantee complete detection | Add as optional defense-in-depth in Phase 3, never as the sole privacy gate |
| [python-docx-template](https://github.com/elapouya/python-docx-template) | Word templates driven by Jinja-like variables | Practical future `.docx` output while preserving fixed templates | Phase 3 export option after Markdown remains canonical and verified |
| [Typst CLI](https://github.com/typst/typst) | Deterministic markup-to-PDF compilation with a local CLI | Good PDF generation option with reproducible templates | Phase 3 candidate for human-readable PDF exports |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Typed tools, resources, prompts, structured outputs, local stdio and HTTP transports | Strong portability layer for exposing trusted scripts and approved local resources to AI hosts | Phase 2: build a narrow local MCP server around deterministic functions, not around raw unrestricted file access |

### Research conclusion

There is no credible “install one package and get this app” option. The closest product, docassemble, covers interview and assembly mechanics but not the project's source-verification model or clearance-specific safety controls. The most economical path is a thin Python product shell around the existing repository, followed by optional standards-based adapters.

## 9. Proposed architecture

### V1 architecture

- **Interface:** local CLI with a calm conversational presentation.
- **Orchestrator:** small explicit Python state machine that reads `agents/conductor.md`-derived stage definitions and calls the existing agents or host model.
- **State:** existing `output/session.json`, validated after every stage.
- **Knowledge:** repository corpus plus the user's separately installed DCSA Library; no network fallback.
- **Rules and gates:** existing scripts invoked as subprocesses with structured results.
- **Output:** canonical verified Markdown package plus checksum and user handoff instructions.
- **Model boundary:** adapter interface so one supported host can ship first and others can follow.

### Later architecture

- Optional local browser UI over the same session engine.
- Narrow MCP server exposing safe functions and scoped local resources.
- Optional durable graph adapter if real usage shows the native state machine is insufficient.
- Optional Word and PDF renderers that consume only a verified canonical package.

## 10. Phased delivery plan

## Phase 1 — Quick win: local guided runner

**Goal:** Turn the current repository workflow into a usable, resumable product without changing its policy logic.

### Phase 1A — Vertical slice

Support one well-covered, unclassified, single-matter scenario end to end using the existing workflow and test fixtures.

Required capabilities:

- `start`, `resume`, `status`, `validate`, and `assemble` commands;
- corpus and library readiness check at start;
- capability canary before user reliance;
- privacy-tier capture;
- open narrative capture followed by immediate narrative stamping;
- explicit stage state and append-only stage log;
- reporting determination, classification, checklist selection, and one-question-at-a-time gap loop;
- progress line showing matter count and required/optional facts remaining;
- final assembly and hard verification gate;
- readable failure messages with the exact recovery action;
- no network access except the already constrained, consent-based entity lookup when separately enabled.

**Phase 1A success criterion:** A maintainer can run the fixture and one manual test session from start to verified package, stop midway, resume without repeating captured facts, and observe all existing tests passing.

### Phase 1B — Complete current workflow coverage

- multiple matters and thread expansion;
- prior-disclosure handling;
- essentials versus thorough pacing;
- privacy-tier changes and Person-N mapping workflow;
- optional specialist passes;
- partial-library degradation;
- recovery from interrupted or invalid state;
- complete error and audit event vocabulary.

**Explicitly out of Phase 1:** accounts, cloud hosting, FSO dashboards, analytics, automated submission, collaborative editing, mobile apps, generalized form builders, and a new policy authoring system.

## Phase 2 — Better interface and interoperability

**Goal:** Make the validated engine easier to use without duplicating its rules.

- Local browser interface with one question per screen, progress, pause/resume, and final review.
- Narrow MCP server exposing operations such as session status, next approved question, validate state, assemble package, verify package, and scoped source lookup.
- Model adapters for at least two hosts.
- Export/import of a portable session bundle with clear plaintext warnings.
- Accessibility testing and keyboard-only operation.
- Structured telemetry that is local and opt-in; never records narrative content by default.

**Phase 2 gate:** CLI and browser UI must produce equivalent validated session state and byte-equivalent canonical package content for the same fixture.

## Phase 3 — Document quality and stronger defenses

**Goal:** Improve handoff quality and operational confidence.

- Optional `.docx` and PDF rendering from the verified canonical package.
- Additional PII warning pass using custom Presidio recognizers, while retaining deterministic pattern checks.
- Visual source/citation crosswalk for maintainers.
- Broader scenario and model eval suite.
- Evaluate LangGraph only if native orchestration shows measurable recovery or observability gaps.
- Evaluate a docassemble adapter only if organizations require a traditional hosted guided-interview deployment.

## Phase 4 — Organizational deployment, only after separate review

- authenticated multi-user deployment;
- encryption and key management;
- retention and deletion policy controls;
- role-based access and deployment administration;
- security assessment, threat model, privacy impact assessment, records-management review, and authorization boundary;
- deployment-specific audit logging that does not expose more adverse information than necessary.

Automated government submission remains out of scope unless an authorized interface, legal authority, and explicit product decision exist.

## 11. Phase 1 functional requirements

### Session lifecycle

- The user can start a new session only when no unfinished session would be overwritten.
- The user can resume from the last valid completed stage.
- Every state mutation is followed by schema validation.
- The narrative is stamped once and cannot be edited afterward.
- The append-only stage log detects shrinkage or rewriting.
- Status identifies the current stage, next action, matter count, and missing required facts without exposing unnecessary narrative text.

### Interview behavior

- The application asks one fact per turn in prose.
- Every question carries an internal source and criticality classification.
- Required questions cannot be silently skipped.
- Optional declined questions remain absent rather than receiving generated filler.
- The interface explains why a question is needed when requested.
- Thread expansion occurs only after the user agrees.
- Classified-information and emergency triage rules are evaluated at the prescribed checkpoints.

### Source handling

- The product checks the repository corpus and separately installed DCSA Library.
- Directive text is loaded only by the existing section-scoped lookup mechanism.
- Missing material produces the prescribed degraded behavior.
- No product feature downloads or silently substitutes authority.
- Citations must resolve to local files before delivery.

### Output and verification

- Assembly uses a fixed template and an explicit output argument.
- Verification is mandatory and blocks delivery on failure.
- The result includes the substitution checklist, crosswalk, outstanding requirements, information-to-obtain list, Person-N template where applicable, disclaimer, source version, and checksum instructions.
- The user is reminded that they verify every fact and sign or submit the report themselves.

## 12. Nonfunctional requirements

### Privacy and security

- Local-only operation is the default.
- No SSN, date of birth, or classified information is accepted.
- Session files are clearly disclosed as plaintext and unencrypted in V1.
- Logs exclude narrative and answer content by default.
- File access is restricted to the project, configured library, and explicit output location.
- Network access is denied by default and separately consented for the limited entity-search case.

### Reliability

- A process interruption after any completed stage loses no validated progress.
- Re-running validation and assembly is idempotent for unchanged state.
- A failed gate returns nonzero and never produces a deliverable marked ready.
- The regression suite passes before release.

### Portability

- Windows is the first supported platform because it matches the current project environment.
- Core logic remains Python and filesystem based.
- Model-host integration is isolated behind an adapter.
- The canonical state and output formats remain vendor-neutral.

### Usability

- Plain language suitable for a stressed non-lawyer.
- No adjudicative predictions, moralizing, or legal deferral.
- Progress is visible at every interview round.
- Errors state what happened, what was preserved, and what the user should do next.

## 13. Success metrics

V1 metrics should be measurable locally without collecting user narratives:

- 100% of release fixtures pass state validation, package assembly, output verification, and regression tests.
- 100% of interrupted fixture sessions resume without repeating a completed answer.
- 0 verified packages contain a known prohibited identifier from the privacy test corpus.
- 0 verified packages contain unresolved citations or hidden unanswered required fields.
- Median maintainer setup-to-first-successful-fixture run is under 10 minutes on a supported machine.
- A representative single-matter session reaches a verified package with no manual JSON editing.
- At least 90% of usability-test participants can identify current progress, outstanding required facts, and the fact that they—not the tool—must verify and submit the report.

The product must not measure or report adjudicative success rates.

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A model bypasses or misunderstands workflow instructions | Keep state transitions, source selection, and delivery gates deterministic |
| A large framework obscures trust boundaries | Ship a thin native runner first; add adapters only behind the same validated engine |
| Users mistake the package for legal advice or a government decision | Preserve disclaimers and prohibit predictions throughout UI and output |
| Sensitive data persists on disk | Loud plaintext disclosure, minimal collection, Person-N placeholders, deletion guidance, no content telemetry |
| Automated PII detection misses an identifier | Treat NLP detection as an additional warning layer, never the only gate |
| Conventional form UI encourages picking instead of explaining | One-question conversational screen, free-text first, no menu-shaped disclosure prompts |
| Policy sources become stale or missing | Continue local manifest checks, version disclosure, verified flags, and `consult_fso` degradation |
| MCP exposes excessive local content or actions | Publish a narrow allowlist of typed tools and scoped resources; no unrestricted filesystem resource |
| Word/PDF rendering diverges from verified Markdown | Keep Markdown canonical; render only after verification and compare required sections post-render |

## 15. Key decisions for review

1. Approve a **CLI-first local product** for Phase 1 rather than a browser application.
2. Approve the **existing Markdown package as the canonical verified output** through Phase 2.
3. Approve a **thin explicit state machine** before evaluating LangGraph.
4. Approve **MCP as a Phase 2 interoperability layer**, not the primary application runtime.
5. Approve **docassemble as a benchmark and possible later adapter**, not the foundation of V1.
6. Choose the first Phase 1A scenario from the best-covered existing fixture set; the current OWI single-incident fixture is the default candidate.

## 16. Recommended immediate backlog

1. Define the small CLI contract and stage transition table.
2. Wrap existing scripts in a consistent structured-result interface without changing their policy behavior.
3. Implement `start`, `resume`, `status`, `validate`, and `assemble`.
4. Complete the OWI vertical slice using the current session schema and fixtures.
5. Add interruption/resume and no-manual-JSON end-to-end tests.
6. Run the full project checkup and conduct a short maintainer usability pass.
7. Review Phase 1A findings before committing to a browser UI, MCP server, or orchestration framework.

## 17. Release acceptance criteria for Phase 1A

Phase 1A is releasable only when:

- the corpus check and configured library check are visible at session start;
- the canary runs before user reliance and records its result;
- the session can stop and resume from at least three different workflow points;
- no completed answer must be re-entered after resume;
- the narrative stamp rejects later mutation;
- each state change passes schema validation;
- the selected single-matter fixture completes without manual state editing;
- assembly and verification pass using the fixed commands;
- a deliberately injected privacy, citation, required-field, and prohibited-language defect each blocks delivery;
- the full regression suite passes; and
- the output clearly identifies itself as user-verified preparation assistance, not adjudication or legal advice.

