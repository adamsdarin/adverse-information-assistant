"""Vendor-neutral boundary for hosts that execute specialist prompts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class HostRequest:
    agent_prompt: Path
    session_path: Path
    user_message: str


@dataclass(frozen=True)
class HostResponse:
    text: str
    structured: dict | None = None


class ModelHost(Protocol):
    """A host implementation runs one stateless specialist turn."""

    def run(self, request: HostRequest) -> HostResponse: ...

