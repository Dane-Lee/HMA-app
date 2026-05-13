import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listAssessments } from "../lib/api";
import { bandTone, formatTimestamp } from "../lib/formatters";
import { PRIVACY_POSTURE_STATEMENT } from "../lib/privacy";
import type { ManualAssessmentSummary } from "../lib/types";

export function HomePage() {
  const [items, setItems] = useState<ManualAssessmentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAssessments().then(setItems).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Unable to load manual assessments.");
    });
  }, []);

  return (
    <div className="grid gap-4">
      <section className="card">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Start here</p>
        <h2 className="mt-2 text-2xl font-semibold">Begin HMA-Manual</h2>
        <p className="mt-3 max-w-2xl text-sm text-ink/70">
          Score the same five HMA movements manually. Optional review videos are temporary and provider-controlled.
        </p>
        <p className="mt-3 rounded-2xl bg-panel px-4 py-3 text-sm text-ink/75">{PRIVACY_POSTURE_STATEMENT}</p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link className="button-primary" to="/assessments/new">
            Start Manual Assessment
          </Link>
          <Link className="button-secondary" to="/history">
            Open History
          </Link>
        </div>
      </section>

      <section className="card">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Recent sessions</p>
            <h2 className="mt-1 text-lg font-semibold">Saved Manual Assessments</h2>
          </div>
          <Link className="text-sm font-semibold text-accent" to="/history">
            View all
          </Link>
        </div>
        <div className="mt-4 grid gap-3">
          {error ? <p className="text-sm text-rose-400">{error}</p> : null}
          {items.length === 0 ? (
            <p className="rounded-2xl bg-panel px-4 py-5 text-sm text-ink/50">No manual assessments yet.</p>
          ) : (
            items.slice(0, 4).map((item) => (
              <Link
                className="rounded-2xl border border-rim bg-panel px-4 py-4 transition hover:border-accent/50 hover:bg-panel-mid"
                key={item.id}
                to={`/assessments/${item.id}/results`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-semibold">{item.participant_name}</p>
                    <p className="mt-1 text-sm text-ink/60">{formatTimestamp(item.created_at)}</p>
                    {item.remaining_video_count > 0 ? (
                      <p className="mt-1 text-xs text-amber-300">{item.remaining_video_count} review video{item.remaining_video_count === 1 ? "" : "s"} remaining</p>
                    ) : null}
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-semibold">{item.total_score}/15</div>
                    <span className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-semibold ${bandTone(item.score_band)}`}>
                      {item.score_band}
                    </span>
                  </div>
                </div>
              </Link>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
