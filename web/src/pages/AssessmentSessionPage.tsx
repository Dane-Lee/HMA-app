import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { CaptureRecorder } from "../components/CaptureRecorder";
import { ProgressChecklist } from "../components/ProgressChecklist";
import {
  finalizeMovement,
  getAssessment,
  listDraftCaptures,
  listMovements,
  submitManualScore,
  uploadCapture
} from "../lib/api";
import { bandTone, prettyFault } from "../lib/formatters";
import { MANUAL_FAULT_PROMPTS } from "../lib/manualScoring";
import type {
  AssessmentDetail,
  CaptureResult,
  DraftCapture,
  FinalizePayload,
  ManualScorePayload,
  MovementDefinition,
  Side
} from "../lib/types";

type CaptureMap = Partial<Record<Side, CaptureResult>>;
type DraftCaptureMap = Partial<Record<Side, DraftCapture>>;
type ManualSideDraft = {
  open: boolean;
  score: number | null;
  faults: string[];
  otherFault: string;
};
type ManualDraftMap = Partial<Record<Side, ManualSideDraft>>;

function groupDraftCaptures(captures: DraftCapture[]) {
  return captures.reduce<Record<string, DraftCaptureMap>>((grouped, capture) => {
    grouped[capture.movement_key] = {
      ...(grouped[capture.movement_key] ?? {}),
      [capture.side]: capture
    };
    return grouped;
  }, {});
}

