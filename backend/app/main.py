"""
سوى — Backend (Production Ready)
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.limiter import limiter
from app.exceptions import APIException
import os

from app.database import engine, Base
from app.routers import videos, auth, transcripts, payments, search, comments, analytics
from app.config import settings

# ── Rate Limiter (shared across routers) ─────────────

app = FastAPI(
    title="Sawa سوى",
    description="بديل Loom العربي — API",
    version="2.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _safe(obj):
    """يحوّل أي قيمة bytes إلى نص عشان JSON ما ينكسر"""
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, dict):
        return {k: _safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe(v) for v in obj]
    return obj


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    PASSWORD_ERROR_TYPES = {"string_too_short", "string_too_long", "value_error"}
    for err in exc.errors():
        loc = err.get("loc", ())
        etype = err.get("type", "")
        if "password" in loc and etype in PASSWORD_ERROR_TYPES:
            if etype == "value_error":
                ctx_msg = str(err.get("ctx", {}).get("error", ""))
                detail = ctx_msg if ctx_msg else "كلمة المرور طويلة جداً"
            else:
                detail = "كلمة المرور يجب أن تكون 8 أحرف على الأقل"
            return JSONResponse(status_code=422, content={"detail": detail, "error_code": "VALIDATION_ERROR"})

    safe_errors = jsonable_encoder(_safe(exc.errors()))
    return JSONResponse(
        status_code=422,
        content={"detail": safe_errors, "error_code": "VALIDATION_ERROR"},
    )


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    content = {"detail": exc.detail}
    if exc.error_code:
        content["error_code"] = exc.error_code
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers,
    )

# ── CORS ─────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

frontend_url = os.getenv("FRONTEND_URL", "")
if frontend_url:
    ALLOWED_ORIGINS.append(frontend_url)
    ALLOWED_ORIGINS.append(frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in ALLOWED_ORIGINS if o],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    expose_headers=["Set-Cookie"],
)

# ── Upload Dir (ensure exists) ────────────────────────
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
app.include_router(comments.router,    prefix="/api",
                   tags=["Comments"])
app.include_router(analytics.router,   prefix="/api/videos",
                   tags=["Analytics"])


@app.get("/")
def root():
    return {"message": "سوى API 🎙️", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
