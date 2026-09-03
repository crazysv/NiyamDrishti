import base64
import os
import uuid
from pathlib import Path

from app.core.config import settings

# Default local uploads directory
UPLOAD_DIR = Path("./uploads")


def parse_data_url(data_url: str) -> tuple[str, bytes]:
    """
    Parses a base64 Data URL (e.g. data:image/jpeg;base64,...) into file extension and raw bytes.
    """
    if "," in data_url:
        header, encoded = data_url.split(",", 1)
        ext = "jpg"
        if "image/png" in header:
            ext = "png"
        elif "image/webp" in header:
            ext = "webp"
        raw_bytes = base64.b64decode(encoded)
        return ext, raw_bytes
    raise ValueError("Invalid Data URL format")


def get_r2_client():
    """Returns a boto3 S3 client configured for Cloudflare R2 if credentials exist, else None."""
    if (
        settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
        and settings.R2_ENDPOINT_URL
    ):
        try:
            import boto3

            return boto3.client(
                "s3",
                endpoint_url=settings.R2_ENDPOINT_URL,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",
            )
        except Exception:
            return None
    return None


async def save_image_bytes(
    inspection_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
) -> str:
    """
    Saves an image either to local filesystem (dev/offline) or Cloudflare R2.
    Returns the storage URL or relative path.
    """
    client = get_r2_client()
    if client and settings.R2_BUCKET_NAME:
        key = f"inspections/{inspection_id}/images/{filename}"
        client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
            Body=file_bytes,
            ContentType="image/jpeg",
        )
        if settings.R2_PUBLIC_BASE_URL:
            return f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{key}"
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key},
            ExpiresIn=86400,
        )

    # Local file storage
    inspection_dir = UPLOAD_DIR / str(inspection_id)
    os.makedirs(inspection_dir, exist_ok=True)

    file_path = inspection_dir / filename
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    return f"/uploads/{inspection_id}/{filename}"


async def save_report_bytes(
    inspection_id: uuid.UUID,
    report_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    content_type: str = "application/pdf",
) -> str:
    """
    Saves an inspection report (PDF or editable JSON) to Cloudflare R2 (prod)
    or local filesystem (dev/offline). Returns the storage URL (RPT-03, STOR-01).
    """
    client = get_r2_client()
    if client and settings.R2_BUCKET_NAME:
        key = f"inspections/{inspection_id}/reports/{filename}"
        client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        if settings.R2_PUBLIC_BASE_URL:
            return f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{key}"
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key},
            ExpiresIn=86400,
        )

    # Local file storage fallback
    report_dir = UPLOAD_DIR / str(inspection_id) / "reports"
    os.makedirs(report_dir, exist_ok=True)

    file_path = report_dir / filename
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    return f"/uploads/{inspection_id}/reports/{filename}"


def generate_presigned_download_url(
    storage_url_or_key: str,
    expires_in: int = 3600,
) -> str:
    """
    Generates a secure, time-limited presigned GET URL for Cloudflare R2 (STOR-01).
    If storage is local filesystem, returns the relative URL directly.
    """
    client = get_r2_client()
    if not (client and settings.R2_BUCKET_NAME):
        return storage_url_or_key

    # Extract clean R2 object key
    key = storage_url_or_key
    if key.startswith("r2://"):
        key = key[5:]
    elif settings.R2_PUBLIC_BASE_URL and key.startswith(settings.R2_PUBLIC_BASE_URL):
        key = key[len(settings.R2_PUBLIC_BASE_URL) :].lstrip("/")
    elif key.startswith("/"):
        key = key.lstrip("/")

    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )
    except Exception:
        return storage_url_or_key


def generate_presigned_upload_url(
    storage_key: str,
    content_type: str = "image/jpeg",
    expires_in: int = 900,
) -> dict:
    """
    Generates a secure, time-limited presigned PUT URL for direct client-to-R2 upload (STOR-01).
    Default expiration is 15 minutes (900s).
    """
    client = get_r2_client()
    if not (client and settings.R2_BUCKET_NAME):
        return {
            "upload_url": f"/api/v1/uploads/{storage_key}",
            "storage_key": storage_key,
            "is_local": True,
            "expires_in": expires_in,
        }

    key = storage_key.lstrip("/")
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )
    return {
        "upload_url": upload_url,
        "storage_key": key,
        "is_local": False,
        "expires_in": expires_in,
    }


def delete_file(storage_url_or_key: str) -> bool:
    """
    Deletes a file from either Cloudflare R2 or local storage (STOR-01).
    """
    client = get_r2_client()
    if client and settings.R2_BUCKET_NAME and not storage_url_or_key.startswith("/uploads/"):
        key = storage_url_or_key.replace("r2://", "").lstrip("/")
        try:
            client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
            return True
        except Exception:
            return False

    # Local delete
    rel_path = storage_url_or_key.lstrip("/")
    local_path = Path(".") / rel_path
    if local_path.exists() and local_path.is_file():
        try:
            local_path.unlink()
            return True
        except Exception:
            return False
    return False