export function AssessmentSessionPage() {
  const { assessmentId = "" } = useParams();
  const navigate = useNavigate();
  const [assessment, setAssessment] = useState<AssessmentDetail | null>(null);
  const [movements, setMovements] = useState<MovementDefinition[]>([]);
  const [selectedMovementKey, setSelectedMovementKey] = useState<string | null>(null);
  const [capturesByMovement, setCapturesByMovement] = useState<Record<string, CaptureMap>>({});
  const [draftCapturesByMovement, setDraftCapturesByMovement] = useState<Record<string, DraftCaptureMap>>({});
  const [manualDraftsByMovement, setManualDraftsByMovement] = useState<Record<string, ManualDraftMap>>({});
  const [providerNotesByMovement, setProviderNotesByMovement] = useState<Record<string, string>>({});
  const [busySide, setBusySide] = useState<Side | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [nextAssessment, nextMovements] = await Promise.all([
          getAssessment(assessmentId),
          listMovements()
        ]);
        setAssessment(nextAssessment);
        setMovements(nextMovements);
        await refreshDraftCaptures();
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Unable to load assessment.");
      }
    }

    load();
  }, [assessmentId]);

  async function refreshDraftCaptures() {
    const draftCaptures = await listDraftCaptures(assessmentId);
    setDraftCapturesByMovement(groupDraftCaptures(draftCaptures));
  }

  const completedKeys = new Set(assessment?.movement_results.map((result) => result.movement_key) ?? []);
  const firstIncomplete = movements.find((movement) => !completedKeys.has(movement.key));
  const selectedMovement =
    movements.find((movement) => movement.key === selectedMovementKey) ??
    firstIncomplete ??
    movements[0];

  useEffect(() => {
    if (!selectedMovementKey && selectedMovement) {
      setSelectedMovementKey(selectedMovement.key);
    }
  }, [selectedMovement, selectedMovementKey]);

  async function handleAnalyze(side: Side, file: File) {
    if (!selectedMovement) {
      return;
    }
    setBusySide(side);
    setError(null);
    try {
      const result = await uploadCapture(assessmentId, selectedMovement.key, side, file);
      setCapturesByMovement((current) => ({
        ...current,
        [selectedMovement.key]: {
          ...(current[selectedMovement.key] ?? {}),
          [side]: result
        }
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to analyze capture.");
    } finally {
      setBusySide(null);
    }
  }

  function defaultManualDraft(seedScore?: number): ManualSideDraft {
    return {
      open: true,
      score: seedScore ?? null,
      faults: [],
      otherFault: ""
    };
  }

  function setManualDraft(
    movementKey: string,
    side: Side,
    patch: Partial<ManualSideDraft>
  ) {
    setManualDraftsByMovement((current) => {
      const movementDrafts = current[movementKey] ?? {};
      const existing = movementDrafts[side] ?? defaultManualDraft();
      return {
        ...current,
        [movementKey]: {
          ...movementDrafts,
          [side]: {
            ...existing,
            ...patch
          }
        }
      };
    });
  }

  function openManualScoring(movementKey: string, side: Side, seedScore?: number) {
    setManualDraftsByMovement((current) => {
      const movementDrafts = current[movementKey] ?? {};
      return {
        ...current,
        [movementKey]: {
          ...movementDrafts,
          [side]: movementDrafts[side] ?? defaultManualDraft(seedScore)
        }
      };
    });
  }

  function closeManualScoring(movementKey: string, side: Side) {
    setManualDraftsByMovement((current) => {
      const movementDrafts = { ...(current[movementKey] ?? {}) };
      delete movementDrafts[side];
      return {
        ...current,
        [movementKey]: movementDrafts
      };
    });
  }

  function toggleManualFault(movementKey: string, side: Side, fault: string) {
    const currentFaults = manualDraftsByMovement[movementKey]?.[side]?.faults ?? [];
    const nextFaults = currentFaults.includes(fault)
      ? currentFaults.filter((item) => item !== fault)
      : [...currentFaults, fault];
    setManualDraft(movementKey, side, { faults: nextFaults });
  }

  async function handleFinalize() {
    if (!selectedMovement || !assessment) {
      return;
    }
    const captures = {
      ...(draftCapturesByMovement[selectedMovement.key] ?? {}),
      ...(capturesByMovement[selectedMovement.key] ?? {})
    };
    const manualDrafts = manualDraftsByMovement[selectedMovement.key] ?? {};
    const sideStates = selectedMovement.sides.map((side) => ({
      side,
      capture: captures[side],
      manualDraft: manualDrafts[side],
      manualActive: assessment.scoring_mode === "manual" || Boolean(manualDrafts[side]?.open)
    }));
    const hasAllRequiredSides = sideStates.every((entry) => {
      if (entry.manualActive) {
        return entry.manualDraft?.score !== null && entry.manualDraft?.score !== undefined;
      }
      return Boolean(entry.capture);
    });
    if (!hasAllRequiredSides) {
      setError("Complete a manual score or analyzed capture for each side before saving this movement.");
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      let updatedAssessment = assessment;
      const appPayload: FinalizePayload = {};
      for (const entry of sideStates) {
        if (!entry.capture) {
          continue;
        }
        appPayload[entry.side] = {
          score: entry.capture.score,
          detected_faults: entry.capture.detected_faults,
          metrics: entry.capture.metrics,
          pose_trace: entry.capture.pose_trace ?? null,
          quality: entry.capture.quality
        };
      }
      if (Object.keys(appPayload).length > 0) {
        updatedAssessment = await finalizeMovement(assessment.id, selectedMovement.key, appPayload);
      }

      const manualPayload: ManualScorePayload = {
        provider_note: providerNotesByMovement[selectedMovement.key]?.trim() || undefined,
        review_reason: assessment.scoring_mode === "manual" ? "manual_mode" : "manual_override",
        accepted_for_learning: true
      };
      for (const entry of sideStates) {
        if (!entry.manualActive || entry.manualDraft?.score === null || entry.manualDraft?.score === undefined) {
          continue;
        }
        manualPayload[entry.side] = {
          score: entry.manualDraft.score,
          faults: entry.manualDraft.faults,
          other_fault: entry.manualDraft.otherFault.trim() || undefined,
          app_score: entry.capture?.score,
          app_metrics: entry.capture?.metrics,
          app_quality: entry.capture?.quality,
          app_source: entry.capture?.source
        };
      }
      if (manualPayload.left || manualPayload.right) {
        updatedAssessment = await submitManualScore(assessment.id, selectedMovement.key, manualPayload);
      }
      setAssessment(updatedAssessment);
      setCapturesByMovement((current) => {
        const next = { ...current };
        delete next[selectedMovement.key];
        return next;
      });
      setManualDraftsByMovement((current) => {
        const next = { ...current };
        delete next[selectedMovement.key];
        return next;
      });
      setProviderNotesByMovement((current) => {
        const next = { ...current };
        delete next[selectedMovement.key];
        return next;
      });

      const nextIncomplete = movements.find(
        (movement) =>
          movement.key !== selectedMovement.key &&
          !updatedAssessment.movement_results.some((result) => result.movement_key === movement.key)
      );

      if (nextIncomplete) {
        setSelectedMovementKey(nextIncomplete.key);
      } else {
        navigate(`/assessments/${assessment.id}/results`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save movement result.");
    } finally {
      setIsSaving(false);
    }
  }

  if (!assessment || !selectedMovement) {
    return (
      <div className="card">
        <p className="text-sm text-ink/60">Loading assessment session...</p>
        {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}
      </div>
    );
  }

  const savedResult = assessment.movement_results.find(
    (result) => result.movement_key === selectedMovement.key
  );
  const activeCaptures = capturesByMovement[selectedMovement.key] ?? {};
  const activeDraftCaptures = draftCapturesByMovement[selectedMovement.key] ?? {};
  const activeManualDrafts = manualDraftsByMovement[selectedMovement.key] ?? {};
  const faultPrompts = MANUAL_FAULT_PROMPTS[selectedMovement.key] ?? [];
  const mergedCaptures = {
    ...activeDraftCaptures,
    ...activeCaptures
  };

  return (
    <div className="grid gap-4">
      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Live session</p>
            <h2 className="mt-1 text-2xl font-semibold">{assessment.name}</h2>
            <p className="mt-2 text-sm text-ink/60">
              {assessment.scoring_mode === "manual" ? "Manual scoring mode" : "AI assisted scoring mode"}
            </p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-semibold">{assessment.total_score}/15</div>
            <span
              className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${bandTone(
                assessment.score_band
              )}`}
            >
              {assessment.score_band}
            </span>
          </div>
        </div>
      </section>

      <ProgressChecklist
        completedKeys={completedKeys}
        movements={movements}
        onSelect={setSelectedMovementKey}
        selectedKey={selectedMovement.key}
      />

      <section className="card grid gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Current movement</p>
            <h2 className="mt-1 text-2xl font-semibold">{selectedMovement.label}</h2>
            <p className="mt-3 text-sm text-ink/70">{selectedMovement.instructions}</p>
          </div>
          <button
            className="button-secondary"
            onClick={() => {
              refreshDraftCaptures().catch((reason: unknown) => {
                setError(reason instanceof Error ? reason.message : "Unable to refresh mobile captures.");
              });
            }}
            type="button"
          >
            Refresh mobile captures
          </button>
        </div>

        <ul className="grid gap-2 text-sm text-ink/70">
          {selectedMovement.capture_tips.map((tip) => (
            <li className="rounded-2xl bg-panel px-4 py-3" key={tip}>
              {tip}
            </li>
          ))}
        </ul>

        <CaptureRecorder
          busySide={busySide}
          draftCaptures={activeDraftCaptures}
          key={selectedMovement.key}
          onAnalyze={handleAnalyze}
          results={mergedCaptures}
          sides={selectedMovement.sides}
        />

        <section className="rounded-3xl border border-rim bg-surface p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-ink/40">Provider scoring</p>
              <h3 className="text-lg font-semibold">Manual score entry</h3>
            </div>
            <span className="rounded-full bg-panel-mid px-3 py-1 text-xs font-semibold text-ink/70">
              {assessment.scoring_mode === "manual" ? "Default for this assessment" : "Available per side"}
            </span>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {selectedMovement.sides.map((side) => {
              const draft = activeManualDrafts[side] ?? defaultManualDraft();
              const manualVisible = assessment.scoring_mode === "manual" || Boolean(activeManualDrafts[side]?.open);
              const captureScore = mergedCaptures[side]?.score;
              return (
                <section className="rounded-2xl border border-rim bg-panel p-4" key={side}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.25em] text-ink/40">{side}</p>
                      <h4 className="font-semibold capitalize">{side} manual score</h4>
                    </div>
                    <span className="rounded-full bg-panel-mid px-3 py-1 text-xs font-semibold text-ink/70">
                      {draft.score === null ? "Not set" : `${draft.score}/3`}
                    </span>
                  </div>

                  {!manualVisible ? (
                    <button
                      className="button-secondary mt-4 w-full"
                      onClick={() => openManualScoring(selectedMovement.key, side, captureScore)}
                      type="button"
                    >
                      Use manual scoring
                    </button>
                  ) : (
                    <div className="mt-4 grid gap-4">
                      <div className="grid grid-cols-4 gap-2">
                        {([0, 1, 2, 3] as const).map((score) => (
                          <button
                            className={`rounded-full border py-2 text-sm font-semibold transition ${
                              draft.score === score
                                ? "border-ink bg-ink text-white"
                                : "border-rim bg-panel text-ink hover:border-accent hover:text-accent"
                            }`}
                            key={score}
                            onClick={() => setManualDraft(selectedMovement.key, side, { score })}
                            type="button"
                          >
                            {score}
                          </button>
                        ))}
                      </div>

                      <div className="grid gap-2">
                        {faultPrompts.map((fault) => (
                          <label className="flex items-center gap-2 rounded-xl bg-panel-mid px-3 py-2 text-sm" key={fault.key}>
                            <input
                              checked={draft.faults.includes(fault.key)}
                              className="h-4 w-4 rounded border-slate-300 text-accent"
                              onChange={() => toggleManualFault(selectedMovement.key, side, fault.key)}
                              type="checkbox"
                            />
                            <span>{fault.label}</span>
                          </label>
                        ))}
                      </div>

                      <input
                        className="rounded-2xl border border-rim bg-panel px-3 py-2 text-sm text-ink placeholder:text-ink/40 focus:border-accent focus:outline-none"
                        maxLength={500}
                        onChange={(event) => setManualDraft(selectedMovement.key, side, { otherFault: event.target.value })}
                        placeholder="Other reason"
                        value={draft.otherFault}
                      />

                      {assessment.scoring_mode !== "manual" ? (
                        <button
                          className="button-secondary py-2 text-sm"
                          onClick={() => closeManualScoring(selectedMovement.key, side)}
                          type="button"
                        >
                          Use app score instead
                        </button>
                      ) : null}
                    </div>
                  )}
                </section>
              );
            })}
          </div>

          {(assessment.scoring_mode === "manual" || Object.values(activeManualDrafts).some(Boolean)) ? (
            <textarea
              className="mt-4 w-full resize-none rounded-2xl border border-rim bg-panel px-3 py-2 text-sm text-ink placeholder:text-ink/40 focus:border-accent focus:outline-none"
              maxLength={2000}
              onChange={(event) =>
                setProviderNotesByMovement((current) => ({
                  ...current,
                  [selectedMovement.key]: event.target.value
                }))
              }
              placeholder="Optional provider note"
              rows={2}
              value={providerNotesByMovement[selectedMovement.key] ?? ""}
            />
          ) : null}
        </section>

        {savedResult ? (
          <div className="rounded-3xl bg-mist p-4 text-sm text-ink/75">
            <p className="font-semibold text-ink">Saved result</p>
            <p className="mt-2">
              Final movement score: <strong>{savedResult.effective_final_score}/3</strong>
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {savedResult.detected_faults.summary?.map((fault) => (
                <span className="rounded-full bg-panel-mid px-3 py-1" key={fault}>
                  {prettyFault(fault)}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {error ? <p className="text-sm text-rose-600">{error}</p> : null}

        <div className="flex flex-wrap gap-3">
          <button className="button-primary" disabled={isSaving} onClick={handleFinalize} type="button">
            {isSaving ? "Saving..." : "Save movement score"}
          </button>
          <Link className="button-secondary" to={`/assessments/${assessment.id}/results`}>
            Review results
          </Link>
        </div>
      </section>
    </div>
  );
}
