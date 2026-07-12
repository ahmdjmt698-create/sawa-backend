"""
الإعدادات المركزية لمشروع سوى
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── قاعدة البيانات ──────────────────────────────
    DATABASE_URL: str = "sqlite:///./sawa.db"

    # ── التخزين ──────────────────────────────────────
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 500
    ALLOWED_EXTENSIONS: list = ["mp4", "webm", "mov", "mp3", "wav", "m4a"]

    # ── نموذج Whisper ────────────────────────────────
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # ── المصادقة ─────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # ── حدود الخطط ──────────────────────────────────
    FREE_MAX_VIDEOS: int = 25
    FREE_MAX_DURATION_SECONDS: int = 300
    PRO_MAX_DURATION_SECONDS: int = 3600

    # ── مفاتيح خارجية ────────────────────────────────
    ANTHROPIC_API_KEY: Optional[str] = None
    HUGGINGFACE_TOKEN: Optional[str] = None
    CRYPTOMUS_MERCHANT_ID: Optional[str] = None
    CRYPTOMUS_API_KEY: Optional[str] = None

    # ── روابط التطبيق والبيئة ────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"   # ← يتجاهل أي متغيرات إضافية في .env بدل رفع خطأ


settings = Settings()
