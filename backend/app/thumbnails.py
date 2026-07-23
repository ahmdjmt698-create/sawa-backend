"""
توليد الصور المصغرة للفيديوهات عبر ffmpeg
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_thumbnail(video_path: str, video_id: str, timestamp: float = 2.0) -> str:
    """
    يستخرج إطاراً من الفيديو عند توقيت معين كصورة مصغرة.

    Args:
        video_path: مسار ملف الفيديو
        video_id: معرّف الفيديو
        timestamp: التوقيت بالثواني (الافتراضي: ثانيتين)

    Returns:
        مسار ملف الصورة المصغرة
    """
    try:
        import ffmpeg
    except ImportError:
        raise ImportError("ffmpeg-python غير مثبت")

    if not Path(video_path).exists():
        raise FileNotFoundError(f"الملف غير موجود: {video_path}")

    thumbnail_dir = os.path.join("thumbnails", video_id)
    os.makedirs(thumbnail_dir, exist_ok=True)
    thumbnail_path = os.path.join(thumbnail_dir, "thumb.jpg")

    try:
        (
            ffmpeg
            .input(video_path, ss=timestamp)
            .output(
                thumbnail_path,
                vframes=1,
                vf="scale=640:-2",
                **{"q:v": "3"},
            )
            .overwrite_output()
            .run(quiet=True, overwrite_output=True)
        )

        logger.info(f"🖼️ [Thumbnail] تم إنشاء الصورة المصغرة: {thumbnail_path}")
        return thumbnail_path

    except ffmpeg.Error as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"❌ [Thumbnail] فشل ffmpeg: {error_msg}")
        raise RuntimeError(f"فشل إنشاء الصورة المصغرة: {error_msg}")


def run_thumbnail_task(video_id: str, file_path: str):
    """
    مهمة خلفية: توليد صورة مصغرة وتحديث قاعدة البيانات.
    """
    from app.database import SessionLocal, Video

    db = SessionLocal()
    try:
        thumbnail_path = generate_thumbnail(file_path, video_id)
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.thumbnail_path = thumbnail_path
            db.commit()
            logger.info(f"🖼️ [Thumbnail] تم حفظ المسار في قاعدة البيانات للفيديو {video_id[:8]}")
    except Exception as e:
        logger.error(f"❌ [Thumbnail] فشل توليد الصورة المصغرة للفيديو {video_id[:8]}: {e}")
    finally:
        db.close()
