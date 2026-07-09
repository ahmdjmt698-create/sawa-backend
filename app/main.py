"""
سوى — Backend (Production Ready)
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.limiter import limiter
import os

from app.database import engine, Base
from app.routers import videos, auth, transcripts, payments, search
from app.config import settings

Base.metadata.create_all(bind=engine)

# ── Rate Limiter (shared across routers) ─────────────
# المثيل الوحيد معرّف في app/limiter.py — لا تُنشئ مثيلاً جديداً هنا

app = FastAPI(
    title="Sawa سوى",
    description="بديل Loom العربي — API",
    version="1.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    يُعيد رسائل خطأ عربية مخصصة لأخطاء التحقق الشائعة.
    الأخطاء الأخرى تُعاد بشكلها الافتراضي (مصفوفة pydantic).
    """
    # أنواع أخطاء طول كلمة المرور:
    #   string_too_short / string_too_long → من Field(min_length=...) الأحرف
    #   value_error                        → من field_validator (فحص البايتات)
    PASSWORD_ERROR_TYPES = {"string_too_short", "string_too_long", "value_error"}
    for err in exc.errors():
        loc   = err.get("loc", ())
        etype = err.get("type", "")
        if "password" in loc and etype in PASSWORD_ERROR_TYPES:
            # value_error يحمل الرسالة العربية مباشرة في ctx["error"]
            if etype == "value_error":
                ctx_msg = str(err.get("ctx", {}).get("error", ""))
                detail  = ctx_msg if ctx_msg else "كلمة المرور طويلة جداً"
            else:
                detail = "كلمة المرور يجب أن تكون 8 أحرف على الأقل"
            return JSONResponse(status_code=422, content={"detail": detail})
    # fallback: جميع أخطاء التحقق الأخرى تُعاد بشكلها الافتراضي
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

# ── CORS ─────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

frontend_url = os.getenv("FRONTEND_URL", "")
if frontend_url:
    ALLOWED_ORIGINS.append(frontend_url)
    # أضف بدون trailing slash أيضاً
    ALLOWED_ORIGINS.append(frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,          # ✅ FIX: was hardcoded ["*"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Upload Dir (ensure exists) ────────────────────────
# NOTE: Static file mount removed — files are served through the
# authenticated /api/videos/{id}/stream endpoint instead.
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# ── Routers ───────────────────────────────────────────
app.include_router(auth.router,        prefix="/api/auth",
                   tags=["Auth"])
app.include_router(videos.router,      prefix="/api/videos",
                   tags=["Videos"])
app.include_router(transcripts.router,
                   prefix="/api/transcripts", tags=["Transcripts"])
app.include_router(payments.router,
                   prefix="/api/payments",    tags=["Payments"])
app.include_router(search.router,      prefix="/api/search",
                   tags=["Search"])


@app.get("/")
def root():
    return {"message": "سوى API 🎙️", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
