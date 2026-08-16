#!/usr/bin/env python3
"""Regenerate corpus/doha/index.json from case-file frontmatter.

Usage: python scripts/build_index.py [--corpus PATH]
Requires: pyyaml
"""
import json
import sys
from pathlib import Path

import yaml

import corpus_paths

_cli = [a for a in sys.argv[1:] if not a.startswith("--")]
_corpus_flag = None
if "--corpus" in sys.argv:
    _corpus_flag = sys.argv[sys.argv.index("--corpus") + 1]
CORPUS = corpus_paths.require(_corpus_flag or (_cli[0] if _cli else None))
CASES = CORPUS / "doha" / "cases"
INDEX = CORPUS / "doha" / "index.json"
VERSION_FILE = CORPUS / "VERSION"


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path.name}: missing YAML frontmatter")
    _, fm, _ = text.split("---", 2)
    return yaml.safe_load(fm)


def main() -> int:
    cases = []
    for path in sorted(CASES.glob("*.md")):
        if path.name.startswith("_"):  # skip templates
            continue
        fm = parse_frontmatter(path)
        cases.append(
            {
                "case_no": fm["case_no"],
                "path": str(path.relative_to(CORPUS)),
                "decided": str(fm["decided"]),
                "guidelines": fm["guidelines"],
                "outcome": fm["outcome"],
                "level": fm["level"],
                "facts_tags": fm.get("facts_tags", []),
                "source_url": fm["source_url"],
            }
        )
    version = VERSION_FILE.read_text(encoding="utf-8").split()[0] if VERSION_FILE.exists() else "unknown"
    INDEX.write_text(
        json.dumps(
            {
                "_comment": "GENERATED FILE — run scripts/build_index.py. Never hand-edit.",
                "corpus_version": version,
                "cases": cases,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Indexed {len(cases)} case(s) -> {INDEX}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
