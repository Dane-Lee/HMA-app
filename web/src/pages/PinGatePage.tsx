import { type FormEvent, useState } from "react";

import { authenticateWithPin } from "../lib/api";

type PinGatePageProps = {
  onSuccess: () => void;
};

export function PinGatePage({ onSuccess }: PinGatePageProps) {
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await authenticateWithPin(pin);
      onSuccess();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to reach the server. Make sure the app is running.");
      setPin("");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <div className="inline-flex items-center rounded-2xl bg-white px-4 py-3">
            <img src="/ati-logo/ATI-logo.png" alt="ATI Worksite Solutions" className="h-10 w-auto" />
          </div>
        </div>

        <form
          className="rounded-3xl border border-white/[0.07] bg-brand p-6"
          onSubmit={handleSubmit}
        >
          <p className="text-xs uppercase tracking-[0.3em] text-white/45">Secure access</p>
          <h1 className="mt-2 text-2xl font-semibold text-white">Enter access PIN</h1>
          <p className="mt-2 text-sm text-white/60">
            Contact your ATI administrator if you do not have a PIN.
          </p>

          <div className="mt-6 grid gap-4">
            <input
              aria-label="Access PIN"
              autoComplete="current-password"
              autoFocus
              className="w-full rounded-2xl border border-white/10 bg-white/[0.06] px-4 py-3 text-center text-2xl tracking-[0.5em] text-white placeholder:tracking-normal placeholder:text-white/25 focus:border-white/30 focus:outline-none"
              disabled={loading}
              inputMode="numeric"
              placeholder="••••"
              type="password"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
            />

            {error ? (
              <p className="text-center text-sm text-rose-400">{error}</p>
            ) : null}

            <button
              className="w-full rounded-full bg-accent py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!pin || loading}
              type="submit"
            >
              {loading ? "Checking..." : "Unlock"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
