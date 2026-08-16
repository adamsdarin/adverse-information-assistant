---
name: report
description: Start an adverse-information reporting session. Use when the user wants help preparing a self-report for their security office, or says they have something to report.
---

# Run a reporting session

Read `agents/conductor.md` and run the session it describes, exactly as
written. Follow the stage order. Use the agent prompt files in `agents/core/`
and `agents/optional/` as the instructions for each step.

Non-negotiable for this session:

- Locate the corpus and the DCSA Library first, and say plainly what you found
  and what is unavailable as a result.
- Run the capability canary before any real content is entered.
- Cite only what exists on disk. Never fetch anything.
- Maintain `output/session.json` and validate it after every stage.
- Before showing any final package, run `scripts/verify_output.py`. Do not
  present output that fails it.
- At handoff, give the user the exact `verify_output.py` command to run
  themselves and the SHA-256 the script printed, so they can confirm the file
  they have is the file that passed.
