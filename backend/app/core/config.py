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
    # Rule engine & Human Review (REV-01, E2-08)
    # ------------------------------------------------------------------
    ACTIVE_RULE_PACK_VERSION: str = ""  # set after RULE-02 seeds initial pack
    REVIEW_CONFIDENCE_THRESHOLD: float = 0.85  # default fallback threshold
    # Field-specific tuned confidence thresholds from Phase 1 pilot data (E2-08, ADR-012)
    # Maps canonical extractor field_types, fine-grained declaration sub-types, and legacy/rule aliases.
    FIELD_CONFIDENCE_THRESHOLDS: dict[str, float] = {
        "mrp": 0.82,
        "net_quantity": 0.80,
        "mfg_date": 0.80,
        "date_of_manufacture": 0.80,
        "manufacturer_address": 0.78,
        "consumer_care": 0.80,
        "country_of_origin": 0.85,
        "commodity_name": 0.85,
        "dimension_count": 0.80,
        "dimensions_and_count": 0.80,
        "dimensions": 0.80,
        "item_count": 0.80,
        "packer_importer": 0.78,
        "importer_packer": 0.78,
        "importer_address": 0.78,
        "packer_address": 0.78,
        "marketer_address": 0.78,
        "rsp": 0.85,
        "retail_sale_price": 0.85,
    }

    # ------------------------------------------------------------------
    # CORS  (comma-separated or JSON list of origins)
    # ------------------------------------------------------------------
    CORS_ALLOWED_ORIGINS: list[str] | str = ["http://localhost:3000"]

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    RATE_LIMIT_AUTH: str = "5/minute"

    # ------------------------------------------------------------------
    # Bhashini ULCA Multilingual Integration (E3-04, ADR-013)
    # ------------------------------------------------------------------
    BHASHINI_API_KEY: str = ""
    BHASHINI_USER_ID: str = ""
    BHASHINI_PIPELINE_ID: str = ""
    BHASHINI_INFERENCE_ENDPOINT: str = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

    # ------------------------------------------------------------------
    # Government SSO (MeriPehchan / Jan Parichay) (E4-01, ADR-016)
    # ------------------------------------------------------------------
    MERIPEHCHAN_CLIENT_ID: str = ""
    MERIPEHCHAN_CLIENT_SECRET: str = ""
    MERIPEHCHAN_DISCOVERY_URL: str = "https://janparichay.nic.in/v1/.well-known/openid-configuration"
    MERIPEHCHAN_AUTHORIZE_URL: str = "https://janparichay.nic.in/v1/auth"
    MERIPEHCHAN_TOKEN_URL: str = "https://janparichay.nic.in/v1/token"
    MERIPEHCHAN_USERINFO_URL: str = "https://janparichay.nic.in/v1/userinfo"
    MERIPEHCHAN_REDIRECT_URI: str = "http://localhost:3000/api/auth/sso/callback"
    MERIPEHCHAN_SANDBOX_ENABLED: bool = True

    # ------------------------------------------------------------------
    # eMaap (National Legal Metrology Portal) Adapter (E4-05, ADR-020)
    # ------------------------------------------------------------------
    EMAAP_API_URL: str = ""
    EMAAP_API_KEY: str = ""
    EMAAP_CLIENT_ID: str = ""
    EMAAP_TIMEOUT_SECONDS: float = 10.0
    EMAAP_SANDBOX_ENABLED: bool = True

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


def get_field_confidence_threshold(field_type: str | None) -> float:
    """
    Returns the tuned confidence threshold for a given declaration field (E2-08, ADR-012).
    Calibrated against Phase 1 pilot datasets (Basmati rice, tea, cosmetics, pan masala).
    """
    if not field_type:
        return settings.REVIEW_CONFIDENCE_THRESHOLD
    clean_field = field_type.lower().strip().replace("-", "_")
    return settings.FIELD_CONFIDENCE_THRESHOLDS.get(clean_field, settings.REVIEW_CONFIDENCE_THRESHOLD)
