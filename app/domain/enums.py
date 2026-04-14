from __future__ import annotations

from enum import Enum


class Category(str, Enum):
    sales_inquiry = "sales_inquiry"
    support = "support"
    complaint = "complaint"
    invoice = "invoice"
    meeting_request = "meeting_request"
    partnership = "partnership"
    other = "other"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RecommendedAction(str, Enum):
    draft_for_review = "draft_for_review"
    ask_human = "ask_human"
    ignore = "ignore"


class SuggestedTool(str, Enum):
    none = "none"
    web_research = "web_research"

