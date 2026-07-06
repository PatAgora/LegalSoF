"""
Application configuration using Pydantic settings.
"""
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import logging
import os

# Known insecure development default — never allowed outside development.
_DEFAULT_SECRET_KEY = "agora-dev-secret-key-change-in-production"


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        # Deployment env files carry vars consumed outside Settings
        # (e.g. ADMIN_EMAIL/ADMIN_PASSWORD read by scripts/init_db.py).
        extra="ignore",
    )

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def _ensure_asyncpg_driver(cls, v: str) -> str:
        # Railway / Heroku expose postgres URLs without the SQLAlchemy
        # driver scheme. Normalise to asyncpg so the app runs unchanged.
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://"):]
        return v
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Agora Consulting AI"
    
    # Security
    SECRET_KEY: str = os.environ.get("SECRET_KEY", _DEFAULT_SECRET_KEY)

    @model_validator(mode="after")
    def _enforce_secret_key(self):
        """Refuse to start in production/staging with a missing or default
        SECRET_KEY; warn (but continue) in development."""
        insecure = not self.SECRET_KEY or self.SECRET_KEY == _DEFAULT_SECRET_KEY
        if insecure:
            if self.ENVIRONMENT.lower() in ("production", "staging"):
                raise RuntimeError(
                    "SECRET_KEY is unset or still the insecure development default. "
                    "Set a strong random SECRET_KEY environment variable before "
                    f"running in {self.ENVIRONMENT}."
                )
            logging.getLogger(__name__).warning(
                "SECRET_KEY is using the insecure development default — "
                "set SECRET_KEY before deploying beyond development."
            )
        return self
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]
    
    # Database — must be set via environment variable or .env file
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sof_platform"
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_MAX_TOKENS: int = 4000

    # AI-assisted Source of Funds claim extraction from free-text
    # client explanations. AI_PROVIDER selects the model provider
    # ('anthropic' now, 'gemini' later). When the active provider's
    # API key is unset the platform falls back to the deterministic
    # regex parser.
    AI_PROVIDER: str = os.environ.get("AI_PROVIDER", "anthropic")

    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    
    # Document encryption at rest. A urlsafe base64 32-byte Fernet key —
    # generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # When unset, documents are stored unencrypted (legacy behaviour);
    # encrypted and plaintext payloads can coexist — see
    # app/services/crypto.py.
    DOCUMENT_ENCRYPTION_KEY: str = ""

    @model_validator(mode="after")
    def _warn_unencrypted_production(self):
        """Warn (but do not block boot) when running in production
        without a document encryption key — plaintext storage remains
        supported for existing deployments."""
        if (
            self.ENVIRONMENT.lower() == "production"
            and not self.DOCUMENT_ENCRYPTION_KEY
        ):
            logging.getLogger(__name__).warning(
                "DOCUMENT_ENCRYPTION_KEY is not set — uploaded documents "
                "will be stored UNENCRYPTED at rest. Set a Fernet key to "
                "enable document encryption in production."
            )
        return self

    # Record retention (SRA / MLR 2017 Reg 40) — years to retain
    # archived matter records before disposal may be considered.
    RETENTION_YEARS: int = 6

    # Storage
    STORAGE_TYPE: str = "local"  # local, s3, minio
    STORAGE_LOCAL_PATH: str = "./uploads"
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_ENDPOINT_URL: str = ""  # For MinIO compatibility
    
    # Document Processing
    ENABLE_OCR: bool = True
    TESSERACT_CMD: str = "/usr/bin/tesseract"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_DOCUMENT_TYPES: List[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "image/png",
        "image/jpeg",
    ]
    
    # Client Portal
    PORTAL_TOKEN_EXPIRE_HOURS: int = 72  # 3 days
    
    # Business Logic
    AMOUNT_TOLERANCE_PERCENTAGE: float = 2.0  # 2% tolerance for amount matching
    DATE_TOLERANCE_DAYS: int = 5  # 5 days tolerance for date matching
    
    # Observability
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str = ""
    
    # Feature Flags
    ENABLE_AI_EXTRACTION: bool = True
    ENABLE_AI_NARRATIVE: bool = True
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60


settings = Settings()
