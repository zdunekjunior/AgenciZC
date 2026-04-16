from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse

from app.auth.admin_auth import (
    ADMIN_SESSION_COOKIE,
    login_admin,
    logout_admin,
    require_admin_session,
)
from app.config import Settings, get_settings
from pydantic import BaseModel, Field

router = APIRouter()


def _admin_dir() -> Path:
    # app/api/routes/admin.py -> app/web/admin/
    return Path(__file__).resolve().parents[2] / "web" / "admin"


@router.get("", response_class=HTMLResponse)
def admin_index(
    settings: Settings = Depends(get_settings),
    session_id: str | None = Cookie(default=None, alias=ADMIN_SESSION_COOKIE),
) -> HTMLResponse:
    # If not authenticated, show login screen.
    try:
        require_admin_session(settings=settings, session_id=session_id)  # type: ignore[arg-type]
    except HTTPException:
        login = _admin_dir() / "login.html"
        if not login.exists():
            raise HTTPException(status_code=404, detail="Admin UI not found")
        return HTMLResponse(login.read_text(encoding="utf-8"))

    index = _admin_dir() / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Admin UI not found")
    return HTMLResponse(index.read_text(encoding="utf-8"))


@router.get("/assets/{asset_path:path}")
def admin_asset(asset_path: str) -> FileResponse:
    base = _admin_dir() / "assets"
    target = (base / asset_path).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Invalid asset path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(path=str(target))


class AdminLoginRequest(BaseModel):
    password: str = Field(..., min_length=1)


@router.post("/login")
def admin_login(payload: AdminLoginRequest, response: Response = None, settings: Settings = Depends(get_settings)):  # type: ignore[assignment]
    login_admin(response=response, password=payload.password, settings=settings)
    return {"ok": True}


@router.post("/logout")
def admin_logout(
    response: Response = None,  # type: ignore[assignment]
    session_id: str | None = Cookie(default=None, alias=ADMIN_SESSION_COOKIE),
):
    logout_admin(response=response, session_id=session_id)
    return {"ok": True}

