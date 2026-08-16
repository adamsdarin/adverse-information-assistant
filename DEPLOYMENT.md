# Deployment Modes and What Each One Can Honestly Promise

Privacy in this tool is a **property of how it is deployed**, not a property
of the software. The same prompts and corpus produce very different privacy
realities depending on where they run. Any build MUST state its own mode at
Stage 1, in the user's first interaction, before any narrative is collected.

Misstating this is the most serious failure this project can commit. A
clearance holder deciding whether to type an undisclosed matter into a tool
is relying on that statement.

---

## Mode 1 — Local (the default, and what the README describes)

The user clones the repo and runs it in a local agentic environment (Claude
Code / Cowork, Codex, Antigravity, Cursor) against their own model provider.

**What can be promised:** the narrative is not stored by this project, not
logged by this project, and not transmitted anywhere by this project. Files
are written only on explicit request, only to `output/`, which is gitignored.

**What must still be disclosed:** the text is sent to whichever model provider
the user has configured, under that provider's terms. This tool has no control
over and makes no promises about that provider. If the user's environment has
telemetry, session recording, or an employer-managed configuration, that is
outside this project's control and the user should know it.

**Stage 1 language:** "Running locally. Nothing you type is stored or
transmitted by this tool. Your words do go to the model provider you've
configured, under their terms — not to me, and not to your employer through
me."

---

## Mode 2 — Hosted / Enterprise (e.g. an AWS build for an organization)

An organization stands this up as a service for its cleared population.

**What CANNOT be promised:** local-only handling. The narrative leaves the
user's machine by definition. Depending on architecture, the hosting
organization — very possibly the user's own employer — may be able to access,
log, retain, or subpoena it.

**Required before a hosted build ships:**

1. **Stage 1 disclosure naming the operator.** Who runs this, what is
   retained, for how long, and who can read it. Written plainly, not in a
   terms-of-service register.
2. **A different privacy section in that build's README.** The local-mode
   language in this repo's README must not survive into a hosted build. Delete
   it; do not soften it.
3. **A stated retention policy**, including whether drafts persist after a
   session and whether an FSO or administrator can retrieve them.
4. **An explicit answer to "can my employer see this?"** — because a user
   drafting a disclosure about an undisclosed matter will assume no unless
   told otherwise, and that assumption may be wrong.
5. **Consider whether the tool should exist in this mode at all** for the
   individual-user flow. A tool where an employee's not-yet-submitted
   adverse-information draft is visible to their employer is a materially
   different product from the one this repo describes, and the individual may
   reasonably decline to use it. An FSO-facing hosted deployment — where the
   security officer is the user and identity is already known — carries none
   of that problem and may be the better enterprise shape.

**Stage 1 language template:** "This instance is operated by <ORG>. What you
type here is transmitted to and stored by <ORG> under their retention policy.
<Who> can access it. If you would rather draft this without your employer
being able to see it, use the local version of this tool instead."

---

## Rule for maintainers

Any fork, port, or repackaging that changes where the data goes MUST update
the Stage 1 disclosure in the same commit. A build whose privacy claims do
not match its architecture should be treated as a security defect, not a
documentation bug.
