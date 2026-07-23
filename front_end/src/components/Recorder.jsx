/**
 * مكوّن تسجيل الشاشة — قلب مشروع سوى
 * يدعم: تسجيل الشاشة، الكاميرا، رفع ملفات، استيراد من Google Drive
 */
import { useState, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { videosAPI } from "../api/client";

const LANGUAGES = [
  { value: "ar",    label: "العربية" },
  { value: "en",    label: "English" },
  { value: "es",    label: "Español" },
  { value: "fr",    label: "Français" },
  { value: "de",    label: "Deutsch" },
  { value: "ru",    label: "Русский" },
  { value: "zh",    label: "中文" },
  { value: "ja",    label: "日本語" },
  { value: "ko",    label: "한국어" },
  { value: "pt",    label: "Português" },
  { value: "it",    label: "Italiano" },
  { value: "tr",    label: "Türkçe" },
  { value: "hi",    label: "हिन्दी" },
  { value: "ar-EG", label: "العربية (مصر)" },
  { value: "ar-AE", label: "العربية (خليجي)" },
  { value: "ar-SY", label: "العربية (شامي)" },
  { value: "ar-MA", label: "العربية (مغاربي)" },
  { value: "ar-LY", label: "العربية (ليبي)" },
];

const ALLOWED_EXTENSIONS = ["mp4", "webm", "mov", "mp3", "wav", "m4a", "avi", "mkv", "ogg", "flac"];
const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

export default function Recorder({ onUploadDone }) {
  const { t } = useTranslation();
  const [state, setState]       = useState("idle");
  const [duration, setDuration] = useState(0);
  const [progress, setProgress] = useState(0);
  const [title, setTitle]       = useState("");
  const [dialect, setDialect]   = useState("ar");
  const [mode, setMode]         = useState(isMobile ? "camera" : "screen");
  const [error, setError]       = useState("");
  const [videoId, setVideoId]   = useState(null);
  const [noiseReduction, setNoiseReduction] = useState(false);

  const mediaRecorderRef = useRef(null);
  const chunksRef        = useRef([]);
  const streamRef        = useRef(null);
  const timerRef         = useRef(null);
  const previewRef       = useRef(null);
  const fileInputRef     = useRef(null);

  const uploadFile = useCallback(async (file, uploadMode) => {
    setState("uploading");
    setProgress(0);
    setError("");
    try {
      const video = await videosAPI.upload(
        file,
        title || file.name || `تسجيل ${new Date().toLocaleDateString("ar")}`,
        dialect,
        uploadMode,
        (pct) => setProgress(pct),
        noiseReduction,
      );
      setVideoId(video.id);
      setState("done");
      if (onUploadDone) onUploadDone(video);
    } catch (err) {
      setError(`فشل الرفع: ${err.message}`);
      setState("idle");
    }
  }, [title, dialect, noiseReduction, onUploadDone]);

  const handleFileSelect = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`نوع الملف غير مدعوم (${ext}). الأنواع المقبولة: ${ALLOWED_EXTENSIONS.join(", ")}`);
      return;
    }
    uploadFile(file, "file");
  }, [uploadFile]);

  const handleGoogleDriveImport = useCallback(async () => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
    const apiKey = import.meta.env.VITE_GOOGLE_API_KEY;
    if (!clientId || !apiKey) {
      setError("استيراد Google Drive غير مُعد — يرجى إعداد VITE_GOOGLE_CLIENT_ID و VITE_GOOGLE_API_KEY");
      return;
    }

    try {
      const token = await new Promise((resolve, reject) => {
        const origin = window.location.origin;
        const scope = "https://www.googleapis.com/auth/drive.readonly";

        const head = document.createElement("script");
        head.src = "https://accounts.google.com/gsi/client";
        head.onload = () => {
          const client = google.accounts.oauth2.initTokenClient({
            client_id: clientId,
            scope,
            callback: (resp) => {
              if (resp.error) reject(new Error(resp.error));
              else resolve(resp.access_token);
            },
          });
          client.requestAccessToken();
        };
        head.onerror = () => reject(new Error("فشل تحميل Google Identity Services"));
        document.head.appendChild(head);
      });

      const pickerToken = await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://apis.google.com/js/api.js";
        script.onload = () => {
          gapi.load("picker", () => resolve());
        };
        script.onerror = () => reject(new Error("فشل تحميل Google Picker API"));
        document.head.appendChild(script);
      });

      const file = await new Promise((resolve, reject) => {
        const docsView = new google.picker.DocsView(google.picker.ViewId.VIDEOS)
          .setSelectFolderEnabled(false)
          .setMimeTypes("video/*,audio/*");

        const picker = new google.picker.PickerBuilder()
          .setTitle("اختر فيديو من Google Drive")
          .addView(docsView)
          .setOAuthToken(token)
          .setDeveloperKey(apiKey)
          .setCallback((data) => {
            if (data.action === google.picker.Action.PICKED) {
              const picked = data.docs[0];
              if (!picked) { reject(new Error("لم يتم اختيار ملف")); return; }
              resolve(picked);
            } else if (data.action === google.picker.Action.CANCEL) {
              reject(new Error("تم الإلغاء"));
            }
          })
          .build();
        picker.setVisible(true);
      });

      setState("uploading");
      setProgress(0);
      setError("");
      setProgress(10);

      const response = await fetch(
        `https://www.googleapis.com/drive/v3/files/${file.id}?alt=media`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) throw new Error("فشل تحميل الملف من Google Drive");

      const contentLength = parseInt(response.headers.get("content-length") || "0");
      const reader = response.body.getReader();
      const chunks = [];
      let received = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        received += value.length;
        if (contentLength > 0) {
          setProgress(Math.round((received / contentLength) * 90) + 10);
        }
      }

      const blob = new Blob(chunks, { type: file.mimeType || "video/mp4" });
      const ext = file.name?.split(".").pop() || "mp4";
      const localFile = new File([blob], `${file.name || "drive-video"}.${ext}`, {
        type: file.mimeType || "video/mp4",
      });

      await uploadFile(localFile, "screen");
    } catch (err) {
      if (err.message === "تم الإلغاء") return;
      setError(`فشل الاستيراد: ${err.message}`);
      setState("idle");
    }
  }, [uploadFile]);

  const startRecording = useCallback(async () => {
    setError("");
    try {
      let combinedStream;

      if (mode === "camera" || isMobile) {
        const camStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: true,
        });
        combinedStream = camStream;
      } else {
        const screenStream = await navigator.mediaDevices.getDisplayMedia({
          video: { frameRate: 30, cursor: "always" },
          audio: true,
        });

        let micStream = null;
        try {
          micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch {
          console.warn("الميكروفون غير متاح — سيُسجَّل الصوت من الشاشة فقط");
        }

        if (micStream) {
          const ctx  = new AudioContext();
          const dest = ctx.createMediaStreamDestination();
          const screenAudioTracks = screenStream.getAudioTracks();

          if (screenAudioTracks.length > 0) {
            const scr = ctx.createMediaStreamSource(screenStream);
            scr.connect(dest);
          }

          const mic = ctx.createMediaStreamSource(micStream);
          mic.connect(dest);

          const audioTracks = dest.stream.getAudioTracks().length > 0
            ? dest.stream.getAudioTracks()
            : micStream.getAudioTracks();

          combinedStream = new MediaStream([
            ...screenStream.getVideoTracks(),
            ...audioTracks,
          ]);
        } else {
          combinedStream = screenStream;
        }

        combinedStream.getVideoTracks()[0].onended = () => stopRecording();
      }

      streamRef.current = combinedStream;

      if (previewRef.current) {
        previewRef.current.srcObject = combinedStream;
        previewRef.current.play().catch(() => {});
      }

      const recorder = new MediaRecorder(combinedStream, {
        mimeType: MediaRecorder.isTypeSupported("video/webm;codecs=vp9")
          ? "video/webm;codecs=vp9"
          : "video/webm",
      });

      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => handleRecordingStop();
      recorder.start(1000);

      mediaRecorderRef.current = recorder;
      setState("recording");

      timerRef.current = setInterval(() => {
        setDuration((d) => d + 1);
      }, 1000);

    } catch (err) {
      if (err.name === "NotAllowedError") {
        setError("رُفض الإذن. يرجى السماح والمحاولة مجدداً.");
      } else {
        setError(`خطأ: ${err.message}`);
      }
    }
  }, [mode]);

  const togglePause = () => {
    const rec = mediaRecorderRef.current;
    if (!rec) return;
    if (state === "recording") {
      rec.pause();
      clearInterval(timerRef.current);
      setState("paused");
    } else {
      rec.resume();
      timerRef.current = setInterval(() => setDuration((d) => d + 1), 1000);
      setState("recording");
    }
  };

  const stopRecording = () => {
    clearInterval(timerRef.current);
    mediaRecorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    if (previewRef.current) previewRef.current.srcObject = null;
  };

  const handleRecordingStop = async () => {
    setState("uploading");
    setProgress(0);

    const blob = new Blob(chunksRef.current, { type: "video/webm" });
    const file = new File([blob], `${title || "تسجيل"}-${Date.now()}.webm`, {
      type: "video/webm",
    });

    try {
      const video = await videosAPI.upload(
        file,
        title || `تسجيل ${new Date().toLocaleDateString("ar")}`,
        dialect,
        mode,
        (pct) => setProgress(pct),
        noiseReduction,
      );
      setVideoId(video.id);
      setState("done");
      if (onUploadDone) onUploadDone(video);
    } catch (err) {
      setError(`فشل الرفع: ${err.message}`);
      setState("idle");
    }
  };

  const formatTime = (s) => {
    const m = Math.floor(s / 60).toString().padStart(2, "0");
    const sec = (s % 60).toString().padStart(2, "0");
    return `${m}:${sec}`;
  };

  const tabStyle = (active) => ({
    flex: 1,
    padding: "8px",
    borderRadius: 8,
    border: "none",
    fontFamily: "var(--font)",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    background: active ? "var(--bg-card)" : "transparent",
    color: active ? "var(--text)" : "var(--text-muted)",
    transition: "all 0.2s",
  });

  const actionBtnStyle = {
    flex: 1,
    padding: "10px 16px",
    borderRadius: 10,
    border: "1px solid var(--border)",
    background: "var(--bg-card)",
    color: "var(--text)",
    fontFamily: "var(--font)",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    transition: "all 0.2s",
  };

  const checkboxRow = {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "10px 14px",
    background: "var(--bg)",
    borderRadius: 10,
    marginBottom: 16,
    cursor: "pointer",
  };

  return (
    <div style={{ maxWidth: 600, margin: "0 auto" }}>

      {(state === "recording" || state === "paused") && (
        <div style={{ position: "relative", marginBottom: 16, borderRadius: 14, overflow: "hidden", background: "#000", border: "2px solid #34D399" }}>
          <video
            ref={previewRef}
            muted
            autoPlay
            playsInline
            style={{ width: "100%", maxHeight: 300, display: "block", objectFit: "cover" }}
          />
          <div style={{ position: "absolute", top: 12, right: 12, display: "flex", gap: 8, alignItems: "center", background: "#000000aa", borderRadius: 20, padding: "4px 12px" }}>
            <div style={{
              width: 10, height: 10, borderRadius: "50%",
              background: state === "recording" ? "#F87171" : "#FCD34D",
              animation: state === "recording" ? "pulse-ring 1s infinite" : "none",
            }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>
              {state === "recording" ? "يُسجَّل" : "متوقف مؤقتاً"} — {formatTime(duration)}
            </span>
          </div>
        </div>
      )}

      {state === "idle" && (
        <div className="card fade-in" style={{ marginBottom: 16 }}>
          {isMobile && (
            <div style={{ padding: "12px 16px", background: "#818CF815", border: "1px solid #818CF833", borderRadius: 10, fontSize: 13, color: "#818CF8", marginBottom: 16, textAlign: "center" }}>
              تسجيل الشاشة متاح على الكمبيوتر فقط. يمكنك تسجيل الكاميرا والميكروفون هنا.
            </div>
          )}

          {!isMobile && (
            <div style={{ display: "flex", background: "var(--bg)", borderRadius: 10, padding: 4, marginBottom: 16 }}>
              {[["screen", "تسجيل الشاشة"], ["camera", "الكاميرا"], ["file", "من الملفات"]].map(([m, label]) => (
                <button key={m} onClick={() => setMode(m)} style={tabStyle(mode === m)}>
                  {label}
                </button>
              ))}
            </div>
          )}

          {mode === "file" && !isMobile && (
            <div style={{ textAlign: "center", marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
                اختر فيديو أو ملف صوتي من جهازك
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="video/*,audio/*"
                style={{ display: "none" }}
                onChange={handleFileSelect}
              />
              <button
                className="btn btn-outline"
                onClick={() => fileInputRef.current?.click()}
                style={{ width: "100%", justifyContent: "center" }}
              >
                <span style={{ fontSize: 16 }}>📂</span>
                اختر ملفاً
              </button>
            </div>
          )}

          {mode !== "file" && (
            <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16, textAlign: "center" }}>
              {mode === "camera" || isMobile
                ? "سيُسجَّل الصوت والفيديو من الكاميرا والميكروفون"
                : "سيُسجَّل الصوت من الميكروفون والشاشة معاً"}
            </div>
          )}

          {mode !== "file" && (
            <div style={{ marginBottom: 12 }}>
              <label>عنوان التسجيل</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="مثال: شرح المشروع لفريق العمل"
              />
            </div>
          )}

          {mode === "file" && (
            <div style={{ marginBottom: 12 }}>
              <label>عنوان التسجيل</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="اتركه فارغاً ليتم استخدام اسم الملف"
              />
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <label>{t("recorder.dialect")}</label>
            <select
              value={dialect}
              onChange={(e) => setDialect(e.target.value)}
              style={{ width: "100%", padding: "10px 14px", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)", fontFamily: "var(--font)", fontSize: 14, cursor: "pointer", direction: "rtl" }}
            >
              {LANGUAGES.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>

          <label
            style={checkboxRow}
            onClick={() => setNoiseReduction(!noiseReduction)}
          >
            <input
              type="checkbox"
              checked={noiseReduction}
              onChange={() => {}}
              style={{ width: "auto", accentColor: "var(--green)" }}
            />
            <span style={{ fontSize: 13, color: "var(--text)", flex: 1 }}>
              تقليل الضوضاء وال Background Noise
            </span>
            <span style={{ fontSize: 11, color: "var(--purple)" }}>
              AI
            </span>
          </label>

          <div style={{ display: "flex", gap: 10 }}>
            {mode === "file" ? (
              <>
                <button
                  className="btn btn-outline"
                  onClick={() => fileInputRef.current?.click()}
                  style={{ flex: 1, justifyContent: "center" }}
                >
                  <span>📂</span> اختر ملفاً
                </button>
                <button
                  className="btn btn-outline"
                  onClick={handleGoogleDriveImport}
                  style={{ flex: 1, justifyContent: "center", borderColor: "#818CF833", color: "#818CF8" }}
                >
                  <span>☁️</span> Google Drive
                </button>
              </>
            ) : (
              <button className="btn btn-primary btn-lg" onClick={startRecording} style={{ width: "100%", justifyContent: "center" }}>
                <span style={{ fontSize: 18 }}>{mode === "camera" || isMobile ? "📹" : "⏺"}</span>
                ابدأ التسجيل
              </button>
            )}
          </div>
        </div>
      )}

      {(state === "recording" || state === "paused") && (
        <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
          <button className="btn btn-outline" onClick={togglePause}>
            {state === "recording" ? "توقف مؤقت" : "استأنف"}
          </button>
          <button className="btn btn-danger" onClick={stopRecording}>
            أنهِ وارفع
          </button>
        </div>
      )}

      {state === "uploading" && (
        <div className="card fade-in" style={{ textAlign: "center", marginTop: 16 }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>☁️</div>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>
            {noiseReduction ? "جاري الرفع وتنظيف الصوت..." : "جاري الرفع وبدء التفريغ..."}
          </div>
          <div style={{ background: "var(--border)", borderRadius: 4, height: 8, overflow: "hidden" }}>
            <div style={{ width: `${progress}%`, height: "100%", background: "linear-gradient(90deg, #34D39966, #34D399)", borderRadius: 4, transition: "width 0.3s" }} />
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>{progress}%</div>
          {noiseReduction && (
            <div style={{ fontSize: 12, color: "var(--purple)", marginTop: 8 }}>
              🔇 جاري تطبيق فلتر تقليل الضوضاء
            </div>
          )}
        </div>
      )}

      {state === "done" && (
        <div className="card fade-in" style={{ textAlign: "center", marginTop: 16, border: "1px solid #34D39944" }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>✅</div>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>تم الرفع بنجاح!</div>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
            {noiseReduction
              ? "جاري تنظيف الصوت ثم بدء التفريغ..."
              : "التفريغ العربي يعمل في الخلفية، سيظهر خلال دقيقة."}
          </div>
          <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
            <a href={`/watch/${videoId}`} className="btn btn-primary">مشاهدة التسجيل</a>
            <button className="btn btn-outline" onClick={() => { setState("idle"); setDuration(0); setTitle(""); setNoiseReduction(false); }}>
              تسجيل جديد
            </button>
          </div>
        </div>
      )}

      {error && (
        <div style={{ marginTop: 12, padding: "12px 16px", background: "#F8717115", border: "1px solid #F8717133", borderRadius: 10, fontSize: 13, color: "#F87171" }}>
          {error}
        </div>
      )}
    </div>
  );
}
