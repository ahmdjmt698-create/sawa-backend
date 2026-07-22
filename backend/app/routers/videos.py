"""
مسارات الفيديوهات — رفع، جلب، حذف، بث، مشاركة محمية، HLS
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta
import aiofiles

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.limiter import limiter

from app.database import get_db, Video, Transcript, TranscriptStatus, User
from app.exceptions import APIException
from app.auth import get_current_user, require_auth, hash_password, verify_password
from app.config import settings
from app.transcription import transcribe_audio, extract_audio_if_needed, denoise_audio

router = APIRouter()


# ── Schemas ───────────────────────────────────────────
class VideoResponse(BaseModel):
    id:           str
    title:        str
    description:  Optional[str]
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


class ShareSettingsRequest(BaseModel):
    password: Optional[str] = None
    expires_in_days: Optional[int] = None


class UnlockShareRequest(BaseModel):
    password: str


# ══════════════════════════════════════════════════════
#  مهمة خلفية: التفريغ الصوتي
# ══════════════════════════════════════════════════════
def run_transcription_task(video_id: str, file_path: str, language: str, noise_reduction: bool = False):
    from app.database import Transcript, Video, TranscriptStatus, SessionLocal
    import json

    db = SessionLocal()
    transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
    if not transcript:
        db.close()
        return

    try:
        audio_path = extract_audio_if_needed(file_path)

        if noise_reduction:
            transcript.status = TranscriptStatus.DENOISING
            db.commit()
            try:
                audio_path = denoise_audio(audio_path)
            except Exception as denoise_err:
                import logging
                logging.getLogger(__name__).warning(f"⚠️ فشل تنظيف الصوت، التفريغ بدون تنظيف: {denoise_err}")

        transcript.status = TranscriptStatus.PROCESSING
        db.commit()
        result = transcribe_audio(audio_path, language=language)

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
#  POST /api/videos/upload
# ══════════════════════════════════════════════════════
@router.post("/upload", response_model=VideoResponse, status_code=201)
@limiter.limit("10/hour")
async def upload_video(
    request:          Request,
    background_tasks: BackgroundTasks,
    file:        UploadFile    = File(...),
    title:       str           = Form("تسجيل جديد"),
    description: Optional[str] = Form(None),
    dialect:     str           = Form("ar"),
    mode:        str           = Form("screen"),
    noise_reduction: bool      = Form(False),
    db:          Session       = Depends(get_db),
    current_user: User         = Depends(require_auth),
):
    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"نوع الملف غير مدعوم. الأنواع المقبولة: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    video_count = db.query(Video).filter(Video.owner_id == current_user.id).count()
    if current_user.plan == "free" and video_count >= settings.FREE_MAX_VIDEOS:
        raise HTTPException(
            status_code=403,
            detail=f"وصلت للحد الأقصى ({settings.FREE_MAX_VIDEOS} تسجيل) في الخطة المجانية. يرجى الترقية.",
        )

    video_id  = str(uuid.uuid4())
    filename  = f"{video_id}.{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    total_bytes = 0
    async with aiofiles.open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                await buffer.close()
                os.remove(file_path)
                raise HTTPException(
                    status_code=413,
                    detail=f"الملف أكبر من الحد الأقصى ({settings.MAX_FILE_SIZE_MB} ميجابايت)",
                )
            await buffer.write(chunk)

    file_size = total_bytes

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

    transcript = Transcript(video_id=video_id)
    db.add(transcript)
    db.commit()
    db.refresh(video)

    background_tasks.add_task(
        run_transcription_task,
        video_id  = video_id,
        file_path = file_path,
        language  = dialect if len(dialect) == 2 else "ar",
        noise_reduction = noise_reduction,
    )

    response = VideoResponse.model_validate(video)
    response.transcript_status = TranscriptStatus.PENDING
    return response


# ══════════════════════════════════════════════════════
#  GET /api/videos/my
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
#  GET /api/videos/share/{token}
# ══════════════════════════════════════════════════════
@router.get("/share/{token}", response_model=VideoResponse)
def get_video_by_share_token(token: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.share_token == token).first()
    if not video:
        raise HTTPException(status_code=404, detail="الرابط غير صحيح أو منتهي")

    # تحقق من انتهاء الصلاحية
    if video.share_expires_at and video.share_expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=410, detail="انتهت صلاحية رابط المشاركة")

    # تحقق من كلمة المرور
    if video.share_password_hash:
        return {
            "id": video.id,
            "title": video.title,
            "requires_password": True,
            "share_token": video.share_token,
        }

    video.views_count += 1
    db.commit()
    r = VideoResponse.model_validate(video)
    r.transcript_status = video.transcript.status if video.transcript else None
    return r


# ══════════════════════════════════════════════════════
#  GET /api/videos/share/{token}/stream
# ══════════════════════════════════════════════════════
@router.get("/share/{token}/stream")
def stream_video_by_share_token(token: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.share_token == token).first()
    if not video:
        raise HTTPException(status_code=404, detail="الرابط غير صحيح أو منتهي")

    if video.share_expires_at and video.share_expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=410, detail="انتهت صلاحية رابط المشاركة")

    if video.share_password_hash:
        raise HTTPException(status_code=401, detail="يتطلب كلمة مرور")

    if not os.path.exists(video.file_path):
        raise HTTPException(status_code=404, detail="الملف غير موجود على الخادم")

    return FileResponse(
        path        = video.file_path,
        media_type  = video.mime_type or "application/octet-stream",
        filename    = Path(video.file_path).name,
        headers     = {"Accept-Ranges": "bytes"},
    )


# ══════════════════════════════════════════════════════
#  PATCH /api/videos/{id}/share-settings  (Feature 4)
# ══════════════════════════════════════════════════════
@router.patch("/{video_id}/share-settings")
def update_share_settings(
    video_id:     str,
    data:         ShareSettingsRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(require_auth),
):
    video = db.query(Video).filter(
        Video.id == video_id, Video.owner_id == current_user.id
    ).first()
    if not video:
        raise HTTPException(404, "الفيديو غير موجود أو ليس لديك صلاحية")

    if data.password is not None:
        if data.password == "":
            video.share_password_hash = None
        else:
            video.share_password_hash = hash_password(data.password)

    if data.expires_in_days is not None:
        if data.expires_in_days <= 0:
            video.share_expires_at = None
        else:
            video.share_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=data.expires_in_days)

    db.commit()
    return {"message": "تم تحديث إعدادات المشاركة"}


# ══════════════════════════════════════════════════════
#  POST /api/videos/share/{token}/unlock  (Feature 4)
# ══════════════════════════════════════════════════════
@router.post("/share/{token}/unlock")
def unlock_shared_video(
    token: str,
    data:  UnlockShareRequest,
    db:    Session = Depends(get_db),
):
    video = db.query(Video).filter(Video.share_token == token).first()
    if not video:
        raise HTTPException(404, "الرابط غير صحيح")

    if video.share_expires_at and video.share_expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(410, "انتهت صلاحية رابط المشاركة")

    if not video.share_password_hash:
        raise HTTPException(400, "هذا الفيديو لا يتطلب كلمة مرور")

    if not verify_password(data.password, video.share_password_hash):
        raise APIException(401, "كلمة المرور غير صحيحة", error_code="WRONG_PASSWORD")

    from app.auth import create_access_token
    access_token = create_access_token(
        {"sub": video.owner_id or "guest", "video_id": video.id, "type": "share_access"},
        timedelta(hours=1),
    )
    video.views_count += 1
    db.commit()

    return {"access_token": access_token}


# ══════════════════════════════════════════════════════
#  GET /api/videos/{id}
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

    if not video.is_public:
        if not current_user or video.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="ليس لديك صلاحية لمشاهدة هذا الفيديو")

    video.views_count += 1
    db.commit()

    r = VideoResponse.model_validate(video)
    r.transcript_status = video.transcript.status if video.transcript else None
    return r


# ══════════════════════════════════════════════════════
#  GET /api/videos/{id}/stream
# ══════════════════════════════════════════════════════
@router.get("/{video_id}/stream")
def stream_video(
    video_id:     str,
    db:           Session       = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
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
#  GET /api/videos/{id}/hls/playlist.m3u8  (Feature 6)
# ══════════════════════════════════════════════════════
@router.get("/{video_id}/hls/playlist.m3u8")
def get_hls_playlist(
    video_id:     str,
    db:           Session       = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "الفيديو غير موجود")

    if not video.hls_ready or not video.hls_playlist_path:
        raise HTTPException(404, "HLS غير جاهز بعد")

    if not os.path.exists(video.hls_playlist_path):
        raise HTTPException(404, "ملف HLS غير موجود")

    return FileResponse(
        path=video.hls_playlist_path,
        media_type="application/vnd.apple.mpegurl",
        headers={
            "Cache-Control": "public, max-age=10",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ══════════════════════════════════════════════════════
#  POST /api/videos/{id}/hls/convert  (Feature 6)
# ══════════════════════════════════════════════════════
@router.post("/{video_id}/hls/convert")
def trigger_hls_conversion(
    video_id:         str,
    background_tasks: BackgroundTasks,
    db:               Session = Depends(get_db),
    current_user:     User    = Depends(require_auth),
):
    video = db.query(Video).filter(
        Video.id == video_id, Video.owner_id == current_user.id
    ).first()
    if not video:
        raise HTTPException(404, "الفيديو غير موجود أو ليس لديك صلاحية")

    background_tasks.add_task(
        _run_hls_conversion,
        video_id=video_id,
        input_path=video.file_path,
        upload_dir=settings.UPLOAD_DIR,
    )

    return {"message": "بدأ التحويل إلى HLS في الخلفية"}


def _run_hls_conversion(video_id: str, input_path: str, upload_dir: str):
    from app.database import SessionLocal, Video
    db = SessionLocal()
    try:
        from app.hls import convert_to_hls
        playlist_path = convert_to_hls(video_id, input_path, upload_dir)
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.hls_playlist_path = playlist_path
            video.hls_ready = True
            db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"HLS conversion failed: {e}")
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.hls_ready = False
            db.commit()
    finally:
        db.close()


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

    if os.path.exists(video.file_path):
        os.remove(video.file_path)

    db.delete(video)
    db.commit()
