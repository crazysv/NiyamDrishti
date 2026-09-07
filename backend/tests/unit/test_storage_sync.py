from unittest.mock import MagicMock, patch

import pytest

from app.db.session import check_db_health, normalize_database_url
from app.services.storage import (
    delete_file,
    generate_presigned_download_url,
    generate_presigned_upload_url,
)


def test_sqlite_url_normalization():
    """Verify SQLite database URL keeps local check_same_thread=False setting (STOR-02)."""
    url, kwargs, _ = normalize_database_url("sqlite+aiosqlite:///./test.db")
    assert url == "sqlite+aiosqlite:///./test.db"
    assert "connect_args" in kwargs
    assert kwargs["connect_args"].get("check_same_thread") is False


def test_neon_postgres_url_normalization():
    """Verify Neon Postgres connection string is converted to asyncpg and configured for serverless (STOR-02)."""
    neon_url = "postgresql://alex:secret@ep-cool-pool.ap-southeast-1.neon.tech/neondb?sslmode=require"
    normalized_url, kwargs, connect_args = normalize_database_url(neon_url)

    assert normalized_url.startswith("postgresql+asyncpg://")
    assert "sslmode" not in normalized_url  # stripped from query string
    assert connect_args.get("ssl") is True  # passed via connect_args for asyncpg
    assert kwargs["pool_pre_ping"] is True  # Neon scale-to-zero protection
    assert kwargs["pool_recycle"] == 300  # 5 min idle recycle


@pytest.mark.asyncio
async def test_db_health_check():
    """Verify check_db_health executes SELECT 1 successfully (STOR-02)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    with patch("app.db.session.AsyncSessionLocal", TestSession), patch("app.db.session.engine", test_engine):
        health = await check_db_health()
        assert health["status"] == "connected"
        assert "dialect" in health
        assert health["is_serverless_ready"] is True

    await test_engine.dispose()


def test_r2_presigned_download_url_generation():
    """Verify Cloudflare R2 presigned download URL generation (STOR-01)."""
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://mock-r2.cloudflarestorage.com/signed-url"

    with (
        patch("app.services.storage.get_r2_client", return_value=mock_s3),
        patch("app.services.storage.settings.R2_BUCKET_NAME", "test-bucket"),
    ):
        signed = generate_presigned_download_url("inspections/123/images/front.jpg", expires_in=1800)
        assert signed == "https://mock-r2.cloudflarestorage.com/signed-url"
        mock_s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "inspections/123/images/front.jpg"},
            ExpiresIn=1800,
        )


def test_r2_presigned_upload_url_generation():
    """Verify Cloudflare R2 presigned PUT upload URL generation (STOR-01)."""
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://mock-r2.cloudflarestorage.com/upload-signed"

    with (
        patch("app.services.storage.get_r2_client", return_value=mock_s3),
        patch("app.services.storage.settings.R2_BUCKET_NAME", "test-bucket"),
    ):
        res = generate_presigned_upload_url("inspections/456/evidence.jpg", content_type="image/jpeg", expires_in=600)
        assert res["upload_url"] == "https://mock-r2.cloudflarestorage.com/upload-signed"
        assert res["is_local"] is False
        assert res["storage_key"] == "inspections/456/evidence.jpg"


def test_storage_local_fallback_when_r2_unconfigured():
    """Verify storage falls back cleanly to local URL when R2 is not configured."""
    with patch("app.services.storage.get_r2_client", return_value=None):
        local_dl = generate_presigned_download_url("/uploads/123/front.jpg")
        assert local_dl == "/uploads/123/front.jpg"

        upload_info = generate_presigned_upload_url("123/front.jpg")
        assert upload_info["is_local"] is True
        assert "/api/v1/uploads/" in upload_info["upload_url"]


def test_delete_file_local(tmp_path):
    """Verify local file deletion works."""
    dummy_file = tmp_path / "test_delete.txt"
    dummy_file.write_text("hello")
    assert dummy_file.exists()

    with patch("app.services.storage.get_r2_client", return_value=None):
        success = delete_file(str(dummy_file))
        assert success is True
        assert not dummy_file.exists()
