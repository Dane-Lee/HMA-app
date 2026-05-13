import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { completeAssessment, deleteAllReviewVideos, getAssessment, listMovements } from "../lib/api";
import { bandTone, formatTimestamp, prettyFault } from "../lib/formatters";
import type { ManualAssessmentDetail, MovementDefinition } from "../lib/types";

export function AssessmentResultsPage() {
  const { assessmentId = "" } = useParams();
  const [assessment, setAssessment] = useState<ManualAssessmentDetail | null>(null);
  const [movements, setMovements] = useState<MovementDefinition[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [nextAssessment, nextMovements] = await Promise.all([getAssessment(assessmentId), listMovements()]);
    setAssessment(nextAssessment);
    setMovements(nextMovements);
  }

  useEffect(() => {
    refresh().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Unable to load results.");
    });
  }, [assessmentId]);

  async function handleDeleteVideos() {
    if (!assessment) return;
    const confirmed = window.confirm(`Delete all remaining review videos for ${assessment.participant_name}?`);
    if (!confirmed) return;
    const response = await deleteAllReviewVideos(assessment.id);
    setAssessment(response.assessment);
  }

  async function handleComplete() {
    if (!assessment) return;
    const confirmed = assessment.remaining_video_count > 0
      ? window.confirm("Delete remaining review videos and mark this assessment complete?")
      : true;
    if (!confirmed) return;
    setAssessment(await completeAssessment(assessment.id, assessment.remaining_video_count > 0));
  }

  if (!assessment) {
    return (
      <section className="card">
        <p className="text-sm text-ink/60">Loading results...</p>
        {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}
      </section>
    );
  }

  const movementMap = new Map(movements.map((movement) => [movement.key, movement.label]));

  return (
    <div className="grid gap-4">
      <section className="card bg-brand text-white">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-white/65">Manual assessment</p>
            <h2 className="mt-1 text-3xl font-semibold">{assessment.participant_name}</h2>
            <p className="mt-2 text-sm text-white/70">{formatTimestamp(assessment.created_at)}</p>
          </div>
          <div className="text-right">
            <p className="text-4xl font-semibold">{assessment.total_score}/15</p>
            <span className={`mt-2 inline-flex rounded-full px-3 py-1 text-sm font-semibold ${bandTone(assessment.score_band)}`}>
              {assessment.score_band}
            </span>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link className="button-secondary border-white/30 bg-white/10 text-white hover:bg-white/20" to={`/assessments/${assessment.id}`}>
            Continue editing
          </Link>
          <Link className="button-secondary border-white/30 bg-white/10 text-white hover:bg-white/20" to="/history">
            History
          </Link>
          {assessment.remaining_video_count > 0 ? (
            <button className="button-secondary border-white/30 bg-white/10 text-white hover:bg-white/20" onClick={() => void handleDeleteVideos()} type="button">
              Delete videos
            </button>
          ) : null}
          <button className="button-secondary border-white/30 bg-white/10 text-white hover:bg-white/20" onClick={() => void handleComplete()} type="button">
            {assessment.status === "completed" ? "Re-confirm complete" : "Complete"}
          </button>
        </div>
      </section>

      <section className="card">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Video lifecycle</p>
        <p className="mt-3 text-sm text-ink/70">
          Remaining temporary review videos: <strong>{assessment.remaining_video_count}</strong>
        </p>
        <p className="mt-2 text-sm text-ink/60">
          Videos are deleted on provider confirmation or retention expiry. Structured manual scores remain.
        </p>
      </section>

      <section className="grid gap-3">
        {assessment.movement_results.length === 0 ? (
          <section className="card">
            <p className="text-sm text-ink/60">No movements scored yet.</p>
          </section>
        ) : (
          assessment.movement_results.map((result) => (
            <article className="card" key={result.movement_key}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Movement</p>
                  <h3 className="mt-1 text-xl font-semibold">{movementMap.get(result.movement_key) ?? result.movement_key}</h3>
                </div>
                <div className="rounded-full bg-mist px-4 py-2 text-sm font-semibold text-accent">
                  {result.final_score}/3
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-panel p-4">
                  <p className="text-xs uppercase tracking-[0.25em] text-ink/45">Right</p>
                  <p className="mt-2 text-2xl font-semibold">{result.right_score ?? "-"}</p>
                </div>
                <div className="rounded-2xl bg-panel p-4">
                  <p className="text-xs uppercase tracking-[0.25em] text-ink/45">Left</p>
                  <p className="mt-2 text-2xl font-semibold">{result.left_score ?? "-"}</p>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {(result.faults.summary ?? []).length ? (
                  result.faults.summary.map((fault) => (
                    <span className="rounded-full bg-panel-mid px-3 py-1 text-sm text-ink/70" key={fault}>
                      {prettyFault(fault)}
                    </span>
                  ))
                ) : (
                  <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-sm text-emerald-300">
                    No faults selected
                  </span>
                )}
              </div>
              {result.provider_note ? (
                <p className="mt-4 rounded-2xl bg-panel px-4 py-3 text-sm text-ink/70">{result.provider_note}</p>
              ) : null}
            </article>
          ))
        )}
      </section>
    </div>
  );
}
