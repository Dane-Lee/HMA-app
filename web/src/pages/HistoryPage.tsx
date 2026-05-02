import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { deleteAssessment, listAssessments } from "../lib/api";
import { bandTone, formatTimestamp } from "../lib/formatters";
import { PRIVACY_POSTURE_STATEMENT } from "../lib/privacy";
import type { AssessmentSummary } from "../lib/types";

export function HistoryPage() {
  const [items, setItems] = useState<AssessmentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    listAssessments().then(setItems).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Unable to load assessment history.");
    });
  }, []);

  async function handleDelete(item: AssessmentSummary) {
    const confirmed = window.confirm(
      `Delete the assessment for ${item.name}? This removes stored results, draft metadata, and any remaining draft review videos.`
    );
    if (!confirmed) {
      return;
    }
    setDeletingId(item.id);
    setError(null);
    try {
      await deleteAssessment(item.id);
      setItems((current) => current.filter((candidate) => candidate.id !== item.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to delete assessment.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="grid gap-4">
      <section className="card">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Provider history</p>
        <h2 className="mt-2 text-2xl font-semibold">Assessment archive</h2>
        <p className="mt-3 text-sm text-ink/70">
          Review completed HMA sessions, total scores, ATI score band, and per-session details.
        </p>
        <p className="mt-3 rounded-2xl bg-panel px-4 py-3 text-sm text-ink/75">
          {PRIVACY_POSTURE_STATEMENT}
        </p>
      </section>

      <section className="grid gap-3">
        {error ? <p className="card text-sm text-rose-600">{error}</p> : null}
        {items.length === 0 ? (
          <p className="card text-sm text-ink/65">No assessments saved yet.</p>
        ) : (
          items.map((item) => (
            <article className="card transition hover:border-accent/40" key={item.id}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold">{item.name}</h3>
                  <p className="mt-2 text-sm text-ink/60">{formatTimestamp(item.created_at)}</p>
                  <p className="mt-2 text-sm text-ink/50">
                    Retain until {item.retention_expires_at ? formatTimestamp(item.retention_expires_at) : "not set"}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-semibold">{item.total_score}/15</p>
                  <span
                    className={`mt-2 inline-flex rounded-full px-3 py-1 text-xs font-semibold ${bandTone(
                      item.score_band
                    )}`}
                  >
                    {item.score_band}
                  </span>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link className="button-secondary py-2" to={`/assessments/${item.id}/results`}>
                  Review results
                </Link>
                <button
                  className="button-secondary py-2 text-rose-200"
                  disabled={deletingId === item.id}
                  onClick={() => void handleDelete(item)}
                  type="button"
                >
                  {deletingId === item.id ? "Deleting..." : "Delete assessment"}
                </button>
              </div>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
