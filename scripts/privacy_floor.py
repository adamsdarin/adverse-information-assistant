#!/usr/bin/env python3
"""The privacy floor: what no privacy tier relaxes. Part of the trust anchor.

Three things never enter this tool, at any tier, in the session file or the
package: a Social Security number, a date of birth, and classified material.
An SSN and a date of birth go directly on the form; classified material does
not belong on an unaccredited system at all.

One definition, imported by validate_session.py (the session file) and
verify_output.py (the package), so the two gates cannot disagree about what
counts. Stdlib only.

Every finding is a LABEL, never the matched text. A message that echoed an
SSN would copy it into a terminal, a log, or a model's context window, which
is the leak this module exists to prevent.

What a pattern cannot do, stated rather than hidden: it cannot read meaning.
An SSN typed as nine bare digits with no label, a date of birth written in
words, or classified content with its markings stripped all pass. Markings
are matched in the forms classified text carries when copied (banner lines
with "//", portion marks such as "(S)" opening a paragraph, and the
classification authority block). A plain description such as "a Secret
document" is ordinary reporting language and never matches.
"""
from __future__ import annotations

import re

# 000-12-3456, 000 12 3456 or 000.12.3456 (one separator used throughout), or
# nine digits right after an SSN label.
SSN_RE = re.compile(
    r"\b\d{3}([-. ])\d{2}\1\d{4}\b"
    r"|\b(?:SSN|SSAN|social\s+security(?:\s+(?:number|no\.?|#))?)(?![A-Za-z])"
    r"(?:\s+(?:is|was))?\s*[:#-]?\s*\d{9}\b",
    re.I,
)

# A DATE-OF-BIRTH LABEL FOLLOWED BY AN ACTUAL DATE. The label alone appears in
# the package's own privacy boilerplate ("no date of birth appears in this
# document"), so matching the phrase would fail every clean package.
_DATE = (
    r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{4}-\d{1,2}-\d{1,2}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
    r"|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})"
)
DOB_RE = re.compile(
    r"\b(?:date\s+of\s+birth|birth\s*date|d\.?o\.?b\b\.?|born(?:\s+on)?\b)"
    r"(?:\s+(?:is|was|of|on))?\s*[:\-]?\s*" + _DATE,
    re.I,
)

# Classification markings in the forms copied classified text carries.
# Case-sensitive on purpose: markings are uppercase, prose is not.
CLASSIFICATION_RE = re.compile(
    # Banner or portion with controls: TOP SECRET//SCI, SECRET//NOFORN, S//NF
    r"\b(?:TOP\s+SECRET|SECRET|CONFIDENTIAL|TS|S|C)\s*//\s*[A-Z]"
    # A portion mark opening a paragraph or sentence: (S) ..., (TS//SI) ...
    r"|(?:^|(?<=\s))\((?:TS|S|C)(?://[A-Z][A-Z0-9 ,/-]*)?\)(?=\s)"
    # The classification authority block
    r"|(?i:\b(?:classified\s+by|declassify\s+on)\s*:)",
    re.M,
)

FLOOR = (
    ("ssn", SSN_RE, "a Social Security number"),
    ("dob", DOB_RE, "a date of birth"),
    ("classification", CLASSIFICATION_RE, "a classification marking"),
)


def violations(text: str) -> list[tuple[str, str]]:
    """(key, label) for every floor rule the text breaks. Never the match."""
    if not isinstance(text, str) or not text:
        return []
    return [(key, label) for key, rx, label in FLOOR if rx.search(text)]
