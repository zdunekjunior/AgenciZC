from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter()


def _admin_dir() -> Path:
    # app/api/routes/admin.py -> app/web/admin/
    return Path(__file__).resolve().parents[2] / "web" / "admin"


@router.get("", response_class=HTMLResponse)
def admin_index() -> HTMLResponse:
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

