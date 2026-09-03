"""Pytest global configuration and hermetic fixtures for NiyamDrishti backend."""

import pytest
from app.core.config import settings


@pytest.fixture(autouse=True)
def force_local_storage_and_offline_rules(monkeypatch):
    """
    Hermetic test isolation:
    - Forces local filesystem storage so tests run offline without external S3 network calls.
    - Ensures ACTIVE_RULE_PACK_VERSION defaults to standard 2026.02.01.
    """
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "")
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "R2_ENDPOINT_URL", "")
    monkeypatch.setattr(settings, "ACTIVE_RULE_PACK_VERSION", "2026.02.01")

    from app.core.rate_limit import limiter
    limiter.enabled = False
