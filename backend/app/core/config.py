"""
Central config — all settings loaded from environment variables via Pydantic Settings.
Every variable here must also appear in .env.example and docs/11_SECRETS_CHECKLIST.md.
Add new secrets to BOTH files in the same commit — never one without the other.
"""

import json
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # App
    # ------------------------------------------------------------------
    APP_ENV: Literal["development", "staging", "production"] = "development"

    # ------------------------------------------------------------------
    # JWT Auth
    # ------------------------------------------------------------------
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ------------------------------------------------------------------
    # Database
    # SQLite for local dev, postgresql+asyncpg://... for Neon (prod)
    # ------------------------------------------------------------------
    DATABASE_URL: str = "sqlite+aiosqlite:///./niyamdrishti.db"

    # ------------------------------------------------------------------
    # Cloudflare R2  (S3-compatible)
    # ------------------------------------------------------------------
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "niyamdrishti-media"
    R2_ENDPOINT_URL: str = ""  # https://<account_id>.r2.cloudflarestorage.com
    R2_PUBLIC_BASE_URL: str = ""  # public CDN / presigned base URL

    # ------------------------------------------------------------------
    # SMTP Email  (Gmail SMTP default — see ADR-003)
    # ------------------------------------------------------------------
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_APP_PASSWORD: str = ""

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------
    PADDLEOCR_LANG: str = "en"
    OCR_MODEL_CACHE_DIR: str = "./ocr_models"

    # ------------------------------------------------------------------
    # Rule engine & Human Review (REV-01)
    # ------------------------------------------------------------------
    ACTIVE_RULE_PACK_VERSION: str = ""  # set after RULE-02 seeds initial pack
    REVIEW_CONFIDENCE_THRESHOLD: float = 0.85  # baseline 85% confidence threshold for review queue routing

    # ------------------------------------------------------------------
    # CORS  (comma-separated or JSON list of origins)
    # ------------------------------------------------------------------
    CORS_ALLOWED_ORIGINS: list[str] | str = ["http://localhost:3000"]

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    RATE_LIMIT_AUTH: str = "5/minute"

    @field_validator("CORS_ALLOWED_ORIGINS", mode="after")
    @classmethod
    def parse_cors(cls, v: list[str] | str) -> list[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                try:
                    parsed = json.loads(v_str)
                    if isinstance(parsed, list):
                        return [str(i).strip() for i in parsed if str(i).strip()]
                except Exception:
                    pass
            return [i.strip() for i in v_str.split(",") if i.strip()]
        if isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]
        return ["http://localhost:3000"]

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()
