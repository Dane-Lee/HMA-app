import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { IssueAssessmentLinkCard } from "../components/IssueAssessmentLinkCard";
import { listAssessments } from "../lib/api";
import { bandTone, formatTimestamp } from "../lib/formatters";
import { PRIVACY_POSTURE_STATEMENT } from "../lib/privacy";
import type { AssessmentSummary } from "../lib/types";

export function HomePage() {
  const [items, setItems] = useState<AssessmentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAssessments().then(setItems).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Unable to load assessments.");
    });
  }, []);

  return (
    <div className="grid gap-4">
      <section className="card">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Start here</p>
        <h2 className="mt-2 text-2xl font-semibold">Begin On-Site HMA</h2>
        <p className="mt-3 max-w-2xl text-sm text-ink/70">
          Use a phone browser to capture short movement clips. Live session
          video is processed transiently; mobile review clips are kept only
          during the configured review window.
        </p>
        <p className="mt-3 rounded-2xl bg-panel px-4 py-3 text-sm text-ink/75">
          {PRIVACY_POSTURE_STATEMENT}
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link className="button-primary" to="/assessments/new">
            Start Assessment
          </Link>
          <Link className="button-secondary" to="/mobile-capture">
            Mobile Capture
          </Link>
          <Link className="button-secondary" to="/history">
            Open Provider History
          </Link>
        </div>
      </section>

      <IssueAssessmentLinkCard />

      <section className="card">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Recent sessions</p>
            <h2 className="mt-1 text-lg font-semibold">Saved Assessments</h2>
          </div>
          <Link className="text-sm font-semibold text-accent" to="/history">
            View all
          </Link>
        </div>
        <div className="mt-4 grid gap-3">
          {error ? <p className="text-sm text-rose-400">{error}</p> : null}
          {items.length === 0 ? (
            <p className="rounded-2xl bg-panel px-4 py-5 text-sm text-ink/50">
              No saved HMA assessments yet.
            </p>
          ) : (
            items.slice(0, 4).map((item) => (
              <Link
                className="rounded-2xl border border-rim bg-panel px-4 py-4 transition hover:border-accent/50 hover:bg-panel-mid"
                key={item.id}
                to={`/assessments/${item.id}/results`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-semibold">{item.name}</p>
                    <p className="mt-1 text-sm text-ink/60">{formatTimestamp(item.created_at)}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-semibold">{item.total_score}/15</div>
                    <span
                      className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-semibold ${bandTone(item.score_band)}`}
                    >
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
