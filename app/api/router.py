from fastapi import APIRouter

from app.api.routes.agent import router as agent_router
from app.api.routes.admin import router as admin_router
from app.api.routes.audit import router as audit_router
from app.api.routes.drafts import router as drafts_router
from app.api.routes.cases import router as cases_router
from app.api.routes.gmail import router as gmail_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.leads import router as leads_router
from app.api.routes.sales import router as sales_router
from app.api.routes.professor import router as professor_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(agent_router, prefix="/agent", tags=["agent"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(audit_router, prefix="/audit", tags=["audit"])
api_router.include_router(drafts_router, prefix="/drafts", tags=["drafts"])
api_router.include_router(cases_router, prefix="/cases", tags=["cases"])
api_router.include_router(leads_router, prefix="/leads", tags=["leads"])
api_router.include_router(gmail_router, prefix="/gmail", tags=["gmail"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(sales_router, prefix="/sales", tags=["sales"])
api_router.include_router(professor_router, prefix="/professor", tags=["professor"])

