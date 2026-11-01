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

## Mode 1b — Local session, hosted reference

The user's own assistant runs the session exactly as in Mode 1, but reads its
reference material from the project's hosted MCP server at
`https://fsotools.ai/adverse/mcp` instead of a DCSA Library on disk. The
server is a **reference service, not a session service** (design:
`docs/HOSTED-MCP-DESIGN.md`). It answers the questions the local scripts
answer from disk — a guideline's text, a reporting table, a published
decision — and nothing else.

**What can be promised:** the narrative is still not stored, logged or
transmitted by this project. The server never receives it: no tool accepts a
string the user could have typed. Every input is a value from a closed set
the server publishes (a guideline letter, an access tier, a population, an
event id, a form name, a state code, a decision id the server returned), and
anything else is rejected by name without echoing what was sent. The server
keeps no session, issues no session id, writes no logs (`observability` is
off, it has no writable binding), and sets `cache-control: no-store` on every
tool response. Every file it serves is copied from an approved DCSA Library
release or from this repository and verified against a hash manifest on
load; a file that fails is never served. Maintainer-authored files are served
with their `maintainer_verified` flag exactly as the repository carries it,
so an unverified table degrades to "consult your security office" hosted or
not. The agents, the session state and the deterministic gates stay on the
user's machine.

**What must still be disclosed:**

- The categorical queries themselves reveal the *shape* of the matter to the
  server ("Guideline G and J", "ts_q", "industry"). A user who wants to reveal
  nothing can have the client call `get_corpus_bundle` once at intake, which
  fetches the whole reference layer, and query decisions only by choice.
- The client's IP address reaches Cloudflare at the edge and keys the rate
  limiter (60 requests a minute, shared across every tool). Cloudflare's zone
  analytics may count requests outside the Worker's control. The promise is
  scoped to "this server keeps no logs and no state", which is checkable from
  the Worker's configuration and code in `mcp/`.
- As in Mode 1, the text goes to whichever model provider the user configured.

**Stage 1 language:** "Running locally. Nothing you type is stored or
transmitted by this tool. When I need reference material — a guideline's text,
a reporting table, a published decision — I ask fsotools.ai for it by category
(a guideline letter, an event type), never in your words, and that server
keeps no logs. Your words do go to the model provider you've configured, under
their terms."

**Clients that cannot run scripts.** A chat window or a custom connector with
no shell can run the served prompts and tools but cannot run
`verify_output.py`. Its package is unverified, and the served `conductor`
prompt says so in the user's first interaction and again at handoff. There is
no hosted `verify_package`, and there never will be: it would be the first
tool to receive the narrative (owner decision D3).

**Operator notes.** The Worker is `adverse-information-assistant` in
`mcp/wrangler.jsonc`. `python scripts/hosted_release.py --library "<library
root>"` rebuilds the served release from an approved library release and this
checkout; it refuses an unapproved release, fetches nothing, flips no verified
flag and runs the test suite first. Deploys happen from the owner's machine
with `npm run mcp:worker:deploy`; `--deploy` on the build script does the same
and then confirms the live `get_release` reports the new ids. Nothing under
`agents/` or `scripts/` may depend on `mcp/`; `tests/run_tests.py` enforces
it, because the local tool must keep working with no network at all.

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
documentation bug. That includes the hosted reference server: a change to
`mcp/` that widens what the server accepts, stores or logs changes Mode 1b's
promise and must change this file in the same commit.
