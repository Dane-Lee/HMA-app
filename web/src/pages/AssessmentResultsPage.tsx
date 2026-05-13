import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { CaptureQualityNotice } from "../components/CaptureQualityNotice";
import { PoseOverlayViewer } from "../components/PoseOverlayViewer";
import { ThresholdBar } from "../components/ThresholdBar";
import {
  approveCalibrationSuggestion,
  deleteAssessment,
  getAssessment,
  getThresholds,
  listCalibrationSuggestions,
  listMovements,
  rejectCalibrationSuggestion,
  submitReview
} from "../lib/api";
import { bandTone, formatTimestamp, prettyFault } from "../lib/formatters";
import { MOVEMENT_CHECKS } from "../lib/movementChecks";
import { PRIVACY_POSTURE_STATEMENT } from "../lib/privacy";
import type {
  AssessmentDetail,
  CalibrationSuggestion,
  MovementDefinition,
  MovementResult,
  ThresholdsMap,
} from "../lib/types";

type ReviewDraft = {
  open: boolean;
  score: number;
  note: string;
  saving: boolean;
  saveError: string | null;
};

export function AssessmentResultsPage() {
  const { assessmentId = "" } = useParams();
  const navigate = useNavigate();
  const [assessment, setAssessment] = useState<AssessmentDetail | null>(null);
  const [movements, setMovements] = useState<MovementDefinition[]>([]);
  const [thresholds, setThresholds] = useState<ThresholdsMap>({});
  const [calibrationSuggestions, setCalibrationSuggestions] = useState<CalibrationSuggestion[]>([]);
  const [reviewDrafts, setReviewDrafts] = useState<Record<string, ReviewDraft>>({});
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    Promise.all([getAssessment(assessmentId), listMovements(), getThresholds(), listCalibrationSuggestions()])
      .then(([nextAssessment, nextMovements, nextThresholds, nextSuggestions]) => {
        setAssessment(nextAssessment);
        setMovements(nextMovements);
        setThresholds(nextThresholds);
        setCalibrationSuggestions(nextSuggestions);
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Unable to load assessment results.");
      });
  }, [assessmentId]);

  if (!assessment) {
    return (
      <div className="card">
        <p className="text-sm text-ink/60">Loading results...</p>
        {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}
      </div>
    );
  }

  const movementMap = new Map(movements.map((m) => [m.key, m.label]));

  function getDraft(movementKey: string, finalScore: number): ReviewDraft {
    return reviewDrafts[movementKey] ?? { open: false, score: finalScore, note: "", saving: false, saveError: null };
  }

  function setDraft(movementKey: string, patch: Partial<ReviewDraft>) {
    setReviewDrafts((prev) => ({
      ...prev,
      [movementKey]: { ...getDraft(movementKey, 0), ...patch },
    }));
  }

  async function handleConfirm(result: MovementResult) {
    setDraft(result.movement_key, { saving: true, saveError: null });
    try {
      const updated = await submitReview(assessmentId, result.movement_key, {
        provider_score: result.app_score_available ? result.final_score : result.effective_final_score,
        review_reason: "provider_confirm",
      });
      setAssessment(updated);
      setDraft(result.movement_key, { saving: false, open: false, saveError: null });
    } catch (reason) {
      setDraft(result.movement_key, {
        saving: false,
        saveError: reason instanceof Error ? reason.message : "Unable to save review.",
      });
    }
  }

  async function handleSaveOverride(result: MovementResult) {
    const draft = getDraft(result.movement_key, result.effective_final_score);
    setDraft(result.movement_key, { saving: true, saveError: null });
    try {
      const updated = await submitReview(assessmentId, result.movement_key, {
        provider_score: draft.score,
        provider_note: draft.note.trim() || undefined,
        review_reason: "provider_override",
      });
      setAssessment(updated);
      setDraft(result.movement_key, { saving: false, open: false, saveError: null });
    } catch (reason) {
      setDraft(result.movement_key, {
        saving: false,
        saveError: reason instanceof Error ? reason.message : "Unable to save override.",
      });
    }
  }

  async function handleApproveSuggestion(suggestion: CalibrationSuggestion) {
    setError(null);
    try {
      const response = await approveCalibrationSuggestion({
        movement_key: suggestion.movement_key,
        threshold_key: suggestion.threshold_key,
        old_value: suggestion.current_value,
        new_value: suggestion.suggested_value,
        rationale: suggestion.rationale
      });
      setThresholds(response.thresholds);
      setCalibrationSuggestions((current) =>
        current.filter((item) => item.id !== suggestion.id)
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to approve calibration.");
    }
  }

  async function handleRejectSuggestion(suggestion: CalibrationSuggestion) {
    setError(null);
    try {
      await rejectCalibrationSuggestion({
        movement_key: suggestion.movement_key,
        threshold_key: suggestion.threshold_key,
        old_value: suggestion.current_value,
        new_value: suggestion.suggested_value,
        rationale: suggestion.rationale
      });
      setCalibrationSuggestions((current) =>
        current.filter((item) => item.id !== suggestion.id)
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to reject calibration.");
    }
  }

  async function handleDeleteAssessment() {
    if (!assessment) {
      return;
    }
    const confirmed = window.confirm(
      `Delete the assessment for ${assessment.name}? This removes stored results, draft metadata, and any remaining draft review videos.`
    );
    if (!confirmed) {
      return;
    }
    setIsDeleting(true);
    setError(null);
    try {
      await deleteAssessment(assessment.id);
      navigate("/history");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to delete assessment.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="grid gap-4">
      <section className="card bg-brand text-white">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-white/65">Completed assessment</p>
            <h2 className="mt-1 text-3xl font-semibold">{assessment.name}</h2>
            <p className="mt-2 text-sm text-white/70">{formatTimestamp(assessment.created_at)}</p>
          </div>
          <div className="text-right">
            <p className="text-4xl font-semibold">{assessment.total_score}/15</p>
            <span
              className={`mt-2 inline-flex rounded-full px-3 py-1 text-sm font-semibold ${bandTone(
                assessment.score_band
              )}`}
            >
              {assessment.score_band}
            </span>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            className="button-secondary border-white/30 bg-white/10 text-white hover:bg-white/20"
            to={`/assessments/${assessment.id}`}
          >
            Continue editing
          </Link>
          <Link
            className="button-secondary border-white/30 bg-white/10 text-white hover:bg-white/20"
            to="/history"
          >
            Provider history
          </Link>
          <button
            className="button-secondary border-white/30 bg-white/10 text-white hover:bg-white/20"
            disabled={isDeleting}
            onClick={() => void handleDeleteAssessment()}
            type="button"
          >
            {isDeleting ? "Deleting..." : "Delete assessment"}
          </button>
        </div>
      </section>

      <section className="card">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Privacy posture</p>
        <p className="mt-3 text-sm text-ink/75">{PRIVACY_POSTURE_STATEMENT}</p>
        <p className="mt-2 text-sm text-ink/70">
          App scores and provider-reviewed scores are stored separately so the
          automated result remains a support tool, not a final employment action.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl bg-panel px-4 py-3">
            <p className="text-xs uppercase tracking-[0.25em] text-ink/45">Consent notice</p>
            <p className="mt-1 text-sm font-semibold">{assessment.consent_notice_version ?? "Not recorded"}</p>
          </div>
          <div className="rounded-2xl bg-panel px-4 py-3">
            <p className="text-xs uppercase tracking-[0.25em] text-ink/45">Retain until</p>
            <p className="mt-1 text-sm font-semibold">
              {assessment.retention_expires_at ? formatTimestamp(assessment.retention_expires_at) : "Not set"}
            </p>
          </div>
        </div>
        {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}
      </section>

      {calibrationSuggestions.length > 0 ? (
        <section className="card">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Calibration</p>
              <h2 className="mt-1 text-xl font-semibold">Provider learning suggestions</h2>
            </div>
            <span className="rounded-full bg-panel-mid px-3 py-1 text-xs font-semibold text-ink/70">
              {calibrationSuggestions.length} pending
            </span>
          </div>
          <div className="mt-4 grid gap-3">
            {calibrationSuggestions.map((suggestion) => (
              <article className="rounded-2xl border border-rim bg-panel p-4" key={suggestion.id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold">
                      {movementMap.get(suggestion.movement_key) ?? suggestion.movement_key}
                    </p>
                    <p className="mt-1 text-sm text-ink/65">{suggestion.threshold_key}</p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="font-semibold">
                      {suggestion.current_value} {"->"} {suggestion.suggested_value}
                    </p>
                    <p className="text-xs text-ink/50">
                      {suggestion.disagreement_count} disagreements
                    </p>
                  </div>
                </div>
                <p className="mt-3 text-sm text-ink/70">{suggestion.rationale}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    className="button-primary py-2 text-sm"
                    onClick={() => void handleApproveSuggestion(suggestion)}
                    type="button"
                  >
                    Approve threshold
                  </button>
                  <button
                    className="button-secondary py-2 text-sm"
                    onClick={() => void handleRejectSuggestion(suggestion)}
                    type="button"
                  >
                    Reject
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section className="grid gap-3">
        {assessment.movement_results.map((result) => {
          const draft = getDraft(result.movement_key, result.effective_final_score);
          const checks = MOVEMENT_CHECKS[result.movement_key] ?? [];
          const movementThresholds = thresholds[result.movement_key] ?? {};
          const isReviewed = result.review_status === "reviewed";
          const hasOverride =
            isReviewed &&
            result.provider_final_score !== null &&
            result.provider_final_score !== result.final_score;
          const appScoreLabel = result.app_score_available ? `${result.final_score}/3` : "Not run";
          const visibleFaults = result.provider_faults?.summary?.length
            ? result.provider_faults.summary
            : result.detected_faults.summary ?? [];

          return (
            <article className="card" key={result.movement_key}>
              {/* Header */}
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Movement</p>
                  <h3 className="mt-1 text-xl font-semibold">
                    {movementMap.get(result.movement_key) ?? result.movement_key}
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      isReviewed
                        ? "bg-emerald-500/20 text-emerald-300"
                        : "bg-panel-mid text-ink/60"
                    }`}
                  >
                    {isReviewed ? "Reviewed" : "Unreviewed"}
                  </span>
                  <div className="rounded-full bg-mist px-4 py-2 text-sm font-semibold text-accent">
                    {result.effective_final_score}/3
                  </div>
                </div>
              </div>

              {/* Provider override notice */}
              {hasOverride ? (
                <div className="mt-3 rounded-2xl bg-amber-500/20 px-4 py-3 text-sm">
                  <span className="font-semibold text-amber-300">Provider override: </span>
                  <span className="text-amber-200">{result.provider_final_score}/3</span>
                  <span className="ml-2 text-ink/50">(app: {appScoreLabel})</span>
                  {result.provider_note ? (
                    <p className="mt-1 italic text-ink/70">"{result.provider_note}"</p>
                  ) : null}
                </div>
              ) : null}

              {/* Side scores */}
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-panel p-4">
                  <p className="text-xs uppercase tracking-[0.25em] text-ink/45">Right effective</p>
                  <p className="mt-2 text-2xl font-semibold">{result.effective_right_score ?? "-"}</p>
                  <p className="mt-1 text-xs text-ink/50">
                    App: {result.app_score_available ? result.right_score ?? "-" : "Not run"}
                  </p>
                </div>
                <div className="rounded-2xl bg-panel p-4">
                  <p className="text-xs uppercase tracking-[0.25em] text-ink/45">Left effective</p>
                  <p className="mt-2 text-2xl font-semibold">{result.effective_left_score ?? "-"}</p>
                  <p className="mt-1 text-xs text-ink/50">
                    App: {result.app_score_available ? result.left_score ?? "-" : "Not run"}
                  </p>
                </div>
              </div>

              {/* Detected faults */}
              <div className="mt-4 flex flex-wrap gap-2">
                {visibleFaults.length ? (
                  visibleFaults.map((fault) => (
                    <span
                      className="rounded-full bg-panel-mid px-3 py-1 text-sm text-ink/70"
                      key={fault}
                    >
                      {prettyFault(fault)}
                    </span>
                  ))
                ) : (
                  <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-sm text-emerald-300">
                    No scoring faults detected
                  </span>
                )}
              </div>

              {/* Threshold bars */}
              {result.app_metrics && checks.length > 0 ? (
                <div className="mt-4 rounded-2xl bg-panel p-4">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-[0.25em] text-ink/45">
                    Scoring metrics
                  </p>
                  <div className="grid gap-3">
                    {checks.map((check) => {
                      const value = result.app_metrics![check.metricKey];
                      const threshold = movementThresholds[check.thresholdKey];
                      if (value === undefined || threshold === undefined) return null;
                      return (
                        <ThresholdBar
                          key={check.metricKey}
                          direction={check.direction}
                          label={check.label}
                          threshold={threshold}
                          unit={check.unit}
                          value={value}
                        />
                      );
                    })}
                  </div>
                </div>
              ) : null}

              <div className="mt-4 grid gap-3">
                <CaptureQualityNotice quality={result.quality} />
                <PoseOverlayViewer
                  detectedFaults={result.detected_faults.summary ?? []}
                  metrics={result.app_metrics}
                  movementKey={result.movement_key}
                  poseTrace={result.pose_trace}
                  thresholds={movementThresholds}
                  title={`${movementMap.get(result.movement_key) ?? result.movement_key} explanation`}
                />
              </div>

              {/* Review actions */}
              <div className="mt-4">
                {!draft.open ? (
                  <div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        className="button-secondary text-sm"
                        disabled={draft.saving}
                        onClick={() => handleConfirm(result)}
                        type="button"
                      >
                        {draft.saving ? "Saving..." : isReviewed ? "Re-confirm" : "Looks right"}
                      </button>
                      <button
                        className="button-secondary text-sm"
                        onClick={() =>
                          setDraft(result.movement_key, { open: true, score: result.effective_final_score, saveError: null })
                        }
                        type="button"
                      >
                        Override score
                      </button>
                    </div>
                    {draft.saveError ? (
                      <p className="mt-2 text-xs text-rose-600">{draft.saveError}</p>
                    ) : null}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-rim bg-panel p-4">
                    <p className="mb-3 text-sm font-semibold text-ink">Override score</p>

                    {/* Score picker */}
                    <div className="mb-3 flex gap-2">
                      {([0, 1, 2, 3] as const).map((s) => (
                        <button
                          key={s}
                          className={`flex-1 rounded-full border py-2 text-sm font-semibold transition ${
                            draft.score === s
                              ? "border-ink bg-ink text-white"
                              : "border-rim bg-panel text-ink hover:border-accent hover:text-accent"
                          }`}
                          onClick={() => setDraft(result.movement_key, { score: s })}
                          type="button"
                        >
                          {s}
                        </button>
                      ))}
                    </div>

                    {/* Note field */}
                    <textarea
                      className="mb-3 w-full resize-none rounded-2xl border border-rim bg-panel px-3 py-2 text-sm text-ink placeholder:text-ink/40 focus:border-accent focus:outline-none"
                      placeholder="Optional note (e.g. camera angle poor, patient reported pain...)"
                      rows={2}
                      value={draft.note}
                      onChange={(e) =>
                        setDraft(result.movement_key, { note: e.target.value })
                      }
                    />

                    {draft.saveError ? (
                      <p className="mb-2 text-xs text-rose-600">{draft.saveError}</p>
                    ) : null}

                    <div className="flex gap-2">
                      <button
                        className="button-primary text-sm"
                        disabled={draft.saving}
                        onClick={() => handleSaveOverride(result)}
                        type="button"
                      >
                        {draft.saving ? "Saving..." : "Save override"}
                      </button>
                      <button
                        className="button-secondary text-sm"
                        onClick={() => setDraft(result.movement_key, { open: false, saveError: null })}
                        type="button"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </article>
          );
        })}
      </section>
    </div>
  );
}
