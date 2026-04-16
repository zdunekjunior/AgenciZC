from __future__ import annotations

from enum import Enum


class LeadTemperature(str, Enum):
    cold = "cold"
    warm = "warm"
    hot = "hot"


class BusinessIntent(str, Enum):
    offer = "offer"
    partnership = "partnership"
    implementation = "implementation"
    support = "support"
    recruitment = "recruitment"
    other = "other"


class SalesPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

