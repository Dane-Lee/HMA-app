import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AppShellSelf } from "./components/AppShellSelf";
import { getAuthStatus } from "./lib/api";
import { AssessmentResultsPage } from "./pages/AssessmentResultsPage";
import { AssessmentSessionPage } from "./pages/AssessmentSessionPage";
import { HistoryPage } from "./pages/HistoryPage";
import { HomePage } from "./pages/HomePage";
import { ModeSelectionPage } from "./pages/ModeSelectionPage";
import { MobileCapturePage } from "./pages/MobileCapturePage";
import { NewAssessmentPage } from "./pages/NewAssessmentPage";
import { PinGatePage } from "./pages/PinGatePage";
import { SelfHomePage } from "./pages/SelfHomePage";
import { SelfStartPage } from "./pages/SelfStartPage";

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [authChecked, setAuthChecked] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [authRequired, setAuthRequired] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [modeSelected, setModeSelected] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setAuthChecked(false);
    setAuthError(null);
    setAuthenticated(false);
    setAuthRequired(false);
    setModeSelected(false);

    getAuthStatus()
      .then((data) => {
        if (cancelled) {
          return;
        }
        setAuthRequired(data.auth_required);
        setAuthenticated(data.authenticated);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setAuthError(
          "Unable to reach the FastAPI backend at http://localhost:8002. Start the backend for local development, or use the Docker HTTPS URL for device verification."
        );
      })
      .finally(() => {
        if (!cancelled) {
          setAuthChecked(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [retryCount]);

  useEffect(() => {
    if (authenticated && location.pathname !== "/" && !modeSelected) {
      setModeSelected(true);
    }
  }, [authenticated, location.pathname, modeSelected]);

  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-depth">
        <p className="text-sm text-white/40">Loading...</p>
      </div>
    );
  }

  if (authError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-depth px-4">
        <div className="w-full max-w-lg rounded-3xl border border-white/10 bg-surface p-6 text-white">
          <p className="text-xs uppercase tracking-[0.3em] text-white/45">Backend unavailable</p>
          <h1 className="mt-2 text-2xl font-semibold">Start the local API server</h1>
          <p className="mt-3 text-sm text-white/65">{authError}</p>
          <div className="mt-6 flex flex-wrap gap-3 text-sm text-white/60">
            <code className="rounded-full bg-white/5 px-3 py-2">uvicorn api.app.main:app --reload --port 8002</code>
            <code className="rounded-full bg-white/5 px-3 py-2">http://localhost:5181</code>
          </div>
          <button
            className="mt-6 rounded-full bg-accent px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90"
            onClick={() => setRetryCount((count) => count + 1)}
            type="button"
          >
            Retry connection
          </button>
        </div>
      </div>
    );
  }

  const isSelfPath = location.pathname.startsWith("/self");
  if (isSelfPath) {
    return (
      <Routes>
        <Route path="/self/start/:token" element={<SelfStartPage />} />
        <Route element={<AppShellSelf />}>
          <Route path="/self/home" element={<SelfHomePage />} />
        </Route>
        <Route path="/self/*" element={<Navigate replace to="/" />} />
      </Routes>
    );
  }

  if (authRequired && !authenticated) {
    return <PinGatePage onSuccess={() => setAuthenticated(true)} />;
  }

  if (location.pathname === "/" && !modeSelected) {
    return (
      <ModeSelectionPage
        onSelectMain={() => setModeSelected(true)}
        onSelectMobileCapture={() => {
          setModeSelected(true);
          navigate("/mobile-capture");
        }}
      />
    );
  }

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="/assessments/new" element={<NewAssessmentPage />} />
        <Route path="/assessments/:assessmentId" element={<AssessmentSessionPage />} />
        <Route path="/mobile-capture" element={<MobileCapturePage />} />
        <Route
          path="/assessments/:assessmentId/results"
          element={<AssessmentResultsPage />}
        />
        <Route path="/history" element={<HistoryPage />} />
      </Route>
      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  );
}
