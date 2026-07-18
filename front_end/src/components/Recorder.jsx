/**
 * مكوّن تسجيل الشاشة — قلب مشروع سوى
 * يستخدم MediaRecorder API — يدعم الشاشة (سطح المكتب) والكاميرا (الجوال)
 */
import { useState, useRef, useCallback } from "react";
import { videosAPI } from "../api/client";

const DIALECTS = [
  { value: "ar",    label: "عربي فصحى" },
  { value: "ar-EG", label: "مصري" },
  { value: "ar-AE", label: "خليجي" },
  { value: "ar-SY", label: "شامي" },
  { value: "ar-MA", label: "مغاربي" },
  { value: "ar-LY", label: "ليبي" },
];

const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

export default function Recorder({ onUploadDone }) {
  const [state, setState]       = useState("idle");
  const [duration, setDuration] = useState(0);
  const [progress, setProgress] = useState(0);
  const [title, setTitle]       = useState("");
  const [dialect, setDialect]   = useState("ar");
  const [mode, setMode]         = useState(isMobile ? "camera" : "screen");
  const [error, setError]       = useState("");
  const [videoId, setVideoId]   = useState(null);

  const mediaRecorderRef = useRef(null);
  const chunksRef        = useRef([]);
  const streamRef        = useRef(null);
  const timerRef         = useRef(null);
  const previewRef       = useRef(null);

  const startRecording = useCallback(async () => {
    setError("");
    try {
      let combinedStream;

      if (mode === "camera" || isMobile) {
        // تسجيل الكاميرا + الميكروفون (الجوال)
        const camStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: true,
        });
        combinedStream = camStream;
      } else {
        // تسجيل الشاشة + الميكروفون (سطح المكتب)
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

        // إذا توقف المستخدم عن مشاركة الشاشة
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
              {[["screen", "تسجيل الشاشة"], ["camera", "الكاميرا"]].map(([m, label]) => (
                <button key={m} onClick={() => setMode(m)}
                  style={{ flex: 1, padding: "8px", borderRadius: 8, border: "none", fontFamily: "var(--font)", fontSize: 13, fontWeight: 600, cursor: "pointer", background: mode === m ? "var(--bg-card)" : "transparent", color: mode === m ? "var(--text)" : "var(--text-muted)", transition: "all 0.2s" }}>
                  {label}
                </button>
              ))}
            </div>
          )}

          <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16, textAlign: "center" }}>
            {mode === "camera" || isMobile
              ? "سيُسجَّل الصوت والفيديو من الكاميرا والميكروفون"
              : "سيُسجَّل الصوت من الميكروفون والشاشة معاً"}
          </div>

          <div style={{ marginBottom: 12 }}>
            <label>عنوان التسجيل</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="مثال: شرح المشروع لفريق العمل"
            />
          </div>

          <div>
            <label>اللهجة العربية</label>
            <select
              value={dialect}
              onChange={(e) => setDialect(e.target.value)}
              style={{ width: "100%", padding: "10px 14px", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)", fontFamily: "var(--font)", fontSize: 14, cursor: "pointer", direction: "rtl" }}
            >
              {DIALECTS.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
        {state === "idle" && (
          <button className="btn btn-primary btn-lg" onClick={startRecording} style={{ width: "100%", justifyContent: "center" }}>
            <span style={{ fontSize: 18 }}>{mode === "camera" || isMobile ? "📹" : "⏺"}</span>
            ابدأ التسجيل
          </button>
        )}

        {(state === "recording" || state === "paused") && (
          <>
            <button className="btn btn-outline" onClick={togglePause}>
              {state === "recording" ? "توقف مؤقت" : "استأنف"}
            </button>
            <button className="btn btn-danger" onClick={stopRecording}>
              أنهِ وارفع
            </button>
          </>
        )}
      </div>

      {state === "uploading" && (
        <div className="card fade-in" style={{ textAlign: "center", marginTop: 16 }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>☁️</div>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>جاري الرفع وبدء التفريغ...</div>
          <div style={{ background: "var(--border)", borderRadius: 4, height: 8, overflow: "hidden" }}>
            <div style={{ width: `${progress}%`, height: "100%", background: "linear-gradient(90deg, #34D39966, #34D399)", borderRadius: 4, transition: "width 0.3s" }} />
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>{progress}%</div>
        </div>
      )}

      {state === "done" && (
        <div className="card fade-in" style={{ textAlign: "center", marginTop: 16, border: "1px solid #34D39944" }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>✅</div>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>تم الرفع بنجاح!</div>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
            التفريغ العربي يعمل في الخلفية، سيظهر خلال دقيقة.
          </div>
          <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
            <a href={`/watch/${videoId}`} className="btn btn-primary">مشاهدة التسجيل</a>
            <button className="btn btn-outline" onClick={() => { setState("idle"); setDuration(0); setTitle(""); }}>
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
