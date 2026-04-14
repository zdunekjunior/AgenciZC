from fastapi import FastAPI

from app.api.router import api_router
from app.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(level=settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )
    app.include_router(api_router)
    return app


app = create_app()

