import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { authAPI } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [verified, setVerified] = useState(false);

  // مرجع لتتبع ما إذا كان قد حدث تسجيل دخول/خروج مؤخراً
  // لمنع سباق الحالة بين verifyToken و login/register
  const authGeneration = useRef(0);

  // التحقق من هوية المستخدم عند بدء التطبيق
  const verifyToken = useCallback(async () => {
    const gen = ++authGeneration.current;
    setLoading(true);
    try {
      const userData = await authAPI.me();
      // تجاهل النتيجة إذا كان قد حدث login/register أثناء الانتظار
      if (gen !== authGeneration.current) return;
      setUser(userData);
      setVerified(true);
    } catch {
      if (gen !== authGeneration.current) return;
      setUser(null);
      setVerified(false);
    } finally {
      if (gen !== authGeneration.current) return;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    verifyToken();
  }, [verifyToken]);

  const login = async (email, password) => {
    authGeneration.current++;  // يلغي أي verifyToken جارٍ
    const data = await authAPI.login(email, password);
    setUser(data.user);
    setVerified(true);
    setLoading(false);
    return data;
  };

  const register = async (name, email, password) => {
    authGeneration.current++;  // يلغي أي verifyToken جارٍ
    const data = await authAPI.register(name, email, password);
    setUser(data.user);
    setVerified(true);
    setLoading(false);
    return data;
  };

  const logout = async () => {
    authGeneration.current++;  // يلغي أي verifyToken جارٍ
    try { await authAPI.logout(); } catch { /* ignore */ }
    setUser(null);
    setVerified(false);
    setLoading(false);
  };

  return (
    <AuthContext.Provider value={{ user, loading, verified, login, register, logout, refresh: verifyToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
