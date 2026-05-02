import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { consumeMagicLink } from "../lib/api";

type State = "exchanging" | "error";

export function SelfStartPage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<State>("exchanging");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setErrorMessage("This link is missing a token. Contact your provider for a new link.");
      setState("error");
      return;
    }

    consumeMagicLink(token)
      .then(() => {
        if (cancelled) return;
        navigate("/self/home", { replace: true });
      })
      .catch((reason) => {
        if (cancelled) return;
        setErrorMessage(
          reason instanceof Error
            ? reason.message
            : "Link is invalid or expired."
        );
        setState("error");
      });

    return () => {
      cancelled = true;
    };
  }, [token, navigate]);

  if (state === "exchanging") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-brand px-4">
        <p className="text-sm text-white/60">Opening your assessment…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand px-4">
      <div className="w-full max-w-md rounded-3xl border border-white/[0.07] bg-brand p-6 text-white">
        <p className="text-xs uppercase tracking-[0.3em] text-white/45">Link unavailable</p>
        <h1 className="mt-2 text-2xl font-semibold">We can't open this link</h1>
        <p className="mt-3 text-sm text-white/65">{errorMessage}</p>
        <p className="mt-4 text-sm text-white/65">
          Please contact your provider to request a new assessment link.
        </p>
      </div>
    </div>
  );
}
