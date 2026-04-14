from fastapi import APIRouter

from app.api.routes.agent import router as agent_router
from app.api.routes.gmail import router as gmail_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(agent_router, prefix="/agent", tags=["agent"])
api_router.include_router(gmail_router, prefix="/gmail", tags=["gmail"])

