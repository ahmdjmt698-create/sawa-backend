"""
خدمة التفريغ الصوتي بالذكاء الاصطناعي
Gemini (رئيسي) → Groq (بديل) → faster-whisper (محلي)
"""
import time
import json
import logging
import os
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
#  Gemini (المزود الرئيسي — يدعم العربية بشكل ممتاز)
# ══════════════════════════════════════════════════════
def transcribe_with_gemini(file_path: str, language: str = "ar") -> dict:
    """
    يفرّغ الملف الصوتي باستخدام Gemini 1.5 Flash.
    يدعم العربية ومختلف اللهجات.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY غير موجود في .env")

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    logger.info(f"🎙️ [Gemini] بدء تفريغ: {file_path}")

    # اقرأ الملف كبيانات خام
    file_ext = Path(file_path).suffix.lower()
    mime_map = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
    }
    mime_type = mime_map.get(file_ext, "audio/wav")

    with open(file_path, "rb") as f:
        audio_data = f.read()

    prompt = """أنت مساعد متخصص في التفريغ الصوتي. فرّغ الملف الصوتي المرفق بدقة عالية.

أرجع النتيجة بالضبط بهذا الشكل JSON (بدون أي نص إضافي خارج الـ JSON):
{
  "full_text": "النص الكامل المفرَّغ",
  "segments": [
    {"start": 0.0, "end": 2.5, "text": "الجملة الأولى"},
    {"start": 2.5, "end": 5.1, "text": "الجملة الثانية"}
  ],
  "language_detected": "ar"
}

