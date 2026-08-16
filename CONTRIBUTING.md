# Contributing

## Priorities (in order)

1. **Correctness bugs** — wrong reporting channel, wrong ISL table application,
   wrong timeline, misattributed SEAD 4 condition. File immediately; these are
   prioritized above all feature work.
2. **Bounce reports** — you're an FSO/SSO/practitioner and you know something
   agencies routinely come back for that our checklists miss. Use the
   bounce-report issue template. This is how the checklists converge on real
   failure modes.
3. **Corpus contributions** — curated DOHA case files and updated guidance.
4. Features.

## Corpus rules (non-negotiable)

- Every DOHA case file MUST link to the official published decision
  (`source_url` on doha.ogc.osd.mil) and pass `scripts/validate_corpus.py`.
- Guideline and reporting-requirement text must be verbatim from the official
  source, with the source and version recorded in frontmatter.
- Both favorable and unfavorable outcomes must stay represented per guideline —
  the corpus must never imply a predictable result.
- **Never commit any real person's report, narrative, or identifying details.**
  Test fixtures are synthetic only. PRs containing anything that looks like a
  real adverse-information narrative will be closed unmerged.

## Agent prompt changes

Changes to `agents/*.md` that touch guardrails (candor rules, escalation
triggers, verification checks, disclaimer blocks) require a fixture in
`tests/fixtures/` demonstrating the behavior.
