"""
مسارات المصادقة — تسجيل + دخول
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.limiter import limiter

from app.database import get_db, User
from app.auth import hash_password, verify_password, create_access_token, require_auth

router  = APIRouter()


# ── Schemas ───────────────────────────────────────────
class RegisterRequest(BaseModel):
    name:     str
    email:    EmailStr
    password: str

class UserResponse(BaseModel):
    id:    str
    name:  str
    email: str
    plan:  str

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserResponse


# ══════════════════════════════════════════════════════
#  POST /api/auth/register
# ══════════════════════════════════════════════════════
@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("10/hour")
def register(request: Request, data: RegisterRequest, db: Session = Depends(get_db)):
    """تسجيل مستخدم جديد"""

    # تحقق أن الإيميل غير مستخدم
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="هذا الإيميل مسجل مسبقاً",
        )

    # أنشئ المستخدم
    user = User(
        name            = data.name,
        email           = data.email,
        hashed_password = hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ══════════════════════════════════════════════════════
#  POST /api/auth/login
# ══════════════════════════════════════════════════════
@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")              # حماية من هجمات القوة الغاشمة
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db:   Session                   = Depends(get_db),
):
    """تسجيل الدخول بالإيميل وكلمة المرور"""
    user = db.query(User).filter(User.email == form.username).first()

    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="إيميل أو كلمة مرور خاطئة",
        )

    token = create_access_token({"sub": user.id})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ══════════════════════════════════════════════════════
#  GET /api/auth/me
# ══════════════════════════════════════════════════════
@router.get("/me", response_model=UserResponse)
def get_me(current_user = Depends(require_auth)):
    """بيانات المستخدم الحالي"""
    return current_user
