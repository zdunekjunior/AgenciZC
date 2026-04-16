from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_admin_panel_requires_login(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    # /admin should show login screen when not authenticated
    r = client.get("/admin")
    assert r.status_code == 200
    assert "Admin login" in r.text or "Logowanie" in r.text

    # admin API endpoints should be blocked
    r2 = client.get("/drafts/pending")
    assert r2.status_code == 401


def test_login_allows_access_and_logout_revokes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_PANEL_PASSWORD", "pw")
    from app.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    # login wrong
    bad = client.post("/admin/login", json={"password": "nope"})
    assert bad.status_code == 403

    ok = client.post("/admin/login", json={"password": "pw"})
    assert ok.status_code == 200
    assert "admin_session" in ok.headers.get("set-cookie", "")

    # now we can access protected endpoints
    p = client.get("/drafts/pending")
    assert p.status_code == 200

    a = client.get("/audit/events?limit=5")
    assert a.status_code == 200

    # logout
    lo = client.post("/admin/logout")
    assert lo.status_code == 200

    # access should be blocked again
    p2 = client.get("/drafts/pending")
    assert p2.status_code == 401

