from __future__ import annotations

from enum import Enum


class CompanyRole(str, Enum):
    secretary = "SecretaryAgent"
    sales = "SalesAgent"
    development = "DevelopmentAgent"
    professor = "ProfessorAgent"
    finance = "FinanceAgent"

