"""
app/auth.py — المصادقة الأساسية + كوكيز cross-domain
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, HTTPException, status, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db, User, SessionLocal
from app.config import settings

# ── Password hashing ─────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── JWT ──────────────────────────────────────────────
ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY

ACCESS_COOKIE_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

# ── Cross-domain cookie settings ─────────────────────
# في الإنتاج: SameSite=None + Secure=True (إلزامي للـ cross-domain)
_COOKIE_SECURE = settings.COOKIE_SECURE
_COOKIE_SAMESITE = "none" if _COOKIE_SECURE else "lax"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token() -> str:
    return uuid.uuid4().hex


def hash_token(token: str) -> str:
    return pwd_context.hash(token)


def create_password_reset_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    return jwt.encode({"sub": user_id, "exp": expire, "type": "password_reset"}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ══════════════════════════════════════════════════════
#  Cookie Helpers — CROSS-DOMAIN FIXED 🔧
# ══════════════════════════════════════════════════════
def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="sawa_access",
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        max_age=ACCESS_COOKIE_MAX_AGE,
        path="/",
    )


def set_refresh_cookie(response: Response, token: str):
    response.set_cookie(
        key="sawa_refresh",
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        max_age=REFRESH_COOKIE_MAX_AGE,
        path="/api/auth/refresh",
    )


def clear_auth_cookie(response: Response):
    response.delete_cookie(
        key="sawa_access",
        path="/",
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
    )


def clear_refresh_cookie(response: Response):
    response.delete_cookie(
        key="sawa_refresh",
        path="/api/auth/refresh",
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
    )


def delete_auth_cookies(response: Response):
    clear_auth_cookie(response)
    clear_refresh_cookie(response)


# ══════════════════════════════════════════════════════
#  Auth Dependencies
# ══════════════════════════════════════════════════════
security = HTTPBearer(auto_error=False)


def _get_token_from_request(request: Request) -> Optional[str]:
    """يجرب الكوكيز أولاً، ثم Authorization header"""
    token = request.cookies.get("sawa_access")
    if token:
        return token

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]

    # HTTPBearer
    try:
        creds = security(request)
        if creds:
            return creds.credentials
    except Exception:
        pass

    return None


def get_current_user(request: Request, db: Session = None) -> Optional[User]:
    token = _get_token_from_request(request)
    if not token:
        return None

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    if db is None:
        db = SessionLocal()
        try:
            return db.query(User).filter(User.id == user_id).first()
        finally:
            db.close()
    return db.query(User).filter(User.id == user_id).first()


def require_auth(request: Request, db: Session = None) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="يجب تسجيل الدخول",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user