# سوى — Backend 🎙️

> بديل Loom العربي مع تفريغ صوت ذكي

---

## 🚀 تشغيل المشروع (خطوة بخطوة)

### 1. تثبيت المتطلبات

```bash
pip install -r requirements.txt
```

### 2. إعداد ملف البيئة

```bash
cp .env.example .env
# عدّل .env حسب بيئتك
```

### 3. تشغيل السيرفر

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. افتح التوثيق التلقائي

```
http://localhost:8000/docs
```

---

## 📁 هيكل المشروع

```
sawa-backend/
├── app/
│   ├── main.py           # نقطة دخول التطبيق
│   ├── config.py         # الإعدادات المركزية
│   ├── database.py       # نماذج قاعدة البيانات
│   ├── auth.py           # JWT + كلمات المرور
│   ├── transcription.py  # نموذج Whisper (القلب)
│   └── routers/
│       ├── auth.py       # تسجيل + دخول
│       ├── videos.py     # رفع + جلب + حذف
│       └── transcripts.py # جلب + تعديل + تصدير
├── uploads/              # ملفات الفيديو (تُنشأ تلقائياً)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🔌 API Endpoints

### المصادقة

| الطريقة | المسار               | الوصف                  |
| ------- | -------------------- | ---------------------- |
| POST    | `/api/auth/register` | تسجيل مستخدم جديد      |
| POST    | `/api/auth/login`    | تسجيل الدخول           |
| GET     | `/api/auth/me`       | بيانات المستخدم الحالي |

### الفيديوهات

| الطريقة | المسار                      | الوصف                   |
| ------- | --------------------------- | ----------------------- |
| POST    | `/api/videos/upload`        | رفع فيديو + بدء التفريغ |
| GET     | `/api/videos/my`            | فيديوهات المستخدم       |
| GET     | `/api/videos/{id}`          | فيديو بعينه             |
| GET     | `/api/videos/share/{token}` | رابط المشاركة العام     |
| DELETE  | `/api/videos/{id}`          | حذف فيديو               |

### التفريغ

| الطريقة | المسار                                       | الوصف                |
| ------- | -------------------------------------------- | -------------------- |
| GET     | `/api/transcripts/{video_id}`                | جلب النص المفرَّغ    |
| PATCH   | `/api/transcripts/{video_id}`                | تعديل النص يدوياً    |
| POST    | `/api/transcripts/{video_id}/retry`          | إعادة التفريغ        |
| GET     | `/api/transcripts/{video_id}/export?fmt=srt` | تصدير (txt/srt/json) |

---

## 🎙️ اختبار التفريغ بسرعة

```python
# test_transcription.py
from app.transcription import transcribe_audio

result = transcribe_audio("test_audio.mp3", language="ar")
print(result["full_text"])
print(f"استغرق {result['processing_time']} ثانية")
```

```bash
python test_transcription.py
```

---

## 📊 نماذج Whisper — اختر حسب احتياجك

| النموذج    | الحجم  | السرعة     | الدقة      |
| ---------- | ------ | ---------- | ---------- |
| `tiny`     | 75 MB  | ⚡⚡⚡⚡⚡ | ⭐⭐       |
| `base`     | 145 MB | ⚡⚡⚡⚡   | ⭐⭐⭐     |
| `small`    | 480 MB | ⚡⚡⚡     | ⭐⭐⭐⭐   |
| `large-v3` | 1.5 GB | ⚡         | ⭐⭐⭐⭐⭐ |

> للتطوير: `base` ✅  
> للإنتاج: `large-v3` ✅

---
