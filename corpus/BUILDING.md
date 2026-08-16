# Building the Corpus Yourself

Two ways to get a corpus: download the maintainer's, or build your own from
the official sources. This is the second one.

**The tool will not do this for you.** No agent downloads, scrapes, or crawls
corpus content — see `never_auto_fetch` in `corpus-sources.yaml`. Government
sites change structure and block automated access, so a scraping tool works
until it silently doesn't. More importantly, the entire design rests on a
*human* having checked each file against its source. Auto-fetched content is
unverified content wearing a verified file's name, which is worse than nothing
because an empty corpus announces itself and a scraped one doesn't.

So this is manual work. Copy, paste, read, verify. Budget real hours.

---

## Build it OUTSIDE the repository

The repo ships the corpus **skeleton** — empty templates, your checklists, the
table structure. The populated corpus is distributed separately (Google Drive)
and lives wherever each user puts it. So do this work in its own folder:

```powershell
Copy-Item -Recurse -Force "path\to\repo\corpus" "$HOME\corpus-aia"
cd "path\to\repo"
python scripts\check_corpus.py "$HOME\corpus-aia" --remember
```

Every script now resolves that folder, and prints which corpus it used on each
run. The repo's own `corpus/` stays empty — and `tests/run_tests.py` fails if
populated content ever appears there, so the mistake gets caught before a push
rather than after.

---

## Marking something verified requires proof

`maintainer_verified: true` (and `verbatim: true` for SEAD 4 texts) is a claim
that a human checked this file against its official source. Since anyone can
type `true`, that claim now has to carry provenance or `validate_corpus.py`
errors:

```yaml
maintainer_verified: true
source_url: "https://www.dni.gov/..."      # where the official document lives
source_sha256: "9f86d081884c7d65..."       # from scripts/hash_source.py
verified_date: "2026-08-16"                # when you checked
```

Get the hash from the exact file you read:

```powershell
python scripts\hash_source.py "$HOME\Downloads\SEAD-4.pdf"
```

This is what makes verification auditable: anyone can fetch the same official
document, hash it, and confirm you checked the same bytes. Without it, a fork
could flip every flag to `true` and nobody could tell.

---

## Do it in this order

Each stage makes the tool measurably more useful. Stop whenever you have
enough for your purposes — a partial corpus is a supported state.

| Stage | Effort | What it unlocks |
|---|---|---|
| 1. Reporting authorities | 2–4 hrs | Reportability answers instead of "ask your security office" |
| 2. SEAD 4 guidelines | 2–3 hrs | Guideline text can be quoted |
| 3. Form maps | 1–2 hrs | Field-level completeness checking |
| 4. DOHA cases | ongoing | Precedent-derived interview questions |

---

## Stage 1 — Reporting authorities

**Get SEAD 3.** Go to dni.gov, find Security Executive Agent Directive 3.
Open `corpus/reporting/sead-3.md`, paste the full text below the frontmatter
including **Appendix A**, and set `verbatim: true` and the `retrieved` date.

Appendix A matters more than the rest — it's the list of data elements each
report type requires, and it's what makes the gap analyst able to tell a
complete report from a thin one.

**Get ISL 2021-02.** From dcsa.mil. Paste into
`corpus/reporting/isl-2021-02.md`. Record the exact version — ISLs get
revised, and the bundled reference is the May 2024 v2.

**Get 32 CFR § 117.8.** From ecfr.gov. Paste §117.8 into
`corpus/reporting/32cfr117-8.md` with the retrieval date. eCFR content changes
by rulemaking, so the date is the version.

**Then do the attribution split.** This is the fiddly part and the one that
matters most. `corpus/reporting/tables/*.yaml` currently hold entries
extracted from the ISL, which both *restates* SEAD 3 and *adds* to it. Go
entry by entry and add:

```yaml
authority: sead-3        # or isl-2021-02, or both
```

