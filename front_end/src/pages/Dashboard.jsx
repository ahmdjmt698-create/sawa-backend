import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { videosAPI } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import Analytics from "../components/Analytics";

export default function Dashboard() {
  const { t } = useTranslation();
  const [videos,       setVideos]       = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [deleting,     setDeleting]     = useState(null);
  const [copied,       setCopied]       = useState(null);
  const [analyticsId,  setAnalyticsId]  = useState(null);

  const { user } = useAuth();
  const navigate  = useNavigate();

  const STATUS_MAP = {
    pending:    { label: t("dashboard.status_pending"), color: "#FCD34D", dot: "⏳" },
    processing: { label: t("dashboard.status_processing"), color: "#818CF8", dot: "⚙️" },
    done:       { label: t("dashboard.status_done"), color: "#34D399", dot: "✅" },
    failed:     { label: t("dashboard.status_failed"), color: "#F87171", dot: "❌" },
  };

  function formatSize(bytes) {
    if (!bytes) return "";
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDur(sec) {
    if (!sec) return "";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  }

  useEffect(() => {
    videosAPI.getMyVideos()
      .then(setVideos)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id) => {
    if (!confirm(t("dashboard.confirm_delete"))) return;
    setDeleting(id);
    try {
      await videosAPI.deleteVideo(id);
      setVideos((v) => v.filter((x) => x.id !== id));
    } catch (e) {
      alert(t("dashboard.delete_failed") + e.message);
    } finally {
      setDeleting(null);
    }
  };

  const copyShare = (video) => {
    const url = `${window.location.origin}/share/${video.share_token}`;
    navigator.clipboard.writeText(url);
    setCopied(video.id);
    setTimeout(() => setCopied(null), 2000);
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: "80px 20px" }}>
        <div className="spin" style={{ width: 36, height: 36, border: "3px solid var(--border)", borderTopColor: "var(--green)", borderRadius: "50%", margin: "0 auto 16px" }} />
        <div style={{ color: "var(--text-muted)" }}>{t("dashboard.loading")}</div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "30px 20px" }}>
      {/* رأس الصفحة */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>{t("dashboard.title")}</h1>
          <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
            {videos.length} {t("dashboard.recording")} · {t("dashboard.plan_label")} <span style={{ color: "var(--green)", fontWeight: 700 }}>{user?.plan === "free" ? t("dashboard.plan_free") : "Pro"}</span>
            {user?.plan === "free" && ` (${videos.length}/25)`}
          </p>
        </div>
        <Link to="/record" className="btn btn-primary">
          <span>⏺</span> {t("dashboard.new_recording")}
        </Link>
      </div>

      {/* فارغة */}
      {videos.length === 0 && (
        <div style={{ textAlign: "center", padding: "80px 20px", background: "var(--bg-card)", border: "1px dashed var(--border)", borderRadius: 16 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🎙️</div>
          <h3 style={{ fontSize: 18, marginBottom: 8 }}>{t("dashboard.empty")}</h3>
          <p style={{ color: "var(--text-muted)", marginBottom: 20 }}>{t("dashboard.empty_desc")}</p>
          <Link to="/record" className="btn btn-primary btn-lg">{t("dashboard.start_first")}</Link>
        </div>
      )}

      {/* قائمة التسجيلات */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {videos.map((v) => {
          const ts = STATUS_MAP[v.transcript_status] || STATUS_MAP.pending;
          return (
            <div key={v.id} className="card fade-in"
              style={{ display: "flex", gap: 14, alignItems: "center", cursor: "pointer", transition: "border-color 0.2s" }}
              onMouseEnter={(e) => e.currentTarget.style.borderColor = "#34D39933"}
              onMouseLeave={(e) => e.currentTarget.style.borderColor = "var(--border)"}
              onClick={() => navigate(`/watch/${v.id}`)}
            >
              {/* ثامبنيل */}
              <div style={{ width: 80, height: 50, borderRadius: 8, background: "linear-gradient(135deg, #34D39920, #818CF820)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 20 }}>
                {v.hls_ready ? "🎬" : "🖥️"}
              </div>

              {/* معلومات */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {v.title}
                </div>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    {new Date(v.created_at).toLocaleDateString("ar")}
                  </span>
                  {v.duration && <span style={{ fontSize: 11, color: "var(--text-muted)" }}>⏱ {formatDur(v.duration)}</span>}
                  {v.file_size && <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{formatSize(v.file_size)}</span>}
                  <span style={{ fontSize: 11, background: ts.color + "20", color: ts.color, borderRadius: 6, padding: "1px 7px", fontWeight: 600 }}>
                    {ts.dot} {ts.label}
                  </span>
                  {v.hls_ready && (
                    <span style={{ fontSize: 11, background: "#60A5FA20", color: "#60A5FA", borderRadius: 6, padding: "1px 7px", fontWeight: 600 }}>
                      🎬 HLS
                    </span>
                  )}
                </div>
              </div>

              {/* أزرار */}
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
                {/* زر التحليلات */}
                <button
                  className="btn btn-outline"
                  style={{ padding: "5px 10px", fontSize: 11 }}
                  onClick={() => setAnalyticsId(v.id)}
                  title={t("dashboard.analytics_title")}
                >
                  📊
                </button>
                <button
                  className="btn btn-outline"
                  style={{ padding: "5px 10px", fontSize: 11 }}
                  onClick={() => copyShare(v)}
                  title={t("dashboard.copy_link_title")}
                >
                  {copied === v.id ? "✅" : "🔗"}
                </button>
                <button
                  className="btn btn-danger"
                  style={{ padding: "5px 10px", fontSize: 11 }}
                  onClick={() => handleDelete(v.id)}
                  disabled={deleting === v.id}
                >
                  {deleting === v.id ? "..." : "🗑"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* مودال التحليلات */}
      {analyticsId && (
        <Analytics videoId={analyticsId} onClose={() => setAnalyticsId(null)} />
      )}
    </div>
  );
}
