---
name: report
description: Starts an adverse-information reporting session that helps a clearance holder prepare a self-report for their security office. Use when the user wants help preparing a self-report or says they have something to report.
---

# Run a reporting session

Read `agents/conductor.md` and run the session it describes exactly as written, in its stage order, using the agent prompt files in `agents/core/` and `agents/optional/` for each step. The conductor owns every session rule, including locating the reference material, the capability canary, `output/session.json` validation, the `verify_output.py` gate, and the hash handoff.
