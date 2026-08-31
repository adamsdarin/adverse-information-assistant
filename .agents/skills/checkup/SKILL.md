---
name: checkup
description: Verify the project is healthy — run the test suite, validate the corpus, and check the DCSA Library. Use before committing, before publishing, or when something seems wrong.
---

# Project health check

Run these in order and report the results plainly. Do not fix anything yet —
report first, then ask what to address.

```bash
python tests/run_tests.py
python scripts/validate_corpus.py
python scripts/check_corpus.py
python scripts/check_library.py
```

How to read it:

- **Tests: any FAIL** — stop. Do not commit or publish. Report the full output.
- **validate_corpus: ERROR** — genuinely broken; the message names the file.
- **validate_corpus: WARN** — expected. Corpus and court entries ship
  unverified until a human checks them against an official source.
- **check_library: not found** — the tool still runs but cannot cite anything.
  Say so; do not offer to download it.
- **check_library: CASE MISMATCH or broken claims** — issues in the library
  itself. Report them; they break macOS and Linux users.

Finish with a one-line verdict: safe to commit, or not, and why.
