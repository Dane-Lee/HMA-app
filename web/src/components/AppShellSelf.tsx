import { Outlet } from "react-router-dom";

export function AppShellSelf() {
  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4 pb-12 pt-5 sm:px-6">
      <header className="mb-5">
        <div className="card bg-brand text-white">
          <div className="flex items-center gap-4">
            <div className="inline-flex items-center rounded-2xl bg-white px-3 py-2">
              <img src="/ati-logo/ATI-logo.png" alt="ATI Worksite Solutions" className="h-9 w-auto" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight">Movement Assessment</h1>
          </div>
          <p className="mt-3 max-w-xl text-sm text-white/65">
            Complete five short movements at your own pace. Your videos will be
            sent to your provider for review.
          </p>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
