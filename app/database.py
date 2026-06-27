"""
إعداد قاعدة البيانات ونماذج الجداول
"""
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import enum
import uuid

from app.config import settings

# ── إعداد المحرك ─────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    # مطلوب لـ SQLite فقط
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Dependency لجلسة قاعدة البيانات ─────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ══════════════════════════════════════════════════════
#  ENUMS
# ══════════════════════════════════════════════════════
class TranscriptStatus(str, enum.Enum):
    PENDING    = "pending"     # في الانتظار
    PROCESSING = "processing"  # قيد المعالجة
    DONE       = "done"        # اكتمل
    FAILED     = "failed"      # فشل


class UserPlan(str, enum.Enum):
    FREE = "free"
    PRO  = "pro"
    TEAM = "team"


class ArabicDialect(str, enum.Enum):
    STANDARD = "ar"       # عربي فصحى
    EGYPTIAN = "ar-EG"    # مصري
    GULF     = "ar-AE"    # خليجي
    LEVANTINE= "ar-SY"    # شامي
    MAGHREBI = "ar-MA"    # مغاربي
    LIBYAN   = "ar-LY"    # ليبي


# ══════════════════════════════════════════════════════
#  MODELS
# ══════════════════════════════════════════════════════
class User(Base):
    __tablename__ = "users"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email        = Column(String, unique=True, nullable=False, index=True)
    name         = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    plan         = Column(String, default=UserPlan.FREE)
    is_active    = Column(Boolean, default=True)
    subscription_expires_at = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    # علاقة: مستخدم → فيديوهاته
    videos       = relationship("Video", back_populates="owner", cascade="all, delete")

    def __repr__(self):
        return f"<User {self.email} [{self.plan}]>"


class Video(Base):
    __tablename__ = "videos"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title        = Column(String, nullable=False, default="تسجيل جديد")
    description  = Column(Text, nullable=True)

    # ── الملف ──────────────────────────────────────
    file_path    = Column(String, nullable=False)   # مسار الملف المحلي أو URL
    file_size    = Column(Integer, nullable=True)   # بالبايت
    duration     = Column(Float, nullable=True)     # بالثواني
    mime_type    = Column(String, nullable=True)

    # ── إعدادات التفريغ ─────────────────────────────
    dialect      = Column(String, default=ArabicDialect.STANDARD)
    is_public    = Column(Boolean, default=True)   # رابط المشاركة العام
    share_token  = Column(String, unique=True, default=lambda: uuid.uuid4().hex)

    # ── البيانات الوصفية ─────────────────────────────
    views_count  = Column(Integer, default=0)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── العلاقات ─────────────────────────────────────
    owner_id     = Column(String, ForeignKey("users.id"), nullable=True)  # nullable للزوار
    owner        = relationship("User", back_populates="videos")
    transcript   = relationship("Transcript", back_populates="video", uselist=False, cascade="all, delete")

    def __repr__(self):
        return f"<Video '{self.title}' [{self.id[:8]}]>"


class Transcript(Base):
    __tablename__ = "transcripts"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id     = Column(String, ForeignKey("videos.id"), unique=True, nullable=False)

    # ── النتائج ──────────────────────────────────────
    full_text    = Column(Text, nullable=True)           # النص الكامل
    segments_json= Column(Text, nullable=True)           # JSON: [{start, end, text}, ...]
    summary      = Column(Text, nullable=True)           # ملخص AI (مرحلة لاحقة)

    # ── الحالة ───────────────────────────────────────
    status       = Column(String, default=TranscriptStatus.PENDING)
    error_message= Column(Text, nullable=True)
    language_detected = Column(String, nullable=True)   # ما اكتشفه Whisper

    # ── التوقيت ──────────────────────────────────────
    processing_time = Column(Float, nullable=True)      # ثواني استغرق التفريغ
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── العلاقة ──────────────────────────────────────
    video        = relationship("Video", back_populates="transcript")

    def __repr__(self):
        return f"<Transcript video={self.video_id[:8]} status={self.status}>"