deciding from the **SEAD 3 text**, not from the ISL. Then set
`attribution_status: complete` in `reporting/authority-layers.yaml`.

Until that's done, federal and military users get "check with your security
office" on every match, because the tool can't tell whether a given
requirement binds them or only contractors.

Finally, read each table against its source and flip `maintainer_verified:
true`. Until you do, the tool will not assert that anything *is* reportable.

---

## Stage 2 — SEAD 4 guidelines

From dni.gov, get SEAD 4. For each of the thirteen files in `corpus/sead4/`:

1. Open it. There are three sections: the Concern, the disqualifying
   conditions, and the mitigating conditions.
2. Paste each **verbatim**, preserving the official numbering and lettering.
   The checklists reference those numbers — `G-23` means Guideline G's
   mitigating conditions — so paraphrasing breaks the link.
3. Set `verbatim: true` and `retrieved`.

Do not summarize. Do not "clean up" the language. The value of this file is
that it is the actual text.

---

## Stage 3 — Form maps

`corpus/forms/pvq-map.yaml` is populated from the PVQ (Final, September 2023),
but **the guideline mapping in it is editorial inference, not something the
form states.** Which SEAD 4 guideline a PVQ section serves was a judgment
call. Review those mappings, correct them, then set `maintainer_verified:
true`.

`sf86-map.yaml` has a skeleton of field lists derived from the public
structure of the SF-86. Verify against the current form and eApp before
trusting it. Wrong field lists produce confidently incomplete reports, which
is the exact failure this tool exists to prevent.

---

## Stage 4 — DOHA cases

This is open-ended and the most valuable per hour once the rest is done.

From **doha.ogc.osd.mil**, browse published ISCR decisions. For each one you
want to add:

1. Read it. Actually read it — the curated summary is the thing agents quote,
   and a summary written from the first paragraph will mislead.
2. Copy `corpus/doha/cases/_TEMPLATE.md`.
3. Name it per `corpus/doha/NAMING.md`:
   `ISCR-24-01234_GJ_denied_hearing.md` — case number, adjudicated guidelines
   uppercase and alphabetized, outcome, level.
4. Fill the frontmatter. `guidelines` is the guidelines the judge **actually
   analyzed**, not everything the SOR alleged.
5. Write the summary: facts, what the judge focused on, what the applicant
   established or failed to establish, the holding.
6. `source_url` must point at the official published decision. The validator
   fails the build without it.

### What to select for

**Both outcomes, deliberately.** A corpus of denials produces a defensive,
fear-shaped interview. A corpus of grants produces a credulous one. Denials
show what absence looks like; grants show what a complete record looks like.
Aim for a real mix per guideline.

**Factual diversity over volume.** Ten cases spanning different fact patterns
in Guideline G beat forty single-incident OWIs. The corpus exists to generate
*questions*, and forty near-identical cases generate one question.

**Never a rate or a tendency.** Published DOHA decisions are contested SOR
cases — a selection-biased sample that says nothing about how ordinary reports
resolve. Nothing in a summary should support a sentence like "cases like this
usually…". If you catch yourself writing one, cut it.

### After adding cases

```bash
python scripts/build_index.py
python scripts/validate_corpus.py
```

Never hand-edit `index.json` — it's generated, and the validator will catch
you.

---

## Check your work

```bash
python scripts/check_corpus.py ./corpus
```

It reports guideline coverage, case counts by outcome, table verification
status, and — most usefully — **what each gap costs a session**. Run it after
each stage to see what you bought.

---

## Keeping it current

Guidance changes. ISLs get revised, 32 CFR Part 117 gets amended, SEAD
directives get reissued. Nothing in this repo notices.

Bump `corpus/VERSION` on every change, because the deliverable footer records
it — which means a report produced last year can be traced to the guidance it
was actually built against. That traceability is worth more than it looks the
first time someone asks why a package says what it says.
