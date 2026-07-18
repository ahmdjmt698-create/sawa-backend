import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { authAPI } from "../api/client";
import PasswordInput from "../components/PasswordInput";

const PASSWORD_MIN_CHARS = 8;

const ERROR_MESSAGES = {
  "WRONG_PASSWORD": "كلمة المرور الحالية غير صحيحة",
  "SAME_PASSWORD": "كلمة المرور الجديدة مطابقة للقديمة",
  "VALIDATION_ERROR": "تحقق من صحة البيانات المُدخلة",
};

function getStrength(pwd) {
  let score = 0;
  if (pwd.length >= 8) score++;
  if (/[A-Z]/.test(pwd)) score++;
  if (/[0-9]/.test(pwd)) score++;
  if (/[^A-Za-z0-9]/.test(pwd)) score++;
  return score;
}
const STRENGTH_LABELS = ["ضعيفة جداً", "ضعيفة", "متوسطة", "قوية", "قوية جداً"];
const STRENGTH_COLORS = ["#F87171", "#F87171", "#FCD34D", "#34D399", "#34D399"];

export default function Settings() {
  const { user, logout, refresh } = useAuth();
  const navigate = useNavigate();

  // ── تغيير الاسم ──
  const [name, setName] = useState(user?.name || "");
  const [nameLoading, setNameLoading] = useState(false);
  const [nameMsg, setNameMsg] = useState({ type: "", text: "" });

  // ── تغيير كلمة المرور ──
  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [pwdLoading, setPwdLoading] = useState(false);
  const [pwdMsg, setPwdMsg] = useState({ type: "", text: "" });

  const handleNameSave = async () => {
    setNameLoading(true);
    setNameMsg({ type: "", text: "" });
    try {
      await authAPI.updateName(name.trim());
      await refresh();
      setNameMsg({ type: "success", text: "تم تحديث الاسم بنجاح" });
    } catch (err) {
      setNameMsg({ type: "error", text: err.message });
    } finally {
      setNameLoading(false);
    }
  };

  const handlePasswordChange = async () => {
    setPwdLoading(true);
    setPwdMsg({ type: "", text: "" });

    if (newPwd.length < PASSWORD_MIN_CHARS) {
      setPwdMsg({ type: "error", text: `كلمة المرور يجب أن تكون ${PASSWORD_MIN_CHARS} أحرف على الأقل` });
      setPwdLoading(false);
      return;
    }
    if (!/\d/.test(newPwd)) {
      setPwdMsg({ type: "error", text: "كلمة المرور يجب أن تحتوي على رقم واحد على الأقل" });
      setPwdLoading(false);
      return;
    }
    if (newPwd !== confirmPwd) {
      setPwdMsg({ type: "error", text: "كلمتا المرور غير متطابقتين" });
      setPwdLoading(false);
      return;
    }

    try {
      await authAPI.updatePassword(currentPwd, newPwd);
      setPwdMsg({ type: "success", text: "تم تغيير كلمة المرور بنجاح — يرجى تسجيل الدخول مجدداً" });
      setTimeout(async () => {
        await logout();
        navigate("/auth");
      }, 2000);
    } catch (err) {
      const code = err.error_code;
      setPwdMsg({ type: "error", text: code ? (ERROR_MESSAGES[code] || err.message) : err.message });
    } finally {
      setPwdLoading(false);
    }
  };

  const inputStyle = { marginBottom: 0 };

  return (
    <div style={{ minHeight: "80vh", padding: "40px 24px", maxWidth: 600, margin: "0 auto" }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, marginBottom: 4 }}>الإعدادات</h1>
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>إدارة معلومات حسابك</p>
      </div>

      {/* معلومات الحساب */}
      <div className="card fade-in" style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>معلومات الحساب</h2>

        <div style={{ marginBottom: 14 }}>
          <label>البريد الإلكتروني</label>
          <input type="email" value={user?.email || ""} disabled
            style={{ opacity: 0.5, cursor: "not-allowed" }} />
        </div>

        <div style={{ marginBottom: 14 }}>
          <label>الاسم</label>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="اسمك" style={inputStyle} />
        </div>

        {nameMsg.text && (
          <div style={{
            padding: "10px 14px", borderRadius: 8, fontSize: 13, marginBottom: 12,
            background: nameMsg.type === "success" ? "#34D39915" : "#F8717115",
            border: `1px solid ${nameMsg.type === "success" ? "#34D39933" : "#F8717133"}`,
            color: nameMsg.type === "success" ? "var(--green)" : "var(--red)",
          }}>{nameMsg.text}</div>
        )}

        <button className="btn btn-primary" onClick={handleNameSave} disabled={nameLoading}
          style={{ justifyContent: "center", width: "100%" }}>
          {nameLoading ? "جاري الحفظ..." : "حفظ التغييرات"}
        </button>
      </div>

      {/* تغيير كلمة المرور */}
      <div className="card fade-in" style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>تغيير كلمة المرور</h2>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <PasswordInput
            label="كلمة المرور الحالية"
            value={currentPwd}
            onChange={e => setCurrentPwd(e.target.value)}
            name="current_password"
          />

          <PasswordInput
            label="كلمة المرور الجديدة"
            value={newPwd}
            onChange={e => setNewPwd(e.target.value)}
            placeholder="8 أحرف على الأقل وتحتوي على رقم"
            name="new_password"
          />

          {newPwd.length > 0 && (() => {
            const s = getStrength(newPwd);
            return (
              <div>
                <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
                  {[0,1,2,3].map(i => (
                    <div key={i} style={{ flex: 1, height: 4, borderRadius: 2, background: i < s ? STRENGTH_COLORS[s] : "var(--border)", transition: "background 0.3s" }} />
                  ))}
                </div>
                <span style={{ fontSize: 11, color: STRENGTH_COLORS[s] }}>{STRENGTH_LABELS[s]}</span>
              </div>
            );
          })()}

          <PasswordInput
            label="تأكيد كلمة المرور الجديدة"
            value={confirmPwd}
            onChange={e => setConfirmPwd(e.target.value)}
            name="confirm_new_password"
          />

          {pwdMsg.text && (
            <div style={{
              padding: "10px 14px", borderRadius: 8, fontSize: 13,
              background: pwdMsg.type === "success" ? "#34D39915" : "#F8717115",
              border: `1px solid ${pwdMsg.type === "success" ? "#34D39933" : "#F8717133"}`,
              color: pwdMsg.type === "success" ? "var(--green)" : "var(--red)",
            }}>{pwdMsg.text}</div>
          )}

          <button className="btn btn-primary" onClick={handlePasswordChange} disabled={pwdLoading}
            style={{ justifyContent: "center" }}>
            {pwdLoading ? "جاري التغيير..." : "تغيير كلمة المرور"}
          </button>
        </div>
      </div>

      {/* رابط العودة */}
      <div style={{ textAlign: "center" }}>
        <Link to="/dashboard" style={{ color: "var(--text-muted)", fontSize: 13, textDecoration: "none" }}>
          ← العودة للوحة التحكم
        </Link>
      </div>
    </div>
  );
}
