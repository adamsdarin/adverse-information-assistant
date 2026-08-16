# Capability canary — answer BEFORE opening canary-answer.json

This is a competence smoke test the conductor runs at session start, before
any real user content. Produce your determination for the scenario below
**first**, then open `tests/fixtures/canary-answer.json` and compare. If any
field differs, tell the user the model failed the check and may not be
reliable for this tool. Do not look at the answer file before answering —
the check only means something if you didn't.

## Scenario

A cleared contractor employee (NISP industry, baseline eligibility, current
holder — not an applicant) says:

> "Two weeks ago I was arrested for driving while intoxicated after a work
> event. I blew a 0.14. I haven't told anyone at work yet. I've never been
> asked about it on any form and nobody has asked me about it since."

## Produce this JSON

```json
{
  "reportable": "...",          // "yes" or "consult_fso" — never anything else
  "channel_family": "...",      // "industry" or "federal"
  "guidelines_must_include": [],// the SEAD 4 letters clearly implicated
  "e_attach": false,            // should Guideline E auto-attach?
  "delay_explanation_needed": false,
  "timeliness_warning": false   // must the user be told to contact their
                                // security office today, out loud?
}
```

Reason it out fully before you peek. The point of the E and delay fields:
this person has made no false statement on any form — distinguish a late
self-report from concealment.
