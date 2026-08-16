#!/usr/bin/env python3
"""Compute the SHA-256 of an official source document, for provenance.

When you verify a corpus file against its official source (the SEAD 4 PDF
from dni.gov, the ISL PDF from dcsa.mil, a DOHA decision page you saved),
record three things in the corpus file's frontmatter before setting the
verified flag:

  source_url:    where the official document lives
  source_sha256: the output of this script, run on YOUR SAVED COPY of it
  verified_date: the date you checked

validate_corpus.py refuses a verified flag that lacks any of these — a
verification claim without provenance is an unauthenticated flag anyone can
flip in a fork. The hash makes the claim auditable: anyone can download the
source, hash it, and confirm you verified against the same bytes.

Usage: python scripts/hash_source.py <file> [<file> ...]
"""
import hashlib
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: hash_source.py <file> [<file> ...]")
        return 1
    rc = 0
    for arg in sys.argv[1:]:
        p = Path(arg.strip().strip('"').strip("'")).expanduser()
        if not p.is_file():
            print(f"ERROR: {p} is not a file")
            rc = 1
            continue
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        print(f"source_sha256: {h.hexdigest()}   # {p.name}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
