---
title: "SEAD 3 — Reporting Requirements for Personnel with Access to Classified Information or Who Hold a Sensitive Position"
issued_by: "Security Executive Agent (ODNI)"
source_url: "https://www.dni.gov/files/NCSC/documents/Regulations/SEAD-3-Reporting-U.pdf"
version: "TODO — record exact version"
retrieved: TODO
verbatim: false
applies_to: all_covered_individuals
populations: [industry, federal_civilian, military]
---

# THIS IS THE BASELINE LAYER — IT APPLIES TO EVERYONE

SEAD 3 binds **every covered individual across the executive branch**:
cleared contractors, federal civilian employees, and military members alike.

It is not a DCSA document and it is not industry-specific. DCSA's ISL 2021-02
is one agency's *implementation* of SEAD 3 for NISP contractors, layered on
top of this. A federal employee is fully subject to SEAD 3 and simply not
subject to the ISL.

See `../authority-layers.yaml` for how the two layers combine.

## Maintainer task — this is the highest-priority corpus gap

Paste verbatim SEAD 3 text below, including **Appendix A** (reportable data
elements), which the gap analyst references for report-type data
requirements.

Then attribute the structured entries in `./tables/`: each currently carries
content extracted from ISL 2021-02, which both restates SEAD 3 and adds to it.
Add `authority: sead-3 | isl-2021-02 | both` to every entry, sourced from
**this** text rather than inferred from the ISL. Until that is done, federal
and military users degrade to `consult_fso` on every match — the requirement
is still stated to them, but the tool cannot confirm which layer it comes from.

<PASTE verbatim SEAD 3 text here.>
