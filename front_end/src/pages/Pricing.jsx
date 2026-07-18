/**
 * صفحة الأسعار والاشتراكات
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const PLANS = [
  {
    id:"free", name:"مجاني", price:0, color:"#555",
    features:["25 تسجيل","5 دقائق للمقطع","تفريغ أساسي","رابط مشاركة"],
    cta:"حسابك الحالي", disabled:true,
  },
  {
    id:"pro", name:"Pro", price:7, color:"#34D399",
    features:["غير محدود","ساعة كاملة للمقطع","ترجمة + تلخيص AI","تصدير DOCX + SRT","بدون علامة مائية"],
    cta:"اشترك الآن", disabled:false, popular:true,
  },
  {
    id:"team", name:"Team", price:20, color:"#818CF8",
    features:["كل مزايا Pro","5 أعضاء","Workspace مشترك","API للمطورين","دعم أولوية"],
    cta:"اشترك الآن", disabled:false,
  },
];

export default function Pricing() {
  const [loading, setLoading] = useState(null);
  const [error,   setError]   = useState("");
  const { user }              = useAuth();
  const navigate              = useNavigate();

  const handleSubscribe = async (planId) => {
    if (!user) { navigate("/auth"); return; }
    setLoading(planId);
    setError("");

    try {
      const token = localStorage.getItem("sawa_token");
      const res = await fetch("/api/payments/create", {
        method: "POST",
        headers: { "Content-Type":"application/json", "Authorization":`Bearer ${token}` },
        body: JSON.stringify({ plan: planId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "فشل إنشاء رابط الدفع");

      if (data.mode === "development") {
        // وضع التطوير — فعّل تجريبياً
        const demoRes = await fetch(`/api/payments/demo-activate/${planId}`, {
          method: "POST",
          headers: { "Authorization": `Bearer ${token}` },
        });
        if (demoRes.ok) {
          alert(`✅ تم تفعيل خطة ${planId} تجريبياً!\nفي الإنتاج سيتم التوجيه لبوابة الدفع.`);
          navigate("/dashboard");
        }
      } else {
        // وجّه المستخدم لبوابة الدفع
        window.location.href = data.payment_url;
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div style={{ maxWidth:900, margin:"0 auto", padding:"40px 20px" }}>
      <div style={{ textAlign:"center", marginBottom:48 }}>
        <h1 style={{ fontSize:28, fontWeight:900, marginBottom:8 }}>اختر خطتك</h1>
        <p style={{ color:"var(--text-muted)" }}>
          ادفع بالفيزا أو الماستركارد — تصلك القيمة USDT
        </p>
        <div style={{ display:"inline-flex", gap:8, background:"var(--bg-card)", border:"1px solid var(--border)", borderRadius:12, padding:8, marginTop:16 }}>
          {["Visa","Mastercard","USDT","BTC"].map(m => (
            <span key={m} style={{ fontSize:12, color:"var(--text-muted)", background:"var(--bg)", borderRadius:6, padding:"4px 10px" }}>{m}</span>
          ))}
        </div>
      </div>

      {/* بطاقات الخطط */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(240px,1fr))", gap:16, marginBottom:24 }}>
        {PLANS.map(p => (
          <div key={p.id} style={{
            background:"var(--bg-card)",
            border:`2px solid ${p.popular ? p.color+"66" : "var(--border)"}`,
            borderRadius:16, padding:24, position:"relative",
          }}>
            {p.popular && (
              <div style={{ position:"absolute", top:-12, right:20, background:p.color, color:"#000", borderRadius:20, padding:"3px 14px", fontSize:11, fontWeight:800 }}>
                الأكثر شعبية
              </div>
            )}
            <div style={{ fontSize:16, fontWeight:700, color:p.color, marginBottom:8 }}>{p.name}</div>
            <div style={{ marginBottom:20 }}>
              <span style={{ fontSize:34, fontWeight:900 }}>${p.price}</span>
              {p.price > 0 && <span style={{ fontSize:13, color:"var(--text-muted)" }}>/شهر</span>}
            </div>
            {p.features.map(f => (
              <div key={f} style={{ display:"flex", gap:8, marginBottom:8 }}>
                <span style={{ color:p.color }}>✓</span>
                <span style={{ fontSize:13 }}>{f}</span>
              </div>
            ))}
            <button
              disabled={p.disabled || loading === p.id || user?.plan === p.id}
              onClick={() => handleSubscribe(p.id)}
              style={{
                width:"100%", marginTop:20, padding:"11px",
                background: user?.plan === p.id ? "#34D39930" : p.disabled ? "#1a1a2e" : p.color,
                color: user?.plan === p.id ? "#34D399" : p.disabled ? "#555" : "#000",
                border:`1px solid ${user?.plan === p.id ? "#34D39966" : "transparent"}`,
                borderRadius:10, fontWeight:700, cursor:p.disabled?"default":"pointer",
                fontFamily:"inherit", fontSize:14, transition:"all 0.2s",
              }}
            >
              {loading === p.id ? "⏳ جاري..." :
               user?.plan === p.id ? "✅ خطتك الحالية" : p.cta}
            </button>
          </div>
        ))}
      </div>

      {error && (
        <div style={{ padding:"12px 16px", background:"#F8717115", border:"1px solid #F8717133", borderRadius:10, color:"var(--red)", fontSize:13, textAlign:"center" }}>
          {error}
        </div>
      )}

      {/* معلومات الدفع */}
      <div style={{ background:"var(--bg-card)", border:"1px solid var(--border)", borderRadius:14, padding:20, marginTop:16 }}>
        <div style={{ fontSize:13, color:"var(--text-muted)", marginBottom:12, fontWeight:700 }}>كيف يعمل الدفع؟</div>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:12 }}>
          {[
            { step:"1", text:"تختار الخطة وتدفع بالفيزا" },
            { step:"2", text:"بوابة Cryptomus تحوّل تلقائياً لـ USDT" },
            { step:"3", text:"يُفعَّل اشتراكك فوراً لمدة 30 يوم" },
          ].map(s => (
            <div key={s.step} style={{ textAlign:"center" }}>
              <div style={{ width:32, height:32, borderRadius:"50%", background:"#34D39920", border:"1px solid #34D39944", margin:"0 auto 8px", display:"flex", alignItems:"center", justifyContent:"center", fontSize:14, fontWeight:800, color:"#34D399" }}>{s.step}</div>
              <div style={{ fontSize:12, color:"var(--text-muted)", lineHeight:1.5 }}>{s.text}</div>
            </div>
          ))}
        </div>
        <div style={{ marginTop:14, padding:"10px 14px", background:"#FCD34D10", border:"1px solid #FCD34D22", borderRadius:8, fontSize:12, color:"#FCD34D" }}>
          ⚠️ رسوم التحويل 3-5% — بدون أي متطلبات بنكية في ليبيا
        </div>
      </div>
    </div>
  );
}
