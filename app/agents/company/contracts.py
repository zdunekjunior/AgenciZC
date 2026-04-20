from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.cases.models import CaseContext


@dataclass(frozen=True)
class CaseAgentInput:
    case: CaseContext


@dataclass(frozen=True)
class CaseAgentOutput:
    """
    Generic output envelope for case-oriented agents.

    Concrete agents should return structured payloads inside `artifacts` and `notes`.
    """

    notes: list[str]
    decisions: list[str]
    artifacts: dict[str, Any]


class CaseAgent(Protocol):
    name: str

    def run(self, input: CaseAgentInput) -> CaseAgentOutput:
        raise NotImplementedError

