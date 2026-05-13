import { type FormEvent, useState } from "react";

import { login } from "../lib/api";
import type { Provider } from "../lib/types";

type LoginPageProps = {
  onLogin: (provider: Provider) => void;
};

export function LoginPage({ onLogin }: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const response = await login(username.trim(), password, mfaCode.trim() || undefined);
      onLogin(response.provider);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand px-4">
      <main className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <div className="inline-flex items-center rounded-2xl bg-white px-4 py-3">
            <img src="/ati-logo/ATI-logo.png" alt="ATI Worksite Solutions" className="h-10 w-auto" />
          </div>
        </div>
        <form className="rounded-3xl border border-white/[0.07] bg-brand p-6 text-white" onSubmit={handleSubmit}>
          <p className="text-xs uppercase tracking-[0.3em] text-white/45">Provider access</p>
          <h1 className="mt-2 text-2xl font-semibold">HMA-Manual</h1>
          <div className="mt-6 grid gap-3">
            <label className="grid gap-1 text-sm">
              <span className="text-white/70">Username</span>
              <input
                autoComplete="username"
                className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-white outline-none focus:border-white/40"
                onChange={(event) => setUsername(event.target.value)}
                required
                value={username}
              />
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-white/70">Password</span>
              <input
                autoComplete="current-password"
                className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-white outline-none focus:border-white/40"
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-white/70">MFA code</span>
              <input
                autoComplete="one-time-code"
                className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-white outline-none focus:border-white/40"
                inputMode="numeric"
                maxLength={10}
                onChange={(event) => setMfaCode(event.target.value)}
                placeholder="Required when enabled"
                value={mfaCode}
              />
            </label>
          </div>
          {error ? <p className="mt-4 text-sm text-rose-200">{error}</p> : null}
          <button className="mt-6 w-full rounded-full bg-accent px-5 py-3 text-sm font-semibold text-white" disabled={submitting} type="submit">
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </main>
    </div>
  );
}
