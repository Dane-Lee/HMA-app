import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { consumeUploadLink } from "../lib/api";

export function SelfStartPage() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("This link is missing a token. Contact your provider for a new link.");
      return;
    }
    consumeUploadLink(token)
      .then(() => navigate("/self/upload", { replace: true }))
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Link is invalid or expired.");
      });
  }, [navigate, token]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-brand px-4 text-white">
        <section className="w-full max-w-md rounded-3xl border border-white/10 bg-white/10 p-6">
          <p className="text-xs uppercase tracking-[0.3em] text-white/45">Link unavailable</p>
          <h1 className="mt-2 text-2xl font-semibold">We can't open this link</h1>
          <p className="mt-3 text-sm text-white/70">{error}</p>
        </section>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand px-4 text-white">
      <p className="text-sm text-white/60">Opening your upload session...</p>
    </div>
  );
}
