from __future__ import annotations

from dataclasses import dataclass

from app.schemas.leads import LeadRecord


@dataclass(frozen=True)
class CRMHandoffInput:
    lead: LeadRecord


@dataclass(frozen=True)
class CRMHandoffResult:
    status: str  # queued|skipped|error
    external_id: str | None = None
    note: str = ""


class CRMHandoffService:
    """
    Stub foundation for future CRM integrations.
    """

    def handoff(self, input: CRMHandoffInput) -> CRMHandoffResult:
        return CRMHandoffResult(status="skipped", external_id=None, note="CRMHandoffService is not implemented yet")

