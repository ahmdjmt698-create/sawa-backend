/**
 * API Client — يعمل في التطوير والإنتاج
 * يدعم الكوكيز httpOnly + CSRF + تجديد التوكن التلقائي
 */

const API_BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : "/api";

let csrfToken = null;

async function initCsrf() {
  try {
    const res = await fetch(`${API_BASE}/auth/csrf-token`, { credentials: "include" });
    if (res.ok) {
      const data = await res.json();
      csrfToken = data.csrf_token;
    }
  } catch { /* CSRF init is best-effort */ }
}

// استدعِ CSRF عند بدء التطبيق
initCsrf();

async function request(method, path, body, isFormData = false, isRetry = false) {
  const headers = {};
  if (!isFormData && body) headers["Content-Type"] = "application/json";

  // أضف CSRF token للطلبات غير GET
  if (method !== "GET" && csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    credentials: "include",
    body: isFormData ? body : body ? JSON.stringify(body) : undefined,
  });

  // تجديد التوكن التلقائي عند 401
  const noRefreshPaths = ["/auth/login", "/auth/register", "/auth/refresh"];
  if (res.status === 401 && !isRetry && !noRefreshPaths.some(p => path.includes(p))) {
    try {
      const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (refreshRes.ok) {
        return request(method, path, body, isFormData, true);
      }
    } catch { /* refresh failed */ }
    // أعد توجيه المستخدم لصفحة الدخول
    window.location.href = "/auth";
    throw new Error("انتهت الصلاحية");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "خطأ غير متوقع" }));
    const error = new Error(err.detail || "فشل الطلب");
    error.status = res.status;
    error.detail = err.detail;
    error.error_code = err.error_code;
    throw error;
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── Auth ──────────────────────────────────────────────
export const authAPI = {
  register: (name, email, password) =>
    request("POST", "/auth/register", { name, email, password }),

  login: (email, password) =>
    request("POST", "/auth/login", { email, password }),

  logout: () => request("POST", "/auth/logout"),
  me: () => request("GET", "/auth/me"),
  csrf: () => request("GET", "/auth/csrf-token"),

  // إعدادات الحساب
  updateName: (name) => request("PATCH", "/auth/settings/name", { name }),
  updatePassword: (current_password, new_password) =>
    request("PATCH", "/auth/settings/password", { current_password, new_password }),

  // إعادة تعيين كلمة المرور
  forgotPassword: (email) => request("POST", "/auth/forgot-password", { email }),
  verifyOtp: (email, otp) => request("POST", "/auth/verify-otp", { email, otp }),
  resetPassword: (reset_token, new_password) =>
    request("POST", "/auth/reset-password", { reset_token, new_password }),
};

// ── Videos ───────────────────────────────────────────
export const videosAPI = {
  upload: (file, title, dialect = "ar", mode = "screen", onProgress, noiseReduction = false) => {
    return new Promise((resolve, reject) => {
      const form = new FormData();
      form.append("file", file);
      form.append("title", title);
      form.append("dialect", dialect);
      form.append("mode", mode);
      if (noiseReduction) form.append("noise_reduction", "true");

      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}/videos/upload`);
      xhr.withCredentials = true;
      if (csrfToken) {
        xhr.setRequestHeader("X-CSRF-Token", csrfToken);
      }

      if (onProgress) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
        };
      }

      xhr.onload = () => {
        if (xhr.status === 201) resolve(JSON.parse(xhr.responseText));
        else {
          try { reject(new Error(JSON.parse(xhr.responseText).detail || "فشل")); }
          catch { reject(new Error("فشل الرفع")); }
        }
      };
      xhr.onerror = () => reject(new Error("خطأ في الشبكة — تحقق من اتصالك"));
      xhr.ontimeout = () => reject(new Error("انتهت مهلة الرفع — جرب تسجيلاً أقصر"));
      xhr.timeout = 300000;
      xhr.send(form);
    });
  },

  getMyVideos: ()    => request("GET", "/videos/my"),
  getVideo:    (id)  => request("GET", `/videos/${id}`),
  getByToken:  (tok) => request("GET", `/videos/share/${tok}`),
  deleteVideo: (id)  => request("DELETE", `/videos/${id}`),

  // Feature 4: إعدادات المشاركة المحمية
  updateShareSettings: (id, data) => request("PATCH", `/videos/${id}/share-settings`, data),
  unlockShare: (token, password)  => request("POST",  `/videos/share/${token}/unlock`, { password }),

  // روابط البث الآمنة
  streamUrl:       (videoId)  => `${API_BASE}/videos/${videoId}/stream`,
  shareStreamUrl:  (token)    => `${API_BASE}/videos/share/${token}/stream`,

  // Feature 6: HLS
  hlsUrl: (videoId) => `${API_BASE}/videos/${videoId}/hls/playlist.m3u8`,
  convertHls: (videoId) => request("POST", `/videos/${videoId}/hls/convert`),
};

// ── Transcripts ───────────────────────────────────────
export const transcriptAPI = {
  get:    (videoId)       => request("GET",   `/transcripts/${videoId}`),
  edit:   (videoId, data) => request("PATCH", `/transcripts/${videoId}`, data),
  retry:  (videoId)       => request("POST",  `/transcripts/${videoId}/retry`),
  export: (videoId, fmt)  => `${API_BASE}/transcripts/${videoId}/export?fmt=${fmt}`,
};

// ── AI Features ───────────────────────────────────────
export const aiAPI = {
  translate:  (videoId)    => request("POST", `/transcripts/${videoId}/translate`),
  summarize:  (videoId)    => request("POST", `/transcripts/${videoId}/summarize`),
  diarize:    (videoId, n) => request("POST", `/transcripts/${videoId}/diarize${n?`?num_speakers=${n}`:""}`),
  exportUrl:  (videoId, fmt) => `${API_BASE}/transcripts/${videoId}/export?fmt=${fmt}`,

  // Feature 2: الفصول الذكية
  generateChapters: (videoId) => request("POST", `/transcripts/${videoId}/chapters`),
  getChapters:      (videoId) => request("GET",  `/transcripts/${videoId}/chapters`),
};

// ── Comments ──────────────────────────────────────────
export const commentsAPI = {
  list:   (videoId)       => request("GET",    `/videos/${videoId}/comments`),
  add:    (videoId, data) => request("POST",   `/videos/${videoId}/comments`, data),
  delete: (commentId)     => request("DELETE", `/videos/comment/${commentId}`),
};

// ── Analytics ─────────────────────────────────────────
export const analyticsAPI = {
  ping: (videoId, secondsWatched) =>
    request("POST", `/videos/${videoId}/view-event`, { seconds_watched: secondsWatched }),
  get:  (videoId) => request("GET", `/videos/${videoId}/analytics`),
};

// ── Payments ──────────────────────────────────────────
export const paymentsAPI = {
  getPlans:  ()     => request("GET",  "/payments/plans"),
  getStatus: ()     => request("GET",  "/payments/status"),
  create:    (plan) => request("POST", "/payments/create", { plan }),
  demo:      (plan) => request("POST", `/payments/demo-activate/${plan}`),
};

// ── Search ────────────────────────────────────────────
export const searchAPI = {
  search:  (q)    => request("GET", `/search?q=${encodeURIComponent(q)}`),
  suggest: (q)    => request("GET", `/search/suggest?q=${encodeURIComponent(q)}`),
};
