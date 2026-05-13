import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { deleteAssessment, listAssessments } from "../lib/api";
import { bandTone, formatTimestamp } from "../lib/formatters";
import type { ManualAssessmentSummary } from "../lib/types";

export function HistoryPage() {
  const [items, setItems] = useState<ManualAssessmentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setItems(await listAssessments());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load history.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleDelete(item: ManualAssessmentSummary) {
    const confirmed = window.confirm(
      `Delete the manual assessment for ${item.participant_name}? This removes scores, metadata, and any remaining temporary review videos.`
    );
    if (!confirmed) return;
    await deleteAssessment(item.id);
    await refresh();
  }

  return (
    <section className="card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-ink/45">History</p>
          <h2 className="mt-1 text-2xl font-semibold">Manual Assessments</h2>
          <p className="mt-2 text-sm text-ink/65">Review completed and in-progress HMA-Manual sessions.</p>
        </div>
        <Link className="button-primary" to="/assessments/new">
          New
        </Link>
      </div>
      {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}
      <div className="mt-5 grid gap-3">
        {items.length === 0 ? (
          <p className="rounded-2xl bg-panel px-4 py-5 text-sm text-ink/50">No manual assessments saved yet.</p>
        ) : (
          items.map((item) => (
            <article className="rounded-2xl border border-rim bg-panel px-4 py-4" key={item.id}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h3 className="font-semibold">{item.participant_name}</h3>
                  <p className="mt-1 text-sm text-ink/60">{formatTimestamp(item.created_at)}</p>
                  <p className="mt-1 text-xs text-ink/45">
                    Status: {item.status} | Review videos remaining: {item.remaining_video_count}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-lg font-semibold">{item.total_score}/15</p>
                  <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${bandTone(item.score_band)}`}>
                    {item.score_band}
                  </span>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link className="button-secondary py-2" to={`/assessments/${item.id}`}>
                  Open
                </Link>
                <Link className="button-secondary py-2" to={`/assessments/${item.id}/results`}>
                  Results
                </Link>
                <button className="button-secondary py-2" onClick={() => void handleDelete(item)} type="button">
                  Delete
                </button>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
