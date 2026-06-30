"""
سوى — Backend (Production Ready)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.database import engine, Base
from app.routers import videos, auth, transcripts, payments, search
from app.config import settings

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sawa سوى",
    description="بديل Loom العربي — API",
    version="1.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url=None,
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
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static Files ──────────────────────────────────────
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.UPLOAD_DIR), name="media")

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
