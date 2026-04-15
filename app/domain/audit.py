from __future__ import annotations

from enum import Enum


class EntityType(str, Enum):
    email = "email"
    draft = "draft"
    thread = "thread"
    workflow = "workflow"


class ActorType(str, Enum):
    system = "system"
    human = "human"
    agent = "agent"
    orchestrator = "orchestrator"

