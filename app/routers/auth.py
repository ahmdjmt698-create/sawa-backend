"""
راوتر المصادقة — تسجيل، دخول، خروج، CSRF، إعدادات، نسيان كلمة المرور
"""
import random
import string
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Cookie, Header
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import get_db, User, RefreshToken, PasswordResetOTP
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_token,
    create_password_reset_token,
    decode_token,
    set_access_cookie,
    set_refresh_cookie,
    delete_auth_cookies,
    ACCESS_COOKIE_MAX_AGE,
    REFRESH_COOKIE_MAX_AGE,
    require_auth,
)
from app.config import settings
from app.limiter import limiter

router = APIRouter()


# ══════════════════════════════════════════════════════
#  Schemas
# ══════════════════════════════════════════════════════
class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    plan: str

    class Config:
        from_attributes = True


class NameUpdateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str


# ══════════════════════════════════════════════════════
#  مساعدات
# ══════════════════════════════════════════════════════
def _issue_tokens(response: Response, user: User):
    """يُصدر توكنين (access + refresh) ويضبطهما كوكيز"""
    access_token = create_access_token({"sub": user.id})
    raw_refresh = create_refresh_token()
    refresh_hash = hash_token(raw_refresh)

    db_refresh = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )

    # نستخدم جلسة مستقلة لأننا قد لا نملك db في كل الحالات
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.add(db_refresh)
        db.commit()
    finally:
        db.close()

    set_access_cookie(response, access_token)
    set_refresh_cookie(response, raw_refresh)


def _generate_otp() -> str:
    """ينشئ رمز تحقق من 6 أرقام"""
    return "".join(random.choices(string.digits, k=6))


# ══════════════════════════════════════════════════════
#  CSRF Token
# ══════════════════════════════════════════════════════
@router.get("/csrf-token")
def get_csrf_token(response: Response):
    """يُنشئ CSRF token ويضعه في كوكيز"""
    from itsdangerous import URLSafeTimedSerializer
    serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
    token = serializer.dumps("csrf")
    response.set_cookie(
        "csrf_token", token,
        httponly=False,
        samesite="strict",
        max_age=60 * 60,
    )
    return {"csrf_token": token}


# ══════════════════════════════════════════════════════
#  تسجيل مستخدم جديد
# ══════════════════════════════════════════════════════
@router.post("/register", status_code=201)
def register(
    response: Response,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    تسجيل مستخدم جديد.
    يُعيّد كوكيز httpOnly بدلاً من التوكن في الـ body.
    """
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="هذا البريد الإلكتروني مسجل مسبقاً",
            error_code="EMAIL_EXISTS",
        )

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _issue_tokens(response, user)
    return {"user": UserResponse.model_validate(user)}


# ══════════════════════════════════════════════════════
#  تسجيل الدخول
# ══════════════════════════════════════════════════════
@router.post("/login")
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    تسجيل الدخول — يُعيّد كوكيز httpOnly.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="لا يوجد حساب بهذا البريد الإلكتروني",
            error_code="EMAIL_NOT_FOUND",
        )
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="كلمة المرور غير صحيحة",
            error_code="WRONG_PASSWORD",
        )

    _issue_tokens(response, user)
    return {"user": UserResponse.model_validate(user)}


# ══════════════════════════════════════════════════════
#  تسجيل الخروج
# ══════════════════════════════════════════════════════
@router.post("/logout")
def logout(
    response: Response,
    sawa_refresh: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    """حذف الكوكيز وإلغاء توكن التحديث"""
    if sawa_refresh:
        refresh_hash = hash_token(sawa_refresh)
        token_record = db.query(RefreshToken).filter(
            RefreshToken.token_hash == refresh_hash
        ).first()
        if token_record:
            token_record.revoked = True
            db.commit()

    delete_auth_cookies(response)
    return {"message": "تم تسجيل الخروج بنجاح"}


# ══════════════════════════════════════════════════════
#  تحديث التوكن (Refresh)
# ══════════════════════════════════════════════════════
@router.post("/refresh")
def refresh_token(
    response: Response,
    sawa_refresh: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    """
    يُحدّث توكن الوصول باستخدام توكن التحديث.
    يُدير الدوران: يلغي القديم ويُصدر جديداً.
    """
    if not sawa_refresh:
        raise HTTPException(status_code=401, detail="لا يوجد توكن تحديث",
                            error_code="TOKEN_EXPIRED")

    refresh_hash = hash_token(sawa_refresh)
    token_record = db.query(RefreshToken).filter(
        and_(
            RefreshToken.token_hash == refresh_hash,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.utcnow(),
        )
    ).first()

    if not token_record:
        raise HTTPException(status_code=401, detail="توكن التحديث غير صالح أو منتهي",
                            error_code="TOKEN_EXPIRED")

    # دوران: ألغِ القديم وأصدر جديداً
    token_record.revoked = True
    db.commit()

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="المستخدم غير موجود",
                            error_code="TOKEN_EXPIRED")

    _issue_tokens(response, user)
    return {"message": "تم تحديث التوكن بنجاح"}


# ══════════════════════════════════════════════════════
#  بيانات المستخدم الحالي
# ══════════════════════════════════════════════════════
@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(require_auth)):
    return UserResponse.model_validate(current_user)


# ══════════════════════════════════════════════════════
#  تغيير الاسم
# ══════════════════════════════════════════════════════
@router.patch("/settings/name", response_model=UserResponse)
def update_name(
    data: NameUpdateRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    current_user.name = data.name
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


# ══════════════════════════════════════════════════════
#  تغيير كلمة المرور
# ══════════════════════════════════════════════════════
@router.patch("/settings/password")
def update_password(
    response: Response,
    data: PasswordChangeRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="كلمة المرور الحالية غير صحيحة",
            error_code="WRONG_PASSWORD",
        )

    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=422,
            detail="كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل وتحتوي على رقم",
            error_code="VALIDATION_ERROR",
        )

    if not any(c.isdigit() for c in data.new_password):
        raise HTTPException(
            status_code=422,
            detail="كلمة المرور الجديدة يجب أن تحتوي على رقم واحد على الأقل",
            error_code="VALIDATION_ERROR",
        )

    if verify_password(data.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="كلمة المرور الجديدة مطابقة للقديمة — اختر كلمة مرور مختلفة",
            error_code="SAME_PASSWORD",
        )

    current_user.hashed_password = hash_password(data.new_password)
    db.commit()

    # ألغِ جميع توكنات التحديث لهذه الجلسة (أجبر على إعادة الدخول)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id
    ).update({"revoked": True})
    db.commit()

    delete_auth_cookies(response)
    return {"message": "تم تغيير كلمة المرور بنجاح"}


# ══════════════════════════════════════════════════════
#  نسيت كلمة المرور — إرسال OTP
# ══════════════════════════════════════════════════════
@router.post("/forgot-password")
@limiter.limit("3/hour")
def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    يُرسل رمز OTP إلى البريد الإلكتروني.
    لا يُكشف هل البريد مسجل أم لا (للأمان).
    """
    user = db.query(User).filter(User.email == data.email).first()
    user_name = user.name if user else ""

    otp = _generate_otp()
    otp_hash = hash_password(otp)

    otp_record = PasswordResetOTP(
        email=data.email,
        otp_hash=otp_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=15),
    )
    db.add(otp_record)
    db.commit()

    # أرسل البريد في الخلفية
    try:
        import asyncio
        from app.email_service import send_otp_email
        asyncio.create_task(send_otp_email(data.email, otp, user_name))
    except Exception as e:
        pass  # لا نوقف التطبيق إذا فشل البريد

    return {"message": "إذا كان البريد مسجلاً، ستصله رسالة خلال دقيقة"}


