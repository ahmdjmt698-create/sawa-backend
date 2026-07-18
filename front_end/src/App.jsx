import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import { RecordPage, WatchPage, SharePage } from "./pages/Pages";
import Pricing from "./pages/Pricing";
import Search from "./pages/Search";
import Settings from "./pages/Settings";

function Protected({ children }) {
  const { user, loading, verified } = useAuth();

  if (loading) return (
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", minHeight: "60vh", gap: 16 }}>
      <div className="spin" style={{ width: 36, height: 36, border: "3px solid #1e1e30", borderTopColor: "#34D399", borderRadius: "50%" }} />
      <span style={{ color: "var(--text-muted)", fontSize: 13 }}>جاري التحقق من الجلسة...</span>
    </div>
  );

  if (!verified) return <Navigate to="/auth" replace />;

  return children;
}

function AppRoutes() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/"          element={<Home />} />
        <Route path="/auth"      element={<Auth />} />
        <Route path="/share/:token" element={<SharePage />} />
        <Route path="/pricing" element={<Pricing />} />

        {/* مسارات محمية */}
        <Route path="/record"    element={<Protected><RecordPage /></Protected>} />
        <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
        <Route path="/search" element={<Protected><Search /></Protected>} />
        <Route path="/watch/:id" element={<Protected><WatchPage /></Protected>} />
        <Route path="/settings" element={<Protected><Settings /></Protected>} />

        {/* أي مسار غير معروف */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
