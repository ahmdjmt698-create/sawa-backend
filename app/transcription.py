"""
خدمة التفريغ الصوتي بالذكاء الاصطناعي
قلب مشروع سوى — faster-whisper + دعم كامل للعربية
"""
import time
import json
import logging
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════
#  تحميل النموذج مرة واحدة عند بدء التطبيق
#  (تحميله كل طلب = بطيء جداً)
# ══════════════════════════════════════════════════════
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logger.info(f"⏳ تحميل نموذج Whisper ({settings.WHISPER_MODEL})...")
        try:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel(
                settings.WHISPER_MODEL,
                device=settings.WHISPER_DEVICE,
                compute_type=settings.WHISPER_COMPUTE_TYPE,
            )
            logger.info("✅ تم تحميل نموذج Whisper بنجاح")
        except ImportError:
            logger.error("❌ faster-whisper غير مثبت. شغّل: pip install faster-whisper")
            raise
    return _whisper_model


# ══════════════════════════════════════════════════════
#  دالة التفريغ الرئيسية
# ══════════════════════════════════════════════════════
def transcribe_audio(
    file_path: str,
    language: str = "ar",
    dialect_hint: Optional[str] = None,
) -> dict:
    """
    تفرّغ ملف صوتي أو فيديو إلى نص عربي

    المعاملات:
        file_path    : مسار الملف (mp4, webm, mp3, wav...)
        language     : رمز اللغة — "ar" للعربية
        dialect_hint : تلميح اللهجة (للمعالجة المستقبلية)

    تُرجع:
        {
            "full_text": "...",
            "segments": [{"start": 0.0, "end": 2.5, "text": "..."}, ...],
            "language_detected": "ar",
            "processing_time": 4.2,
        }
    """
    if not Path(file_path).exists():
        raise FileNotFoundError(f"الملف غير موجود: {file_path}")

    model    = get_whisper_model()
    start_ts = time.time()

    logger.info(f"🎙️ بدء تفريغ: {file_path}")

    # ── التفريغ ──────────────────────────────────────
    segments_iter, info = model.transcribe(
        file_path,
        language=language,
        beam_size=5,            # دقة أعلى من beam_size=1
        vad_filter=True,        # يتجاهل الصمت تلقائياً
        vad_parameters=dict(
            min_silence_duration_ms=500,  # صمت 0.5 ثانية = نهاية جملة
        ),
        word_timestamps=True,   # طوابع زمنية على مستوى الكلمة
    )

    # ── تجميع النتائج ────────────────────────────────
    segments   = []
    full_parts = []

    for seg in segments_iter:
        text = seg.text.strip()
        if not text:
            continue

        segment_data = {
            "start": round(seg.start, 2),
            "end":   round(seg.end,   2),
            "text":  text,
        }

        # كلمات منفردة مع طوابعها (للـ karaoke-style highlighting)
        if seg.words:
            segment_data["words"] = [
                {
                    "word":  w.word.strip(),
                    "start": round(w.start, 2),
                    "end":   round(w.end,   2),
                }
                for w in seg.words
            ]

        segments.append(segment_data)
        full_parts.append(text)

    processing_time = round(time.time() - start_ts, 2)
    full_text = " ".join(full_parts)

    logger.info(f"✅ اكتمل التفريغ في {processing_time} ثانية — {len(segments)} مقطع")

    return {
        "full_text":         full_text,
        "segments":          segments,
        "language_detected": info.language,
        "language_prob":     round(info.language_probability, 3),
        "processing_time":   processing_time,
        "segments_count":    len(segments),
    }


# ══════════════════════════════════════════════════════
#  استخراج الصوت من الفيديو (إذا لزم)
# ══════════════════════════════════════════════════════
def extract_audio_if_needed(video_path: str) -> str:
    """
    Whisper يقبل mp4 مباشرة في معظم الحالات،
    لكن إذا كان الملف webm أو نادراً → نستخرج الصوت أولاً
    """
    path = Path(video_path)
    if path.suffix.lower() in [".mp3", ".wav", ".m4a", ".flac"]:
        return video_path  # صوت بالفعل، لا داعي للاستخراج

    # للفيديو: Whisper يعالجه مباشرة بدون ffmpeg في معظم الحالات
    # إذا واجهت مشكلة، فعّل هذا الكود:
    # audio_path = str(path.with_suffix(".wav"))
    # os.system(f'ffmpeg -i "{video_path}" -ar 16000 -ac 1 "{audio_path}" -y')
    # return audio_path

    return video_path


# ══════════════════════════════════════════════════════
#  اكتشاف لغة الملف (اختياري — قبل التفريغ الكامل)
# ══════════════════════════════════════════════════════
def detect_language(file_path: str) -> dict:
    """
    يكتشف لغة الملف الصوتي بسرعة دون تفريغ كامل
    يفيد لتأكيد أن المستخدم رفع ملفاً عربياً فعلاً
    """
    model    = get_whisper_model()
    import numpy as np
    import soundfile as sf

    # خذ أول 30 ثانية فقط للكشف السريع
    try:
        audio, sr = sf.read(file_path, frames=sr * 30 if (sr := 16000) else 16000 * 30)
        audio = audio.astype(np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)  # stereo → mono
    except Exception:
        return {"language": "unknown", "probability": 0.0}

    _, info = model.transcribe(file_path, language=None)
    return {
        "language":    info.language,
        "probability": round(info.language_probability, 3),
    }
