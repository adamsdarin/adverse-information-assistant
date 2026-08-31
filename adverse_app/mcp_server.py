"""Narrow optional MCP facade for trusted local operations."""
from __future__ import annotations

from pathlib import Path

from . import core


def create_server(session_path: Path):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise core.SessionError("The optional MCP SDK is not installed. Install the project's MCP extra before using this command.") from exc

    mcp = FastMCP("Adverse Information Assistant", instructions="Local-only tools over a validated adverse-information session. Never request classified information, SSNs, dates of birth, or the user's real name.")

    @mcp.tool()
    def session_status() -> dict:
        """Return compact progress without exposing narrative content."""
        return core.status(session_path)

    @mcp.tool()
    def next_intake_question() -> dict:
        """Return the one currently approved intake question."""
        data = core.read_session(session_path)
        question = core.next_question(data)
        return {"complete": question is None, "key": None if question is None else question.key, "prompt": None if question is None else question.prompt}

    @mcp.tool()
    def answer_intake_question(answer: str) -> dict:
        """Save one answer, validate immediately, and return compact progress."""
        core.answer_intake(answer, session_path)
        return core.status(session_path)

    @mcp.tool()
    def validate_session() -> dict:
        """Run the deterministic state gate."""
        ok, detail = core.validate(session_path)
        return {"valid": ok, "detail": detail}

    @mcp.tool()
    def assemble_package() -> dict:
        """Assemble canonical Markdown after session validation."""
        package, detail = core.assemble(session_path)
        return {"package": str(package.resolve()), "detail": detail}

    @mcp.tool()
    def verify_package() -> dict:
        """Run the hard delivery gate and return the canonical SHA-256."""
        digest, detail = core.verify(session_path)
        return {"sha256": digest, "detail": detail}

    return mcp


def run(session_path: Path) -> None:
    create_server(session_path).run(transport="stdio")

