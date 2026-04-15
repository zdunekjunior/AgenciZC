from __future__ import annotations

from enum import Enum


class DraftApprovalStatus(str, Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    sent = "sent"