التعليمات:
- احفظ الطوابع الزمنية (start/end) بالثواني بدقة
- اقسم النص إلى جمل قصيرة (3-10 ثوانٍ لكل مقطع)
- لا تُخترع توقيتاً — استخدم التوقيت الحقيقي من الملف
- تعرّف على اللهجة إذا مختلفة عن الفصحى"""

    start_time = time.time()

    try:
        response = model.generate_content([
            prompt,
            {"mime_data": {"data": audio_data, "mime_type": mime_type}},
        ])

        raw_text = response.text.strip()
        # نظّف الـ JSON
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        result = json.loads(raw_text)
        processing_time = round(time.time() - start_time, 2)

        # تحقق من صحة البنية
        if "full_text" not in result:
            raise ValueError("استجابة Gemini لا تحتوي على full_text")
        if "segments" not in result:
            result["segments"] = []

        result["processing_time"] = processing_time
        result.setdefault("language_detected", language)
        result.setdefault("segments_count", len(result["segments"]))

        logger.info(f"✅ [Gemini] اكتمل التفريغ في {processing_time}s — {len(result['segments'])} مقطع")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"❌ [Gemini] فشل تحليل JSON: {e}")
        raise ValueError(f"فشل تحليل استجابة Gemini: {e}")
    except Exception as e:
        logger.error(f"❌ [Gemini] خطأ: {e}")
        raise


# ══════════════════════════════════════════════════════
#  Groq (المزود البديل — سريع جداً)
# ══════════════════════════════════════════════════════
def transcribe_with_groq(file_path: str, language: str = "ar") -> dict:
    """
    يفرّغ الملف باستخدام Groq Whisper API.
    سريع جداً ويدعم العربية.
    """
    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise ValueError("GROQ_API_KEY غير موجود في .env")

    from groq import Groq

    client = Groq(api_key=api_key)
    logger.info(f"🎙️ [Groq] بدء تفريغ: {file_path}")

    start_time = time.time()

    with open(file_path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=(Path(file_path).name, f.read()),
            model="whisper-large-v3-turbo",
            language=language,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    processing_time = round(time.time() - start_time, 2)

    segments = []
    full_parts = []
    for seg in result.segments:
        text = seg.text.strip()
        if text:
            segments.append({
                "start": round(seg.start, 2),
                "end":   round(seg.end, 2),
                "text":  text,
            })
            full_parts.append(text)

    output = {
        "full_text":         " ".join(full_parts),
        "segments":          segments,
        "language_detected": getattr(result, "language", language),
        "processing_time":   processing_time,
        "segments_count":    len(segments),
    }

    logger.info(f"✅ [Groq] اكتمل التفريغ في {processing_time}s — {len(segments)} مقطع")
    return output


# ══════════════════════════════════════════════════════
#  faster-whisper (المحلي — كخيار أخير)
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
            logger.error("❌ faster-whisper غير مثبت.")
            raise
    return _whisper_model


def transcribe_with_local_whisper(file_path: str, language: str = "ar") -> dict:
    model    = get_whisper_model()
    start_ts = time.time()

    logger.info(f"🎙️ [Local Whisper] بدء تفريغ: {file_path}")

    segments_iter, info = model.transcribe(
        file_path,
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        word_timestamps=True,
    )

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

        if seg.words:
            segment_data["words"] = [
                {"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)}
                for w in seg.words
            ]

        segments.append(segment_data)
        full_parts.append(text)

    processing_time = round(time.time() - start_ts, 2)

    logger.info(f"✅ [Local Whisper] اكتمل في {processing_time}s — {len(segments)} مقطع")

    return {
        "full_text":         " ".join(full_parts),
        "segments":          segments,
        "language_detected": info.language,
        "language_prob":     round(info.language_probability, 3),
        "processing_time":   processing_time,
        "segments_count":    len(segments),
    }


# ══════════════════════════════════════════════════════
#  الدالة الرئيسية — سلسلة التخفيض (Fallback Chain)
# ══════════════════════════════════════════════════════
def transcribe_audio(
    file_path: str,
    language: str = "ar",
    dialect_hint: Optional[str] = None,
) -> dict:
    """
    تفرّغ ملف صوتي أو فيديو — يجرّب المزودات بالترتيب:
    1. Gemini (الرئيسي)
    2. Groq (بديل)
    3. faster-whisper (محلي)
    """
    if not Path(file_path).exists():
        raise FileNotFoundError(f"الملف غير موجود: {file_path}")

    provider = settings.TRANSCRIPTION_PROVIDER.lower()
    providers = []

    if provider == "gemini":
        providers = [
            ("gemini", transcribe_with_gemini),
            ("groq", transcribe_with_groq),
            ("local", transcribe_with_local_whisper),
        ]
    elif provider == "groq":
        providers = [
            ("groq", transcribe_with_groq),
            ("gemini", transcribe_with_gemini),
            ("local", transcribe_with_local_whisper),
        ]
    else:
        providers = [
            ("local", transcribe_with_local_whisper),
            ("gemini", transcribe_with_gemini),
            ("groq", transcribe_with_groq),
        ]

    errors = []
    for name, func in providers:
        try:
            logger.info(f"🔄 محاولة التفريغ عبر: {name}")
            result = func(file_path, language=language)
            result["provider"] = name
            return result
        except Exception as e:
            logger.warning(f"⚠️ فشل {name}: {e}")
            errors.append(f"{name}: {str(e)}")
            continue

    raise RuntimeError(
        f"فشلت جميع مزودات التفريغ:\n" + "\n".join(errors)
    )


# ══════════════════════════════════════════════════════
#  تقليل الضوضاء بـ ffmpeg afftdn
# ══════════════════════════════════════════════════════
def denoise_audio(input_path: str) -> str:
    """
    ينظف الصوت باستخدام فلتر afftdn في ffmpeg.
    يُنشئ ملفاً جديداً بجانب الأصلي ويعيد مساره.
    """
    import subprocess

    input_p = Path(input_path)
    denoised_path = input_p.with_name(f"{input_p.stem}_denoised{input_p.suffix}")

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", "afftdn=nf=-25,highpass=f=80,lowpass=f=12000",
        "-ar", "16000",
        str(denoised_path),
    ]

    logger.info(f"🔇 بدء تنظيف الصوت: {input_path}")
    result = subprocess.run(cmd, capture_output=True, timeout=600)

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        logger.error(f"❌ فشل تنظيف الصوت: {stderr[-500:]}")
        raise RuntimeError(f"ffmpeg denoise failed: {stderr[-200:]}")

    logger.info(f"✅ تم تنظيف الصوت: {denoised_path}")
    return str(denoised_path)


# ══════════════════════════════════════════════════════
#  استخراج الصوت من الفيديو
# ══════════════════════════════════════════════════════
def extract_audio_if_needed(video_path: str) -> str:
    path = Path(video_path)
    if path.suffix.lower() in [".mp3", ".wav", ".m4a", ".flac"]:
        return video_path
    return video_path