# ══════════════════════════════════════════════════════
#  التحقق من OTP
# ══════════════════════════════════════════════════════
@router.post("/verify-otp")
def verify_otp(
    data: VerifyOTPRequest,
    db: Session = Depends(get_db),
):
    otp_record = (
        db.query(PasswordResetOTP)
        .filter(
            and_(
                PasswordResetOTP.email == data.email,
                PasswordResetOTP.used == False,
                PasswordResetOTP.expires_at > datetime.utcnow(),
            )
        )
        .order_by(PasswordResetOTP.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(
            status_code=400,
            detail="انتهت صلاحية الرمز، اطلب رمزاً جديداً",
            error_code="OTP_EXPIRED",
        )

    otp_record.attempts += 1
    db.commit()

    if otp_record.attempts > 5:
        raise HTTPException(
            status_code=429,
            detail="تجاوزت عدد المحاولات، اطلب رمزاً جديداً",
            error_code="OTP_MAX_ATTEMPTS",
        )

    if not verify_password(data.otp, otp_record.otp_hash):
        remaining = 5 - otp_record.attempts
        raise HTTPException(
            status_code=400,
            detail=f"الرمز غير صحيح، تبقى {remaining} محاولات",
            error_code="OTP_INVALID",
        )

    otp_record.used = True
    db.commit()

    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="حدث خطأ")

    reset_token = create_password_reset_token(user.id)
    return {"reset_token": reset_token}


# ══════════════════════════════════════════════════════
#  إعادة تعيين كلمة المرور
# ══════════════════════════════════════════════════════
@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    payload = decode_token(data.reset_token)
    if not payload or payload.get("type") != "password_reset":
        raise HTTPException(
            status_code=400,
            detail="الرابط غير صالح أو منتهي",
            error_code="INVALID_TOKEN",
        )

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=422,
            detail="كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل",
            error_code="VALIDATION_ERROR",
        )

    if not any(c.isdigit() for c in data.new_password):
        raise HTTPException(
            status_code=422,
            detail="كلمة المرور الجديدة يجب أن تحتوي على رقم",
            error_code="VALIDATION_ERROR",
        )

    user.hashed_password = hash_password(data.new_password)
    db.commit()

    # ألغِ جميع توكنات التحديث
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id
    ).update({"revoked": True})
    db.commit()

    return {"message": "تم تغيير كلمة المرور بنجاح"}
