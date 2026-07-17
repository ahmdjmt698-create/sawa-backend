"""
تحويل الفيديوهات إلى تنسيق HLS — Feature 6
يعمل كمهمة خلفية بعد رفع الفيديو مباشرة
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_to_hls(video_id: str, input_path: str, upload_dir: str) -> str:
    """
    يحوّل ملف فيديو إلى تنسيق HLS (HTTP Live Streaming).

    يُنشئ:
        uploads/hls/{video_id}/
            playlist.m3u8     ← قائمة التشغيل الرئيسية
            seg_000.ts        ← مقاطع فيديو (كل 6 ثوانٍ)
            seg_001.ts
            ...

    يُعيد مسار ملف m3u8 أو يرفع استثناءً عند الفشل.
    """
    try:
        import ffmpeg
    except ImportError:
        raise ImportError("ffmpeg-python غير مثبت. شغّل: pip install ffmpeg-python")

    if not Path(input_path).exists():
        raise FileNotFoundError(f"الملف المدخل غير موجود: {input_path}")

    # مجلد HLS الخاص بهذا الفيديو
    hls_dir = os.path.join(upload_dir, "hls", video_id)
    os.makedirs(hls_dir, exist_ok=True)

    playlist_path = os.path.join(hls_dir, "playlist.m3u8")
    segment_pattern = os.path.join(hls_dir, "seg_%03d.ts")

    logger.info(f"🎬 [HLS] بدء تحويل: {input_path}")

    try:
        (
            ffmpeg
            .input(input_path)
            .output(
                playlist_path,
                format="hls",
                hls_time=6,               # كل مقطع 6 ثوانٍ
                hls_playlist_type="vod",  # VOD (ليس live)
                hls_segment_filename=segment_pattern,
                vcodec="libx264",         # H.264 — دعم واسع
                acodec="aac",
                video_bitrate="800k",
                audio_bitrate="128k",
                # تقليص الدقة إلى 720p للأداء
                vf="scale=w=1280:h=720:force_original_aspect_ratio=decrease",
            )
            .overwrite_output()
            .run(quiet=True)
        )

        logger.info(f"✅ [HLS] اكتمل التحويل: {playlist_path}")
        return playlist_path

    except ffmpeg.Error as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"❌ [HLS] فشل ffmpeg: {error_msg}")
        raise RuntimeError(f"فشل تحويل HLS: {error_msg}")


def run_hls_conversion_task(video_id: str, input_path: str, upload_dir: str):
    """
    مهمة خلفية: تحوّل الفيديو وتحدّث قاعدة البيانات.
    تُستدعى من BackgroundTasks بعد الرفع.
    """
    from app.database import SessionLocal, Video

    db = SessionLocal()
    try:
        playlist_path = convert_to_hls(video_id, input_path, upload_dir)

        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.hls_playlist_path = playlist_path
            video.hls_ready = True
            db.commit()
            logger.info(f"✅ [HLS] تم تحديث قاعدة البيانات للفيديو {video_id[:8]}")

    except Exception as e:
        logger.error(f"❌ [HLS] فشل التحويل للفيديو {video_id[:8]}: {e}")
        # لا نوقف التطبيق — HLS اختياري
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.hls_ready = False
            db.commit()
    finally:
        db.close()
