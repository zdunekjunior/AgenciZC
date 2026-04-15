from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Protocol, TypeVar

TIn = TypeVar("TIn")
TOut = TypeVar("TOut")


class AgentStatus(str, Enum):
    ok = "ok"
    error = "error"
    skipped = "skipped"


@dataclass(frozen=True)
class AgentError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRun(Generic[TOut]):
    agent_name: str
    status: AgentStatus
    output: TOut | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[AgentError] = field(default_factory=list)


class Agent(Protocol[TIn, TOut]):
    """
    Common contract for all agents in the system.
    """

    name: str

    def run(self, input: TIn) -> AgentRun[TOut]:
        raise NotImplementedError

