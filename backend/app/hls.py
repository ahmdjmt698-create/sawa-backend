"""
تحويل الفيديوهات إلى تنسيق HLS — عالي الجودة مع عدة دقات
يولّد محلياً ثم يرفع إلى R2 إن كان التخزين سحابياً
"""
import os
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# ── إعدادات الدقات المتعددة ─────────────────────────
RENDITIONS = [
    {"suffix": "360p",  "height": 360,  "video_bitrate": "500k",  "maxrate": "550k",  "bufsize": "1000k"},
    {"suffix": "720p",  "height": 720,  "video_bitrate": "1500k", "maxrate": "1650k", "bufsize": "3000k"},
    {"suffix": "1080p", "height": 1080, "video_bitrate": "3000k", "maxrate": "3300k", "bufsize": "6000k"},
]

# ── Content-Type حسب الامتداد ────────────────────────
_CONTENT_TYPES = {
    ".m3u8": "application/vnd.apple.mpegurl",
    ".ts":   "video/mp2t",
}


def _get_video_height(input_path: str) -> int:
    """يجلب ارتفاع الفيديو الأصلي عبر ffprobe."""
    try:
        import ffmpeg
        probe = ffmpeg.probe(input_path)
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "video":
                return stream.get("height", 720)
    except Exception:
        pass
    return 720


def convert_to_hls(video_id: str, input_path: str, storage_key: str = None, storage=None) -> str:
    """
    يحوّل ملف فيديو إلى تنسيق HLS مع عدة دقات (adaptive bitrate).

    يولّد الملفات محلياً (ffmpeg يحتاج مسار محلي)، ثم يرفعها إلى R2 إن كان
    التخزين سحابياً. يُعيد مفتاح التخزين (R2 key أو مسار محلي) لـ master.m3u8.
    """
    try:
        import ffmpeg
    except ImportError:
        raise ImportError("ffmpeg-python غير مثبت. شغّل: pip install ffmpeg-python")

    if not Path(input_path).exists():
        raise FileNotFoundError(f"الملف المدخل غير موجود: {input_path}")

    original_height = _get_video_height(input_path)

    active_renditions = [r for r in RENDITIONS if r["height"] <= original_height]
    if not active_renditions:
        active_renditions = [RENDITIONS[0]]

    hls_dir = os.path.join("hls", video_id)
    os.makedirs(hls_dir, exist_ok=True)

    playlist_paths = []

    for rendition in active_renditions:
        r_dir = os.path.join(hls_dir, rendition["suffix"])
        os.makedirs(r_dir, exist_ok=True)

        playlist_path = os.path.join(r_dir, "playlist.m3u8")
        segment_pattern = os.path.join(r_dir, "seg_%03d.ts")

        logger.info(f"🎬 [HLS] تحويل {rendition['suffix']} للفيديو {video_id[:8]}...")

        try:
            (
                ffmpeg
                .input(input_path)
                .output(
                    playlist_path,
                    format="hls",
                    hls_time=6,
                    hls_playlist_type="vod",
                    hls_segment_filename=segment_pattern,
                    vcodec="libx264",
                    preset="medium",
                    acodec="aac",
                    audio_bitrate="128k",
                    video_bitrate=rendition["video_bitrate"],
                    maxrate=rendition["maxrate"],
                    bufsize=rendition["bufsize"],
                    vf=f"scale=w=-2:h={rendition['height']}:force_original_aspect_ratio=decrease",
                    **{"movflags": "+faststart"},
                )
                .overwrite_output()
                .run(quiet=True, overwrite_output=True)
            )
            playlist_paths.append((rendition["suffix"], playlist_path))
            logger.info(f"✅ [HLS] اكتمل {rendition['suffix']}: {playlist_path}")

        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"❌ [HLS] فشل {rendition['suffix']}: {error_msg}")
            continue

    if not playlist_paths:
        raise RuntimeError("فشل تحويل HLS لجميع الدقات")

    master_path = os.path.join(hls_dir, "master.m3u8")
    _write_master_playlist(master_path, playlist_paths)

    logger.info(f"✅ [HLS] اكتمل التحويل محلياً: {len(active_renditions)} دقة — {master_path}")

    # ── ارفع إلى R2 إن كان التخزين سحابياً ──
    if storage is not None and hasattr(storage, "client") and hasattr(storage, "bucket"):
        r2_master_key = _upload_hls_to_r2(hls_dir, video_id, storage)
        # نظّف الملفات المحلية بعد الرفع
        shutil.rmtree(hls_dir, ignore_errors=True)
        return r2_master_key

    return master_path


def _write_master_playlist(master_path: str, playlist_paths: list):
    """يكتب master.m3u8 مع جميع الدقات."""
    lines = ["#EXTM3U", "#EXT-X-VERSION:3", ""]

    height_map = {r["suffix"]: r["height"] for r in RENDITIONS}

    for suffix, path in playlist_paths:
        h = height_map.get(suffix, 720)
        relative_path = os.path.relpath(path, os.path.dirname(master_path))
        lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH={h * 1000},RESOLUTION={int(h * 16/9)}x{h},NAME=\"{suffix}\"")
        lines.append(relative_path)
        lines.append("")

    os.makedirs(os.path.dirname(master_path), exist_ok=True)
    with open(master_path, "w") as f:
        f.write("\n".join(lines))


def _upload_hls_to_r2(hls_dir: str, video_id: str, storage) -> str:
    """
    يرفع جميع ملفات HLS إلى R2 ويعيد مفتاح master.m3u8.
    """
    r2_prefix = f"hls/{video_id}"
    master_r2_key = None

    for root, _dirs, files in os.walk(hls_dir):
        for fname in files:
            local_file = os.path.join(root, fname)
            rel_path = os.path.relpath(local_file, hls_dir)
            r2_key = f"{r2_prefix}/{rel_path}"

            ext = os.path.splitext(fname)[1].lower()
            content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")

            with open(local_file, "rb") as f:
                storage.put(r2_key, f.read(), content_type)

            if fname == "master.m3u8":
                master_r2_key = r2_key

            logger.debug(f"📤 [HLS→R2] {r2_key}")

    if not master_r2_key:
        raise RuntimeError("master.m3u8 not found after R2 upload")

    logger.info(f"✅ [HLS→R2] تم رفع {r2_prefix}/ إلى R2 — master: {master_r2_key}")
    return master_r2_key


def run_hls_conversion_task(video_id: str, file_path: str, storage_key: str = None):
    """
    مهمة خلفية: تحوّل الفيديو وتحدّث قاعدة البيانات.
    تُستدعى من BackgroundTasks بعد الرفع.
    """
    from app.database import SessionLocal, Video

    db = SessionLocal()
    try:
        from app.storage import storage
        store = storage()
        playlist_path = convert_to_hls(video_id, file_path, storage_key, store)

        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.hls_playlist_path = playlist_path
            video.hls_ready = True
            db.commit()
            logger.info(f"✅ [HLS] تم تحديث قاعدة البيانات للفيديو {video_id[:8]}")

    except Exception as e:
        logger.error(f"❌ [HLS] فشل التحويل للفيديو {video_id[:8]}: {e}")
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.hls_ready = False
            db.commit()
    finally:
        db.close()
