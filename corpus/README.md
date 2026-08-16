# Corpus

The corpus is the only source the agents may cite. **The repo ships structure
and templates, not full official texts** — populating verbatim text from the
official sources is a maintainer task, deliberately manual so a human verifies
every load-bearing word. AI-generated "recollections" of directives or cases
must never be committed here; that would rebuild the hallucination risk this
architecture exists to remove.

| Directory | Content | Official source |
|-----------|---------|-----------------|
| `sead4/` | The 13 adjudicative guidelines, verbatim | dni.gov (SEAD 4) |
| `doha/cases/` | Curated published DOHA decisions | doha.ogc.osd.mil |
| `reporting/` | SEAD 3 / ISL 2021-02 / 32 CFR §117.8 texts + structured tables | dni.gov, dcsa.mil, eCFR |
| `forms/` | Guideline ↔ form-section crosswalks | eApp/SF-86, PVQ |
| `checklists/` | Per-guideline required narrative elements (maintainer-authored) | derived; see each file's `sources` |

## Workflow

1. Copy the `_TEMPLATE` file in the target directory.
2. Paste verbatim text from the official source; fill all frontmatter fields,
   including `source_url` and `retrieved` date.
3. Run `python scripts/validate_corpus.py` — commit only on a clean pass.
4. Run `python scripts/build_index.py` to regenerate `doha/index.json`
   (never hand-edit the index).

## Case curation criteria

Published ISCR decisions only (hearing and appeal); factual diversity per
guideline; **both favorable and unfavorable outcomes represented** so the
corpus never implies a predictable result; every file links to the official
published decision.

## Versioning

`corpus/VERSION` holds the corpus snapshot identifier recorded in every
deliverable footer. Bump it on any corpus change.
