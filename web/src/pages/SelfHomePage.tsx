import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { endSelfSession, getSelfMe } from "../lib/api";
import type { SelfMe } from "../lib/types";

type LoadState = "loading" | "ready" | "unauthenticated" | "error";

export function SelfHomePage() {
  const navigate = useNavigate();
  const [me, setMe] = useState<SelfMe | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    getSelfMe()
      .then((data) => {
        if (cancelled) return;
        setMe(data);
        setState("ready");
      })
      .catch((reason) => {
        if (cancelled) return;
        const message = reason instanceof Error ? reason.message : "Unable to load your assessment.";
        if (message.includes("Authentication required")) {
          setState("unauthenticated");
        } else {
          setErrorMessage(message);
          setState("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSignOut() {
    try {
      await endSelfSession();
    } finally {
      navigate("/self/start/", { replace: true });
    }
  }

  if (state === "loading") {
    return <p className="text-sm text-ink/60">Loading…</p>;
  }

  if (state === "unauthenticated") {
    return (
      <section className="card bg-surface text-ink">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Session ended</p>
        <h2 className="mt-2 text-xl font-semibold">Your access link has expired</h2>
        <p className="mt-3 text-sm text-ink/70">
          Please contact your provider for a new assessment link.
        </p>
      </section>
    );
  }

  if (state === "error") {
    return (
      <section className="card bg-surface text-ink">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Something went wrong</p>
        <h2 className="mt-2 text-xl font-semibold">We couldn't load your assessment</h2>
        <p className="mt-3 text-sm text-ink/70">{errorMessage}</p>
      </section>
    );
  }

  const employee = me!.employee;

  return (
    <section className="grid gap-4">
      <div className="card bg-surface text-ink">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Welcome</p>
        <h2 className="mt-2 text-2xl font-semibold">Hi, {employee.name}</h2>
        <p className="mt-3 text-sm text-ink/70">
          Your assessment will appear here when it's ready. We'll guide you
          through five short movements, one at a time.
        </p>
      </div>
      <div className="flex justify-end">
        <button
          className="rounded-full border border-ink/15 bg-panel-mid px-4 py-2 text-sm font-semibold text-ink/80 transition hover:bg-panel-hi"
          onClick={handleSignOut}
          type="button"
        >
          Sign out
        </button>
      </div>
    </section>
  );
}
