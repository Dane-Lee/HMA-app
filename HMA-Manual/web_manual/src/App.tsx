import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { getAuthStatus } from "./lib/api";
import type { Provider } from "./lib/types";
import { AssessmentResultsPage } from "./pages/AssessmentResultsPage";
import { AssessmentSessionPage } from "./pages/AssessmentSessionPage";
import { HistoryPage } from "./pages/HistoryPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { NewAssessmentPage } from "./pages/NewAssessmentPage";
import { SelfStartPage } from "./pages/SelfStartPage";
import { SelfUploadPage } from "./pages/SelfUploadPage";

export default function App() {
  const location = useLocation();
  const [authChecked, setAuthChecked] = useState(false);
  const [provider, setProvider] = useState<Provider | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAuthStatus()
      .then((status) => {
        if (cancelled) return;
        setProvider(status.provider);
        setAuthError(null);
      })
      .catch(() => {
        if (cancelled) return;
        setAuthError("Unable to reach the HMA-Manual backend at http://localhost:8003.");
      })
      .finally(() => {
        if (!cancelled) setAuthChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (location.pathname.startsWith("/self")) {
    return (
      <Routes>
        <Route path="/self/start/:token" element={<SelfStartPage />} />
        <Route path="/self/upload" element={<SelfUploadPage />} />
        <Route path="/self/*" element={<Navigate replace to="/self/upload" />} />
      </Routes>
    );
  }

  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-depth">
        <p className="text-sm text-white/45">Loading HMA-Manual...</p>
      </div>
    );
  }

  if (authError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-depth px-4">
        <section className="card max-w-lg">
          <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Backend unavailable</p>
          <h1 className="mt-2 text-2xl font-semibold">Start HMA-Manual API</h1>
          <p className="mt-3 text-sm text-ink/70">{authError}</p>
          <code className="mt-4 block rounded-2xl bg-panel px-4 py-3 text-sm">
            uvicorn api_manual.app.main:app --reload --port 8003
          </code>
        </section>
      </div>
    );
  }

  if (!provider) {
    return <LoginPage onLogin={setProvider} />;
  }

  return (
    <Routes>
      <Route element={<AppShell provider={provider} onLogout={() => setProvider(null)} />}>
        <Route index element={<HomePage />} />
        <Route path="/assessments/new" element={<NewAssessmentPage />} />
        <Route path="/assessments/:assessmentId" element={<AssessmentSessionPage />} />
        <Route path="/assessments/:assessmentId/results" element={<AssessmentResultsPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Route>
      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  );
}
