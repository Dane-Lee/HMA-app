import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { logout } from "../lib/api";
import type { Provider } from "../lib/types";

type AppShellProps = {
  provider: Provider;
  onLogout: () => void;
};

const navItems = [
  { to: "/", label: "Overview" },
  { to: "/assessments/new", label: "New" },
  { to: "/history", label: "History" }
];

export function AppShell({ provider, onLogout }: AppShellProps) {
  const navigate = useNavigate();
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

  async function handleLogout() {
    await logout();
    onLogout();
    navigate("/", { replace: true });
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4 pb-12 pt-5 sm:px-6">
      <header className="mb-5 flex flex-col gap-4">
        <div className="card bg-brand text-white">
          <div className="flex items-start justify-between gap-4">
            <div className="inline-flex items-center rounded-2xl bg-white px-3 py-2">
              <img src="/ati-logo/ATI-logo.png" alt="ATI Worksite Solutions" className="h-9 w-auto" />
            </div>
            <div className="text-right">
              <h1 className="text-2xl font-semibold tracking-tight">HMA-Manual</h1>
              <p className="mt-1 text-xs text-white/55">{provider.display_name}</p>
            </div>
          </div>
          <p className="mt-3 max-w-xl text-sm text-white/65">
            Manual five-movement HMA scoring with temporary review videos and provider-controlled results.
          </p>
        </div>
        <nav aria-label="Primary" className="flex items-center gap-2 overflow-x-auto pb-1">
          <div className="flex gap-2">
            {navItems.map((item) => (
              <NavLink
                className={({ isActive }) =>
                  `rounded-full px-4 py-2 text-sm font-semibold transition ${
                    isActive ? "bg-accent text-white" : "bg-panel-mid text-ink/80 hover:bg-panel-hi hover:text-ink"
                  }`
                }
                key={item.to}
                to={item.to}
              >
                {item.label}
              </NavLink>
            ))}
          </div>
          <button
            aria-label="Toggle light/dark mode"
            className="ml-auto shrink-0 rounded-full border border-ink/20 bg-panel-mid px-3 py-2 text-sm font-semibold"
            onClick={toggleTheme}
            type="button"
          >
            {isLight ? "Dark" : "Light"}
          </button>
          <button className="button-secondary shrink-0 py-2" onClick={() => void handleLogout()} type="button">
            Sign out
          </button>
        </nav>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
