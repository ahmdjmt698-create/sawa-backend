import { useState } from "react";
import { useTranslation } from "react-i18next";

export default function PasswordInput({
  value, onChange, placeholder,
  label, name = "password",
  minLength, required = false, style: extraStyle = {},
}) {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);
  const displayLabel = label !== undefined ? label : t("password_input.label");
  const displayPlaceholder = placeholder !== undefined ? placeholder : t("password_input.placeholder");

  return (
    <div style={{ position: "relative", ...extraStyle }}>
      {displayLabel && <label>{displayLabel}</label>}
      <input
        type={visible ? "text" : "password"}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={displayPlaceholder}
        autoComplete={name === "new_password" ? "new-password" : "current-password"}
        minLength={minLength}
        required={required}
        style={{ paddingLeft: 44 }}
      />
      <button
        type="button"
        onClick={() => setVisible(v => !v)}
        aria-label={visible ? t("password_input.hide") : t("password_input.show")}
        style={{
          position: "absolute",
          left: 12,
          top: label ? "calc(50% + 10px)" : "50%",
          transform: "translateY(-50%)",
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "var(--text-muted)",
          padding: 4,
          display: "flex",
          alignItems: "center",
          transition: "color 0.2s",
        }}
        onMouseEnter={e => e.currentTarget.style.color = "var(--green)"}
        onMouseLeave={e => e.currentTarget.style.color = "var(--text-muted)"}
      >
        {visible ? (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
            <line x1="1" y1="1" x2="23" y2="23"/>
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        )}
      </button>
    </div>
  );
}
