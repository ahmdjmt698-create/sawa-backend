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
    MAX_FILE_SIZE_MB: int = 500          # حد أقصى 500 ميجا للفيديو
    ALLOWED_EXTENSIONS: list = ["mp4", "webm", "mov", "mp3", "wav", "m4a"]

    # ── نموذج Whisper ────────────────────────────────
    # الخيارات: tiny | base | small | medium | large-v3
    # tiny  → سريع جداً، دقة أقل (للتطوير)
    # large-v3 → أبطأ، دقة عالية جداً (للإنتاج)
    WHISPER_MODEL: str = "small"  # غيّر حسب حاجتك
    WHISPER_DEVICE: str = "cpu"          # غيّر لـ "cuda" إذا عندك GPU
    WHISPER_COMPUTE_TYPE: str = "int8"   # int8 = أسرع على الـ CPU

    # ── المصادقة ─────────────────────────────────────
    SECRET_KEY: str = "غير-هذا-المفتاح-في-الإنتاج-حتماً"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # أسبوع

    # ── حدود الخطط ──────────────────────────────────
    FREE_MAX_VIDEOS: int = 25
    FREE_MAX_DURATION_SECONDS: int = 300   # 5 دقائق
    PRO_MAX_DURATION_SECONDS: int = 3600   # ساعة كاملة
    ANTHROPIC_API_KEY: Optional[str] = None  # مفتاح Anthropic API (اختياري)
    # معرف تاجر Cryptomus (اختياري)
    CRYPTOMUS_MERCHANT_ID: Optional[str] = None
    CRYPTOMUS_API_KEY: Optional[str] = None  # مفتاح Cryptomus API (اختياري)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
