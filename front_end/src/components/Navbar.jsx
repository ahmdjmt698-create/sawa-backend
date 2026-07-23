import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../hooks/useAuth";

export default function Navbar() {
  const { user, logout } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate         = useNavigate();
  const location         = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const isActive = (path) => location.pathname === path;

  const toggleLanguage = () => {
    const next = i18n.language === "ar" ? "en" : "ar";
    i18n.changeLanguage(next);
  };

  return (
    <nav style={{
      position: "sticky", top: 0, zIndex: 100,
      height: 58,
      background: scrolled ? "rgba(6,6,14,0.85)" : "transparent",
      backdropFilter: scrolled ? "blur(20px)" : "none",
      WebkitBackdropFilter: scrolled ? "blur(20px)" : "none",
      borderBottom: scrolled ? "1px solid #1e1e3080" : "1px solid transparent",
      padding: "0 24px",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      transition: "all 0.3s ease",
    }}>

      {/* شعار */}
      <Link to="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{
          fontSize: 22, fontWeight: 900,
          background: "linear-gradient(135deg, #34D399, #818CF8)",
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
        }}>{t("app_name")}</div>
        <span style={{
          fontSize: 10, color: "#34D399", background: "#34D39915",
          border: "1px solid #34D39930", borderRadius: 6, padding: "1px 7px",
          fontWeight: 700, letterSpacing: 1,
        }}>BETA</span>
      </Link>

      {/* روابط وسط */}
      {user && (
        <div style={{ display: "flex", gap: 4 }}>
          {[
            { to: "/dashboard", label: t("nav.my_recordings") },
            { to: "/search",    label: t("nav.search") },
            { to: "/pricing",   label: t("nav.pricing") },
          ].map(l => (
            <Link key={l.to} to={l.to} style={{
              textDecoration: "none", padding: "6px 14px", borderRadius: 8,
              fontSize: 13, fontWeight: 500,
              color: isActive(l.to) ? "#34D399" : "#888",
              background: isActive(l.to) ? "#34D39912" : "transparent",
              transition: "all 0.2s",
            }}
              onMouseEnter={(e) => { if (!isActive(l.to)) { e.currentTarget.style.color = "#ccc"; e.currentTarget.style.background = "#ffffff08"; } }}
              onMouseLeave={(e) => { if (!isActive(l.to)) { e.currentTarget.style.color = "#888"; e.currentTarget.style.background = "transparent"; } }}
            >{l.label}</Link>
          ))}
        </div>
      )}

      {/* يمين */}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {/* زر تبديل اللغة */}
        <button onClick={toggleLanguage} style={{
          padding: "5px 10px", borderRadius: 8, fontSize: 12, fontWeight: 700,
          color: "#888", background: "transparent", border: "1px solid #1e1e30",
          cursor: "pointer", fontFamily: "inherit", transition: "all 0.2s",
        }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#818CF866"; e.currentTarget.style.color = "#ccc"; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#1e1e30"; e.currentTarget.style.color = "#888"; }}
        >
          {i18n.language === "ar" ? "EN" : "عربي"}
        </button>

        {user ? (
          <>
            <Link to="/record" style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              background: "#34D399", color: "#000", padding: "7px 16px",
              borderRadius: 10, fontWeight: 800, fontSize: 13, textDecoration: "none",
              boxShadow: "0 0 16px #34D39930", transition: "all 0.2s",
            }}
              onMouseEnter={(e) => e.currentTarget.style.boxShadow = "0 0 24px #34D39950"}
              onMouseLeave={(e) => e.currentTarget.style.boxShadow = "0 0 16px #34D39930"}
            >
              <span style={{ fontSize: 12 }}>⏺</span> {t("nav.record")}
            </Link>

            {/* أفاتار مع قائمة منسدلة */}
            <div ref={menuRef} style={{ position: "relative" }}>
              <div style={{
                display: "flex", alignItems: "center", gap: 8, padding: "5px 12px",
                background: "#0d0d1a", border: "1px solid #1e1e30", borderRadius: 10,
                cursor: "pointer", transition: "border-color 0.2s",
              }}
                onClick={() => setMenuOpen(!menuOpen)}
                onMouseEnter={(e) => e.currentTarget.style.borderColor = "#34D39966"}
                onMouseLeave={(e) => e.currentTarget.style.borderColor = "#1e1e30"}
              >
                <div style={{
                  width: 26, height: 26, borderRadius: "50%",
                  background: "linear-gradient(135deg, #34D399, #818CF8)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 12, fontWeight: 800, color: "#000",
                }}>
                  {user.name?.[0] || "?"}
                </div>
                <span style={{ fontSize: 13, color: "#ccc" }}>{user.name?.split(" ")[0]}</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth="2" style={{ transform: menuOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}>
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </div>

              {menuOpen && (
                <div style={{
                  position: "absolute", top: "calc(100% + 6px)", right: 0,
                  minWidth: 160, background: "#0d0d1a", border: "1px solid #1e1e30",
                  borderRadius: 10, padding: "6px", boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
                  animation: "fadeIn 0.15s ease",
                }}>
                  <Link to="/settings" onClick={() => setMenuOpen(false)} style={{
                    display: "block", padding: "8px 14px", borderRadius: 8,
                    fontSize: 13, color: "#ccc", textDecoration: "none",
                    transition: "background 0.15s",
                  }}
                    onMouseEnter={(e) => e.currentTarget.style.background = "#ffffff08"}
                    onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                  >{t("nav.settings")}</Link>
                  <button onClick={() => { setMenuOpen(false); logout().then?.(() => navigate("/")) || (logout(), navigate("/")); }} style={{
                    display: "block", width: "100%", padding: "8px 14px", borderRadius: 8,
                    fontSize: 13, color: "var(--red)", textAlign: "right",
                    background: "none", border: "none", cursor: "pointer", fontFamily: "var(--font)",
                    transition: "background 0.15s",
                  }}
                    onMouseEnter={(e) => e.currentTarget.style.background = "#F8717110"}
                    onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                  >{t("nav.logout")}</button>
                </div>
              )}
            </div>
          </>
        ) : (
          <>
            <Link to="/auth" style={{
              padding: "7px 16px", borderRadius: 10, fontSize: 13, fontWeight: 600,
              color: "#888", textDecoration: "none", background: "transparent",
              border: "1px solid #1e1e30", transition: "all 0.2s",
            }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#34D39966"; e.currentTarget.style.color = "#ccc"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#1e1e30"; e.currentTarget.style.color = "#888"; }}
            >{t("nav.login")}</Link>

            <Link to="/auth?mode=register" style={{
              padding: "7px 16px", borderRadius: 10, fontSize: 13, fontWeight: 800,
              color: "#000", textDecoration: "none", background: "#34D399",
              boxShadow: "0 0 16px #34D39930", transition: "all 0.2s",
            }}>{t("nav.register")}</Link>
          </>
        )}
      </div>
    </nav>
  );
}
