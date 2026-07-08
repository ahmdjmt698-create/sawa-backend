"""
مسارات الفيديوهات — رفع، جلب، حذف، بث
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from app.limiter import limiter

from app.database import get_db, Video, Transcript, TranscriptStatus, User
from app.auth import get_current_user, require_auth
from app.config import settings
from app.transcription import transcribe_audio, extract_audio_if_needed

router = APIRouter()


# ── Schemas ───────────────────────────────────────────
class VideoResponse(BaseModel):
    id:           str
    title:        str
    description:  Optional[str]
    # file_path intentionally excluded — never expose raw filesystem paths
    duration:     Optional[float]
    file_size:    Optional[int]
    dialect:      str
    is_public:    bool
    share_token:  str
    views_count:  int
    created_at:   datetime
    transcript_status: Optional[str] = None

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════
#  مهمة خلفية: التفريغ الصوتي
# ══════════════════════════════════════════════════════
def run_transcription_task(video_id: str, file_path: str, language: str):
    """
    تعمل في الخلفية بعد الرفع مباشرة
    لا تُوقف المستخدم في الانتظار
    """
    from app.database import Transcript, Video, TranscriptStatus, SessionLocal
    import json, time

    # جلسة قاعدة بيانات مستقلة للـ background task — تُعاد من SessionLocal المشتركة
    db = SessionLocal()

    transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
    if not transcript:
        db.close()
        return

    try:
        # غيّر الحالة لـ "قيد المعالجة"
        transcript.status = TranscriptStatus.PROCESSING
        db.commit()

        # استخرج الصوت إذا لزم
        audio_path = extract_audio_if_needed(file_path)

        # فرّغ الصوت
        result = transcribe_audio(audio_path, language=language)

        # احفظ النتائج
        transcript.full_text         = result["full_text"]
        transcript.segments_json     = json.dumps(result["segments"], ensure_ascii=False)
        transcript.language_detected = result["language_detected"]
        transcript.processing_time   = result["processing_time"]
        transcript.status            = TranscriptStatus.DONE

        db.commit()

    except Exception as e:
        transcript.status        = TranscriptStatus.FAILED
        transcript.error_message = str(e)
        db.commit()

    finally:
        db.close()


# ══════════════════════════════════════════════════════
#  POST /api/videos/upload  — يتطلب مصادقة
# ══════════════════════════════════════════════════════
@router.post("/upload", response_model=VideoResponse, status_code=201)
@limiter.limit("10/hour")                   # أقصى 10 رفعات/ساعة لكل IP
async def upload_video(
    request:          Request,
    background_tasks: BackgroundTasks,
    file:        UploadFile    = File(...),
    title:       str           = Form("تسجيل جديد"),
    description: Optional[str] = Form(None),
    dialect:     str           = Form("ar"),
    db:          Session       = Depends(get_db),
    current_user: User         = Depends(require_auth),   # ✅ FIX: was Optional + Depends(get_current_user)
):
    """رفع فيديو أو ملف صوتي وبدء التفريغ تلقائياً — يتطلب تسجيل الدخول"""

    # ── تحقق من نوع الملف ──────────────────────────
    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"نوع الملف غير مدعوم. الأنواع المقبولة: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    # ── تحقق من حدود الخطة ─────────────────────────
    video_count = db.query(Video).filter(Video.owner_id == current_user.id).count()
    if current_user.plan == "free" and video_count >= settings.FREE_MAX_VIDEOS:
        raise HTTPException(
            status_code=403,
            detail=f"وصلت للحد الأقصى ({settings.FREE_MAX_VIDEOS} تسجيل) في الخطة المجانية. يرجى الترقية.",
        )

    # ── احفظ الملف ─────────────────────────────────
    video_id  = str(uuid.uuid4())
    filename  = f"{video_id}.{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = os.path.getsize(file_path)

    # ── أنشئ سجل الفيديو ───────────────────────────
    video = Video(
        id          = video_id,
        title       = title,
        description = description,
        file_path   = file_path,
        file_size   = file_size,
        mime_type   = file.content_type,
        dialect     = dialect,
        owner_id    = current_user.id,
    )
    db.add(video)

    # ── أنشئ سجل التفريغ (في الانتظار) ─────────────
    transcript = Transcript(video_id=video_id)
    db.add(transcript)
    db.commit()
    db.refresh(video)

    # ── ابدأ التفريغ في الخلفية ─────────────────────
    background_tasks.add_task(
        run_transcription_task,
        video_id  = video_id,
        file_path = file_path,
        language  = dialect if len(dialect) == 2 else "ar",
    )

    response = VideoResponse.model_validate(video)
    response.transcript_status = TranscriptStatus.PENDING
    return response


# ══════════════════════════════════════════════════════
#  GET /api/videos/my  — فيديوهات المستخدم
# ══════════════════════════════════════════════════════
@router.get("/my", response_model=List[VideoResponse])
def get_my_videos(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_auth),
):
    videos = (
        db.query(Video)
        .filter(Video.owner_id == current_user.id)
        .order_by(Video.created_at.desc())
        .all()
    )
    result = []
    for v in videos:
        r = VideoResponse.model_validate(v)
        r.transcript_status = v.transcript.status if v.transcript else None
        result.append(r)
    return result


# ══════════════════════════════════════════════════════
#  GET /api/videos/share/{token}  — رابط المشاركة العام
#  يجب أن يسبق /{video_id} لتجنب تعارض المسارات
# ══════════════════════════════════════════════════════
@router.get("/share/{token}", response_model=VideoResponse)
def get_video_by_share_token(token: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.share_token == token).first()
    if not video:
        raise HTTPException(status_code=404, detail="الرابط غير صحيح أو منتهي")
    video.views_count += 1
    db.commit()
    r = VideoResponse.model_validate(video)
    r.transcript_status = video.transcript.status if video.transcript else None
    return r


# ══════════════════════════════════════════════════════
#  GET /api/videos/share/{token}/stream  — بث للزوار عبر رابط المشاركة
# ══════════════════════════════════════════════════════
@router.get("/share/{token}/stream")
def stream_video_by_share_token(token: str, db: Session = Depends(get_db)):
    """
    بث الملف الصوتي/المرئي للزوار الذين يملكون رابط المشاركة.
    لا يكشف عن مسار الملف — يعيد البيانات مباشرة.
    """
    video = db.query(Video).filter(Video.share_token == token).first()
    if not video:
        raise HTTPException(status_code=404, detail="الرابط غير صحيح أو منتهي")

    if not os.path.exists(video.file_path):
        raise HTTPException(status_code=404, detail="الملف غير موجود على الخادم")

    return FileResponse(
        path        = video.file_path,
        media_type  = video.mime_type or "application/octet-stream",
        filename    = Path(video.file_path).name,
        headers     = {"Accept-Ranges": "bytes"},
    )


# ══════════════════════════════════════════════════════
#  GET /api/videos/{id}  — فيديو بعينه
# ══════════════════════════════════════════════════════
@router.get("/{video_id}", response_model=VideoResponse)
def get_video(
    video_id:     str,
    db:           Session       = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="الفيديو غير موجود")

    # تحقق من الصلاحية
    if not video.is_public:
        if not current_user or video.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="ليس لديك صلاحية لمشاهدة هذا الفيديو")

    # أضف مشاهدة
    video.views_count += 1
    db.commit()

    r = VideoResponse.model_validate(video)
    r.transcript_status = video.transcript.status if video.transcript else None
    return r


# ══════════════════════════════════════════════════════
#  GET /api/videos/{id}/stream  — بث للمالك (أو فيديو عام)
# ══════════════════════════════════════════════════════
@router.get("/{video_id}/stream")
def stream_video(
    video_id:     str,
    db:           Session       = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    يطبّق نفس منطق التحقق من الصلاحية الموجود في get_video()
    ثم يبثّ الملف مباشرة — لا يُعرض مسار الملف للعميل أبداً.
    يدعم HTTP Range requests لتمكين التخطي في الفيديو.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="الفيديو غير موجود")

    if not video.is_public:
        if not current_user or video.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="ليس لديك صلاحية لمشاهدة هذا الفيديو")

    if not os.path.exists(video.file_path):
        raise HTTPException(status_code=404, detail="الملف غير موجود على الخادم")

    return FileResponse(
        path        = video.file_path,
        media_type  = video.mime_type or "application/octet-stream",
        filename    = Path(video.file_path).name,
        headers     = {"Accept-Ranges": "bytes"},
    )


# ══════════════════════════════════════════════════════
#  DELETE /api/videos/{id}
# ══════════════════════════════════════════════════════
@router.delete("/{video_id}", status_code=204)
def delete_video(
    video_id:     str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_auth),
):
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.owner_id == current_user.id,
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="الفيديو غير موجود أو ليس لديك صلاحية حذفه")

    # احذف الملف من القرص
    if os.path.exists(video.file_path):
        os.remove(video.file_path)

    db.delete(video)
    db.commit()
