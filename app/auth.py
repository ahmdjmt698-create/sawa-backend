"""
نظام المصادقة — JWT + تشفير كلمات المرور + Refresh Tokens + الكوكيز
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib

from fastapi import Depends, HTTPException, status, Cookie, Request
from fastapi.security import OAuth2PasswordBearer
from app.exceptions import APIException
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, User, RefreshToken

# ── إعداد التشفير ────────────────────────────────────
pwd_context    = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme  = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ══════════════════════════════════════════════════════
#  كلمات المرور
# ══════════════════════════════════════════════════════
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ══════════════════════════════════════════════════════
#  JWT Tokens
# ══════════════════════════════════════════════════════
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token() -> str:
    """ينشئ توكن عشوائي آمن — القيمة الأصلية تُخزَّن في الكوكيز"""
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    """يشفر توكنRefresh بالـ SHA-256 لتخزينه في قاعدة البيانات"""
    return hashlib.sha256(token.encode()).hexdigest()


def create_password_reset_token(user_id: str) -> str:
    """ينشئ توكن إعادة تعيين كلمة المرور (صالح 10 دقائق)"""
    to_encode = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(minutes=10),
        "type": "password_reset",
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


# ══════════════════════════════════════════════════════
#  كوكيز المساعدة
# ══════════════════════════════════════════════════════
COOKIE_SAMESITE = "lax"
ACCESS_COOKIE_MAX_AGE = 60 * 15          # 15 دقيقة
REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 يوم


def set_access_cookie(response, token: str):
    response.set_cookie(
        key="sawa_token",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_COOKIE_MAX_AGE,
    )


def set_refresh_cookie(response, token: str):
    response.set_cookie(
        key="sawa_refresh",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_COOKIE_MAX_AGE,
    )


def delete_auth_cookies(response):
    response.delete_cookie("sawa_token", samesite=COOKIE_SAMESITE)
    response.delete_cookie("sawa_refresh", samesite=COOKIE_SAMESITE)


# ══════════════════════════════════════════════════════
#  Dependencies
# ══════════════════════════════════════════════════════
def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    sawa_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    يُرجع المستخدم الحالي — أو None إذا لم يكن مسجلاً دخوله.
    يقرأ التوكن من الكوكيز أولاً، ثم من هيدر Bearer كبديل.
    """
    # قراءة التوكن من الكوكيز أولاً
    effective_token = sawa_token or token

    if not effective_token:
        return None
    payload = decode_token(effective_token)
    if not payload:
        return None
    if payload.get("type") != "access":
        return None
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    return user


def require_auth(
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    """يُرجع المستخدم أو يرفع خطأ 401 إذا لم يكن مسجلاً"""
    if not current_user:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="يجب تسجيل الدخول أولاً",
            error_code="TOKEN_EXPIRED",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user
