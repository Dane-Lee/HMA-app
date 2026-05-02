import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { CaptureRecorder } from "../components/CaptureRecorder";
import { ProgressChecklist } from "../components/ProgressChecklist";
import {
  finalizeMovement,
  getAssessment,
  listDraftCaptures,
  listMovements,
  uploadCapture
} from "../lib/api";
import { bandTone, prettyFault } from "../lib/formatters";
import type {
  AssessmentDetail,
  CaptureResult,
  DraftCapture,
  FinalizePayload,
  MovementDefinition,
  Side
} from "../lib/types";

type CaptureMap = Partial<Record<Side, CaptureResult>>;
type DraftCaptureMap = Partial<Record<Side, DraftCapture>>;

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

  async function handleFinalize() {
    if (!selectedMovement || !assessment) {
      return;
    }
    const captures = {
      ...(draftCapturesByMovement[selectedMovement.key] ?? {}),
      ...(capturesByMovement[selectedMovement.key] ?? {})
    };
    const payload: FinalizePayload = {};
    if (captures.right) {
      payload.right = {
        score: captures.right.score,
        detected_faults: captures.right.detected_faults,
        metrics: captures.right.metrics
      };
    }
    if (captures.left) {
      payload.left = {
        score: captures.left.score,
        detected_faults: captures.left.detected_faults,
        metrics: captures.left.metrics
      };
    }
    const hasAllRequiredSides = selectedMovement.sides.every((side) => captures[side]);
    if (!hasAllRequiredSides) {
      setError("Capture and analyze both sides before saving this movement.");
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      const updatedAssessment = await finalizeMovement(assessment.id, selectedMovement.key, payload);
      setAssessment(updatedAssessment);
      setCapturesByMovement((current) => {
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

        {savedResult ? (
          <div className="rounded-3xl bg-mist p-4 text-sm text-ink/75">
            <p className="font-semibold text-ink">Saved result</p>
            <p className="mt-2">
              Final movement score: <strong>{savedResult.final_score}/3</strong>
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
