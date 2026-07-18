import { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { authAPI } from "../api/client";
import PasswordInput from "../components/PasswordInput";

const PASSWORD_MIN_CHARS = 8;
const PASSWORD_MAX_BYTES = 72;

const passwordByteLen = (str) => new TextEncoder().encode(str).length;

const ERROR_MESSAGES = {
  "WRONG_PASSWORD":   "كلمة المرور غير صحيحة",
  "EMAIL_NOT_FOUND":  "لا يوجد حساب بهذا البريد",
  "EMAIL_EXISTS":     "البريد مسجل مسبقاً — سجّل الدخول بدلاً منه",
  "RATE_LIMITED":     "محاولات كثيرة، انتظر دقيقة واحدة",
  "TOKEN_EXPIRED":    "انتهت صلاحية جلستك — سجّل الدخول مجدداً",
  "VALIDATION_ERROR": "تحقق من صحة البيانات المُدخلة",
  "OTP_EXPIRED":      "انتهت صلاحية الرمز، اطلب رمزاً جديداً",
  "OTP_MAX_ATTEMPTS": "تجاوزت عدد المحاولات، اطلب رمزاً جديداً",
  "OTP_INVALID":      "الرمز غير صحيح",
  "SAME_PASSWORD":    "كلمة المرور الجديدة مطابقة للقديمة",
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

export default function Auth() {
  const [params]               = useSearchParams();
  const [mode, setMode]        = useState(params.get("mode") === "register" ? "register" : "login");
  const [name, setName]        = useState("");
  const [email, setEmail]      = useState("");
  const [password, setPassword]= useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [error, setError]      = useState("");
  const [fieldError, setFieldError] = useState("");
  const [loading, setLoading]  = useState(false);

  // نسيت كلمة المرور
  const [forgotMode, setForgotMode]       = useState(null); // null | "email" | "otp" | "reset"
  const [forgotEmail, setForgotEmail]     = useState("");
  const [otp, setOtp]                     = useState(["", "", "", "", "", ""]);
  const [resetToken, setResetToken]       = useState("");
  const [newPassword, setNewPassword]     = useState("");
  const [confirmNew, setConfirmNew]       = useState("");
  const [otpCountdown, setOtpCountdown]   = useState(0);
  const [forgotMessage, setForgotMessage] = useState("");

  const { login, register } = useAuth();
  const navigate            = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setFieldError("");
    setLoading(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        if (!name.trim()) { setError("يرجى إدخال اسمك"); setLoading(false); return; }
        if (password.length < PASSWORD_MIN_CHARS) {
          setError(`كلمة المرور يجب أن تكون ${PASSWORD_MIN_CHARS} أحرف على الأقل`);
          setLoading(false); return;
        }
        if (passwordByteLen(password) > PASSWORD_MAX_BYTES) {
          setError("كلمة المرور طويلة جداً — الحد الأقصى 72 بايت");
          setLoading(false); return;
        }
        if (password !== confirmPwd) {
          setError("كلمتا المرور غير متطابقتين");
          setLoading(false); return;
        }
        await register(name, email, password);
      }
      navigate("/dashboard");
    } catch (err) {
      const code = err.error_code;
      setError(code ? (ERROR_MESSAGES[code] || err.message) : err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── نسيت كلمة المرور: الخطوة 1 ──
  const handleForgotEmail = async () => {
    setForgotMessage("");
    setLoading(true);
    try {
      await authAPI.forgotPassword(forgotEmail);
      setForgotMode("otp");
      setOtpCountdown(60);
      const timer = setInterval(() => {
        setOtpCountdown(prev => {
          if (prev <= 1) { clearInterval(timer); return 0; }
          return prev - 1;
        });
      }, 1000);
    } catch (err) {
      setForgotMessage(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── نسيت كلمة المرور: الخطوة 2 (OTP) ──
  const handleOtpDigit = async (index, value) => {
    if (!/^\d*$/.test(value)) return;
    const newOtp = [...otp];
    newOtp[index] = value.slice(-1);
    setOtp(newOtp);

    if (value && index < 5) {
      document.getElementById(`otp-${index + 1}`)?.focus();
    }

    if (newOtp.every(d => d !== "") && newOtp.join("").length === 6) {
      setLoading(true);
      try {
        const data = await authAPI.verifyOtp(forgotEmail, newOtp.join(""));
        setResetToken(data.reset_token);
        setForgotMode("reset");
      } catch (err) {
        const code = err.error_code;
        setForgotMessage(code ? (ERROR_MESSAGES[code] || err.message) : err.message);
        if (code === "OTP_INVALID") setOtp(["", "", "", "", "", ""]);
      } finally {
        setLoading(false);
      }
    }
  };

  const handleOtpKeyDown = (index, e) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      document.getElementById(`otp-${index - 1}`)?.focus();
    }
  };

  // ── نسيت كلمة المرور: الخطوة 3 (كلمة مرور جديدة) ──
  const handleResetPassword = async () => {
    if (newPassword.length < 8) {
      setForgotMessage("كلمة المرور يجب أن تكون 8 أحرف على الأقل");
      return;
    }
    if (newPassword !== confirmNew) {
      setForgotMessage("كلمتا المرور غير متطابقتين");
      return;
    }
    setLoading(true);
    try {
      await authAPI.resetPassword(resetToken, newPassword);
      setForgotMode(null);
      setError("");
      setForgotMessage("");
      setEmail(forgotEmail);
      setPassword("");
      setMode("login");
      setForgotEmail("");
    } catch (err) {
      setForgotMessage(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ── نسيت كلمة المرور: إعادة الإرسال ──
  const handleResendOtp = async () => {
    if (otpCountdown > 0) return;
    setOtp(["", "", "", "", "", ""]);
    setForgotMessage("");
    await handleForgotEmail();
  };

  // ── عرض واجهة نسيت كلمة المرور ──
  if (forgotMode) {
    return (
      <div style={{ minHeight: "80vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
        <div style={{ width: "100%", maxWidth: 420 }}>
          <div style={{ textAlign: "center", marginBottom: 32 }}>
            <Link to="/" style={{ textDecoration: "none", fontSize: 28, fontWeight: 900, background: "linear-gradient(135deg, #34D399, #818CF8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>سوى</Link>
          </div>

          <div className="card fade-in">
            {forgotMode === "email" && (
              <>
                <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>نسيت كلمة المرور؟</h3>
                <p style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 20 }}>أدخل بريدك الإلكتروني وسنرسل لك رمزاً للتحقق</p>
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div>
                    <label>البريد الإلكتروني</label>
                    <input type="email" value={forgotEmail} onChange={e => setForgotEmail(e.target.value)} placeholder="example@email.com" />
                  </div>
                  {forgotMessage && <div style={{ padding: "10px 14px", background: "#F8717115", border: "1px solid #F8717133", borderRadius: 8, fontSize: 13, color: "var(--red)" }}>{forgotMessage}</div>}
                  <button className="btn btn-primary" onClick={handleForgotEmail} disabled={loading} style={{ justifyContent: "center" }}>
                    {loading ? "جاري الإرسال..." : "إرسال رمز التحقق"}
                  </button>
                  <button onClick={() => { setForgotMode(null); setForgotMessage(""); }} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 13, fontFamily: "var(--font)" }}>← العودة للدخول</button>
                </div>
              </>
            )}

            {forgotMode === "otp" && (
              <>
                <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>أدخل رمز التحقق</h3>
                <p style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 20 }}>أرسلنا 6 أرقام إلى {forgotEmail}</p>
                <div style={{ display: "flex", gap: 8, direction: "ltr", justifyContent: "center", marginBottom: 16 }}>
                  {otp.map((digit, i) => (
                    <input key={i} id={`otp-${i}`} maxLength={1} value={digit}
                      onChange={e => handleOtpDigit(i, e.target.value)}
                      onKeyDown={e => handleOtpKeyDown(i, e)}
                      style={{ width: 48, height: 56, textAlign: "center", fontSize: 24, borderRadius: 10, border: "2px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontFamily: "var(--font)", outline: "none", transition: "border-color 0.2s" }}
                      onFocus={e => e.target.style.borderColor = "var(--green)"}
                      onBlur={e => e.target.style.borderColor = "var(--border)"}
                    />
                  ))}
                </div>
                {forgotMessage && <div style={{ padding: "10px 14px", background: "#F8717115", border: "1px solid #F8717133", borderRadius: 8, fontSize: 13, color: "var(--red)", marginBottom: 12, textAlign: "center" }}>{forgotMessage}</div>}
                <div style={{ textAlign: "center" }}>
                  {otpCountdown > 0 ? (
                    <span style={{ color: "var(--text-muted)", fontSize: 13 }}>إعادة الإرسال بعد {otpCountdown} ثانية</span>
                  ) : (
                    <button onClick={handleResendOtp} style={{ background: "none", border: "none", color: "var(--green)", cursor: "pointer", fontSize: 13, fontFamily: "var(--font)", fontWeight: 600 }}>إعادة إرسال الرمز</button>
                  )}
                </div>
                <button onClick={() => { setForgotMode("email"); setForgotMessage(""); }} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 13, fontFamily: "var(--font)", marginTop: 12 }}>← العودة</button>
              </>
            )}

            {forgotMode === "reset" && (
              <>
                <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>كلمة مرور جديدة</h3>
                <p style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 20 }}>اختر كلمة مرور قوية</p>
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <PasswordInput label="كلمة المرور الجديدة" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="8 أحرف على الأقل" name="new_password" />
                  {newPassword.length > 0 && (() => {
                    const s = getStrength(newPassword);
                    return (
                      <div>
                        <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
                          {[0,1,2,3].map(i => (
                            <div key={i} style={{ flex: 1, height: 4, borderRadius: 2, background: i < s ? STRENGTH_COLORS[s] : "var(--border)" }} />
                          ))}
                        </div>
                        <span style={{ fontSize: 11, color: STRENGTH_COLORS[s] }}>{STRENGTH_LABELS[s]}</span>
                      </div>
                    );
                  })()}
                  <PasswordInput label="تأكيد كلمة المرور" value={confirmNew} onChange={e => setConfirmNew(e.target.value)} placeholder="أعد إدخال كلمة المرور" name="confirm_new_password" />
                  {forgotMessage && <div style={{ padding: "10px 14px", background: "#F8717115", border: "1px solid #F8717133", borderRadius: 8, fontSize: 13, color: "var(--red)" }}>{forgotMessage}</div>}
                  <button className="btn btn-primary" onClick={handleResetPassword} disabled={loading} style={{ justifyContent: "center" }}>
                    {loading ? "جاري التغيير..." : "تغيير كلمة المرور"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── واجهة الدخول / التسجيل الرئيسية ──
  return (
    <div style={{ minHeight: "80vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
      <div style={{ width: "100%", maxWidth: 420 }}>

        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <Link to="/" style={{ textDecoration: "none", fontSize: 28, fontWeight: 900, background: "linear-gradient(135deg, #34D399, #818CF8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            سوى
          </Link>
          <p style={{ color: "var(--text-muted)", fontSize: 14, marginTop: 8 }}>
            {mode === "login" ? "مرحباً بعودتك" : "انضم إلى سوى مجاناً"}
          </p>
        </div>

        <div className="card fade-in">
          <div style={{ display: "flex", background: "var(--bg)", borderRadius: 10, padding: 4, marginBottom: 24 }}>
            {[["login", "تسجيل الدخول"], ["register", "حساب جديد"]].map(([m, label]) => (
              <button key={m} onClick={() => { setMode(m); setError(""); setFieldError(""); }}
                style={{ flex: 1, padding: "8px", borderRadius: 8, border: "none", fontFamily: "var(--font)", fontSize: 13, fontWeight: 600, cursor: "pointer", background: mode === m ? "var(--bg-card)" : "transparent", color: mode === m ? "var(--text)" : "var(--text-muted)", transition: "all 0.2s" }}>
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {mode === "register" && (
              <div>
                <label>الاسم الكامل</label>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="أحمد محمد" required />
              </div>
            )}
            <div>
              <label>البريد الإلكتروني</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="example@email.com" required />
            </div>
          {mode === "register" && password.length > 0 && (() => {
            const bytes   = passwordByteLen(password);
            const tooLong = bytes > PASSWORD_MAX_BYTES;
            const nearMax = bytes >= PASSWORD_MAX_BYTES - 8;
            const color   = tooLong ? "var(--red)" : nearMax ? "#F59E0B" : "var(--text-muted)";
            return (
              <div style={{ display: "flex", justifyContent: "flex-end", fontSize: 11, color, marginTop: -8, marginBottom: 2 }}>
                {bytes}/{PASSWORD_MAX_BYTES} bytes
                {tooLong && <span style={{ marginRight: 6 }}>— تجاوز الحد الأقصى</span>}
              </div>
            );
          })()}
            <PasswordInput
              label="كلمة المرور"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={`${PASSWORD_MIN_CHARS} أحرف على الأقل`}
              name="password"
              minLength={PASSWORD_MIN_CHARS}
              required
            />

            {mode === "register" && (
              <PasswordInput
                label="تأكيد كلمة المرور"
                value={confirmPwd}
                onChange={(e) => setConfirmPwd(e.target.value)}
                placeholder="أعد إدخال كلمة المرور"
                name="confirm_password"
                required
              />
            )}

            {mode === "login" && (
              <div style={{ textAlign: "left", marginTop: -8 }}>
                <button type="button" onClick={() => { setForgotMode("email"); setForgotEmail(email); setOtp(["","","","","",""]); setForgotMessage(""); }}
                  style={{ background: "none", border: "none", color: "var(--green)", cursor: "pointer", fontSize: 12, fontFamily: "var(--font)" }}>
                  نسيت كلمة المرور؟
                </button>
              </div>
            )}

            {error && (
              <div style={{ padding: "10px 14px", background: "#F8717115", border: "1px solid #F8717133", borderRadius: 8, fontSize: 13, color: "var(--red)" }}>
                {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary" disabled={loading}
              style={{ justifyContent: "center", marginTop: 4, opacity: loading ? 0.7 : 1 }}>
              {loading ? (
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="spin" style={{ width: 16, height: 16, border: "2px solid #000", borderTopColor: "transparent", borderRadius: "50%", display: "inline-block" }} />
                  جاري...
                </span>
              ) : mode === "login" ? "دخول →" : "إنشاء الحساب →"}
            </button>
          </form>
        </div>

        {mode === "login" && (
          <p style={{ textAlign: "center", fontSize: 13, color: "var(--text-muted)", marginTop: 16 }}>
            ليس لديك حساب؟{" "}
            <button onClick={() => setMode("register")}
              style={{ background: "none", border: "none", color: "var(--green)", cursor: "pointer", fontFamily: "var(--font)", fontSize: 13, fontWeight: 600 }}>
              سجّل مجاناً
            </button>
          </p>
        )}
      </div>
    </div>
  );
}
