# 1. استخدام نسخة خفيفة جداً من بايثون لتقليل استهلاك الـ RAM والقرص
FROM python:3.10-slim

# 2. تثبيت أداة ffmpeg (إلزامية لمعالجة واستخراج الصوت) مع تنظيف الكاش فوراً لتقليل الحجم
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 3. تحديد مجلد العمل داخل الحاوية
WORKDIR /app

# 4. نسخ ملف المكتبات وتثبيتها بدون كاش لتوفير المساحة
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. نسخ كافة ملفات المشروع إلى الحاوية
COPY . .

# 6. أمر التشغيل الذكي: يقوم بتشغيل uvicorn مباشرة ويجبره على قراءة متغير الـ PORT من Render
# هذا السطر يحميك تماماً حتى لو كان ملف main.py القديم لا يقرأ المنفذ ديناميكياً
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]