from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import Cookie, Depends, HTTPException, Response

from app.config import Settings, get_settings


ADMIN_SESSION_COOKIE = "admin_session"
SESSION_TTL = timedelta(hours=12)


@dataclass
class Session:
    session_id: str
    created_at: datetime
    expires_at: datetime


class InMemoryAdminSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def _now(self) -> datetime:
        return datetime.now(tz=timezone.utc)

    def create(self) -> Session:
        now = self._now()
        sid = secrets.token_urlsafe(32)
        s = Session(session_id=sid, created_at=now, expires_at=now + SESSION_TTL)
        self._sessions[sid] = s
        return s

    def delete(self, *, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def is_valid(self, *, session_id: str | None) -> bool:
        if not session_id:
            return False
        s = self._sessions.get(session_id)
        if s is None:
            return False
        if s.expires_at < self._now():
            self._sessions.pop(session_id, None)
            return False
        return True


@lru_cache(maxsize=1)
def get_admin_store() -> InMemoryAdminSessionStore:
    return InMemoryAdminSessionStore()


def _configured_password(settings: Settings) -> str:
    pw = (settings.admin_panel_password or "").strip()
    if not pw:
        # Force explicit configuration in any non-dev scenario.
        raise HTTPException(status_code=503, detail="Admin panel password not configured")
    return pw


def login_admin(*, response: Response, password: str, settings: Settings) -> None:
    configured = _configured_password(settings)
    if not secrets.compare_digest(password, configured):
        raise HTTPException(status_code=403, detail="Invalid password")
    store = get_admin_store()
    s = store.create()
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=s.session_id,
        httponly=True,
        samesite="lax",
        secure=False,  # ready to harden on HTTPS deployment
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )


def logout_admin(*, response: Response, session_id: str | None) -> None:
    if session_id:
        get_admin_store().delete(session_id=session_id)
    response.delete_cookie(key=ADMIN_SESSION_COOKIE, path="/")


def require_admin_session(
    settings: Settings = Depends(get_settings),
    session_id: str | None = Cookie(default=None, alias=ADMIN_SESSION_COOKIE),
) -> None:
    _configured_password(settings)
    if not get_admin_store().is_valid(session_id=session_id):
        raise HTTPException(status_code=401, detail="Admin auth required")

