from django.db import connection


def test_health_needs_no_login_and_checks_the_database(api, db):
    response = api.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_503_when_the_database_is_down(api, db, monkeypatch):
    def broken_cursor():
        raise RuntimeError("database gone")

    # Undo the patch before teardown: the test database's own cleanup needs a working cursor.
    with monkeypatch.context() as patch:
        patch.setattr(connection, "cursor", broken_cursor)
        response = api.get("/api/health/")
    assert response.status_code == 503  # a probe must see "not ready", not a 500 crash
    assert response.json()["database"] == "unavailable"
