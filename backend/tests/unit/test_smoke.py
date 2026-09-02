"""
Smoke tests - verify app and config import cleanly.
Feature tests are added alongside their tasks (AUTH-02, CAP-08, etc.)
"""
from app.core.config import settings
from app.main import app


def test_settings_load():
    """Config loads with correct defaults."""
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.is_sqlite is True
    assert settings.APP_ENV == "development"


def test_app_created():
    """FastAPI app instantiates correctly."""
    assert app.title == "NiyamDrishti API"


def test_routes_registered():
    """All three routers are mounted (check via openapi schema keys)."""
    from fastapi.testclient import TestClient
    client = TestClient(app)
    paths = list(app.openapi()["paths"].keys())
    assert any("/auth" in p for p in paths)
    assert any("/inspections" in p for p in paths)
    assert any("/rule-packs" in p for p in paths)
