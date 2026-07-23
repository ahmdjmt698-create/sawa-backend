"""
توليد الصور المصغرة للفيديوهات عبر ffmpeg
يولّد محلياً ثم يرفع إلى R2 إن كان التخزين سحابياً
"""
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def generate_thumbnail(video_path: str, video_id: str, timestamp: float = 2.0, storage=None) -> str:
    """
    يستخرج إطاراً من الفيديو عند توقيت معين كصورة مصغرة.
    إذا كان storage مُعطىً (R2)، يرفع الصورة ويعيد المفتاح السحابي.
    وإلا يعيد المسار المحلي.

    Args:
        video_path: مسار ملف الفيديو (محلي — مطلوب لـ ffmpeg)
        video_id: معرّف الفيديو
        timestamp: التوقيت بالثواني (الافتراضي: ثانيتين)
        storage: كائن StorageBackend (اختياري — للرفع إلى R2)

    Returns:
        مفتاح التخزين (R2 key أو مسار محلي)
    """
    try:
        import ffmpeg
    except ImportError:
        raise ImportError("ffmpeg-python غير مثبت")

    if not Path(video_path).exists():
        raise FileNotFoundError(f"الملف غير موجود: {video_path}")

    # ── ولّد محلياً (ffmpeg يحتاج مسار محلي) ──
    thumbnail_dir = os.path.join("thumbnails", video_id)
    os.makedirs(thumbnail_dir, exist_ok=True)
    local_path = os.path.join(thumbnail_dir, "thumb.jpg")

    try:
        (
            ffmpeg
            .input(video_path, ss=timestamp)
            .output(
                local_path,
                vframes=1,
                vf="scale=640:-2",
                **{"q:v": "3"},
            )
            .overwrite_output()
            .run(quiet=True, overwrite_output=True)
        )

        logger.info(f"🖼️ [Thumbnail] تم إنشاء الصورة المصغرة: {local_path}")

    except ffmpeg.Error as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"❌ [Thumbnail] فشل ffmpeg: {error_msg}")
        raise RuntimeError(f"فشل إنشاء الصورة المصغرة: {error_msg}")

    # ── ارفع إلى R2 إن كان التخزين سحابياً ──
    if storage is not None and hasattr(storage, "client") and hasattr(storage, "bucket"):
        r2_key = f"hls/{video_id}/thumb.jpg"
        try:
            with open(local_path, "rb") as f:
                storage.put(r2_key, f.read(), "image/jpeg")
            logger.info(f"🖼️ [Thumbnail] تم الرفع إلى R2: {r2_key}")
            # نظّف الملف المحلي
            os.remove(local_path)
            return r2_key
        except Exception as e:
            logger.warning(f"⚠️ [Thumbnail] فشل الرفع إلى R2، نعيد المسار المحلي: {e}")

    return local_path


def run_thumbnail_task(video_id: str, file_path: str):
    """
    مهمة خلفية: توليد صورة مصغرة وتحديث قاعدة البيانات.
    """
    from app.database import SessionLocal, Video

    db = SessionLocal()
    try:
        from app.storage import storage
        store = storage()
        thumbnail_key = generate_thumbnail(file_path, video_id, storage=store)
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.thumbnail_path = thumbnail_key
            db.commit()
            logger.info(f"🖼️ [Thumbnail] تم حفظ المفتاح في قاعدة البيانات للفيديو {video_id[:8]}: {thumbnail_key}")
    except Exception as e:
        logger.error(f"❌ [Thumbnail] فشل توليد الصورة المصغرة للفيديو {video_id[:8]}: {e}")
    finally:
        db.close()
