"""Command-line interface for the local product shell."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import core


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="adverse", description="Local guided runner for the Adverse Information Assistant")
    ap.add_argument("--session", type=Path, default=core.DEFAULT_SESSION)
    sub = ap.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="start a new local session")
    start.add_argument("--privacy", choices=("high", "medium", "low"), help="record an explicit privacy selection at start")
    start.add_argument("--force", action="store_true", help="replace the exact session file named by --session")
    sub.add_parser("resume", help="show the next intake question and recovery status")
    answer = sub.add_parser("answer", help="answer the current intake question")
    answer.add_argument("text")
    sub.add_parser("status", help="show compact session status")
    sub.add_parser("validate", help="run the deterministic session gate")
    assemble = sub.add_parser("assemble", help="assemble the canonical Markdown package")
    assemble.add_argument("--output", type=Path)
    verify = sub.add_parser("verify", help="run the hard output gate")
    verify.add_argument("--package", type=Path)
    web = sub.add_parser("web", help="start the local browser interface")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    sub.add_parser("mcp", help="start the narrow local MCP server over stdio")
    return ap


def emit(value: object) -> None:
    if isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    ns = parser().parse_args(argv)
    try:
        if ns.command == "start":
            core.start(ns.session, ns.privacy, ns.force)
            emit(core.status(ns.session))
        elif ns.command in {"resume", "status"}:
            emit(core.status(ns.session))
        elif ns.command == "answer":
            core.answer_intake(ns.text, ns.session)
            emit(core.status(ns.session))
        elif ns.command == "validate":
            ok, detail = core.validate(ns.session)
            emit(detail)
            return 0 if ok else 1
        elif ns.command == "assemble":
            path, detail = core.assemble(ns.session, ns.output)
            emit({"package": str(path.resolve()), "detail": detail})
        elif ns.command == "verify":
            digest, detail = core.verify(ns.session, ns.package)
            emit({"sha256": digest, "detail": detail})
        elif ns.command == "web":
            from .web import serve
            serve(ns.session, ns.host, ns.port)
        elif ns.command == "mcp":
            from .mcp_server import run
            run(ns.session)
        return 0
    except core.SessionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
