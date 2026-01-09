"""
Application configuration using Pydantic settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import secrets


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Legal SoF Platform"
    
    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./sof_platform.db"
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_MAX_TOKENS: int = 4000
    
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
