import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Overview" },
  { to: "/assessments/new", label: "New" },
  { to: "/history", label: "History" }
];

export function AppShell() {
  const [isLight, setIsLight] = useState(false);

  useEffect(() => {
    setIsLight(document.documentElement.classList.contains("light"));
  }, []);

  function toggleTheme() {
    const next = !isLight;
    setIsLight(next);
    document.documentElement.classList.toggle("light", next);
    localStorage.setItem("hma-theme", next ? "light" : "dark");
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4 pb-12 pt-5 sm:px-6">
      <header className="mb-5 flex flex-col gap-4">
        <div className="card bg-brand text-white">
          <div className="flex items-start justify-between gap-4">
            <div className="inline-flex items-center rounded-2xl bg-white px-3 py-2">
              <img src="/ati-logo/ATI-logo.png" alt="ATI Worksite Solutions" className="h-9 w-auto" />
            </div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">HMA</h1>
              <button
                aria-label="Toggle light/dark mode"
                className="rounded-full border border-white/20 bg-white/10 p-2 transition hover:bg-white/20"
                onClick={toggleTheme}
                type="button"
              >
                {isLight ? (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
                  </svg>
                )}
              </button>
            </div>
          </div>
          <p className="mt-3 max-w-xl text-sm text-white/65">
            Mobile-first floor workflow for rapid five-movement capture,
            scoring, and provider review.
          </p>
        </div>
        <nav aria-label="Primary" className="flex items-center gap-2 overflow-x-auto pb-1">
          <div className="flex gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                className={({ isActive }) =>
                  `rounded-full px-4 py-2 text-sm font-semibold transition ${
                    isActive
                      ? "bg-accent text-white"
                      : "bg-panel-mid text-ink/80 hover:bg-panel-hi hover:text-ink"
                  }`
                }
                to={item.to}
              >
                {item.label}
              </NavLink>
            ))}
          </div>
          <NavLink
            className={({ isActive }) =>
              `ml-auto shrink-0 rounded-full px-5 py-3 text-sm font-semibold transition sm:px-6 ${
                isActive
                  ? "bg-accent text-white"
                  : "border border-accent/40 bg-accent/10 text-accent hover:bg-accent hover:text-white"
              }`
            }
            to="/mobile-capture"
          >
            Mobile Capture
          </NavLink>
        </nav>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
