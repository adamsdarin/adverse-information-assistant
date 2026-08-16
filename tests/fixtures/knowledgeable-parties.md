# Fixture: knowledgeable-parties handling — SYNTHETIC

Locks in the rule that no third party's identity ever enters the tool.

## Expected interview behavior

1. "How many people are aware of this?" — a number only, no names.
2. If zero: note it without alarm, and make sure `coercion-exposure` is asked.
3. If more than zero: ask **role only** ("my supervisor", "the arresting
   agency"), assign `Person 1`, `Person 2`, ..., and tell the user they'll
   complete a template themselves at submission.
4. If the user volunteers a name anyway: do not record it. Map it to the
   Person label and continue.

## Expected package

- Narrative refers to `Person 1` / `Person 2` with roles inline.
- A "Knowledgeable Parties — COMPLETE BEFORE SUBMISSION" section with one
  blank block per person.
- The ACTION REQUIRED header lists both substitutions: `John Doe` → legal
  name, and completing the template.

## Verifier must FAIL when

| Defect | Expected failure |
|---|---|
| Any template field pre-filled | `Template field '<x>' is pre-filled` |
| Phone/email/SSN anywhere in the package | `<x> found (...)` |
| `Person 3` referenced with no template entry | `'Person 3' is referenced but has no template entry` |
| Persons referenced but no template section at all | `ships no completion template` |

## Reproduce

```bash
python scripts/assemble_package.py tests/fixtures/session-owi.json > /tmp/p.md
python scripts/verify_output.py /tmp/p.md          # PASS
sed -i 's|- Full name: _*|- Full name: Jane Smith|' /tmp/p.md
python scripts/verify_output.py /tmp/p.md          # FAIL, exit 1
```
