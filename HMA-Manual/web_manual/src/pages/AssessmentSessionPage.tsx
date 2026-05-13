import { type ChangeEvent, type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ProgressChecklist } from "../components/ProgressChecklist";
import {
  completeAssessment,
  deleteAllReviewVideos,
  deleteReviewVideo,
  getAssessment,
  issueUploadSession,
  listMovements,
  saveManualScore,
  uploadReviewVideo
} from "../lib/api";
import { prettyFault } from "../lib/formatters";
import { MANUAL_FAULT_PROMPTS } from "../lib/manualScoring";
import type {
  ManualAssessmentDetail,
  ManualReviewVideo,
  ManualScorePayload,
  MovementDefinition,
  Side
} from "../lib/types";

type SideDraft = {
  score: number | null;
  faults: string[];
};

type MovementDraft = Partial<Record<Side, SideDraft>> & {
  providerNote?: string;
};

type PendingVideo = {
  file: File;
  previewUrl: string;
};

function sideLabel(side: Side) {
  return side === "left" ? "Left side" : "Right side";
}

function makeClientVideoId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function slotKey(movementKey: string, side: Side) {
  return `${movementKey}:${side}`;
}

export function AssessmentSessionPage() {
  const { assessmentId = "" } = useParams();
  const navigate = useNavigate();
  const [assessment, setAssessment] = useState<ManualAssessmentDetail | null>(null);
  const [movements, setMovements] = useState<MovementDefinition[]>([]);
  const [selectedMovementKey, setSelectedMovementKey] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, MovementDraft>>({});
  const [pendingVideos, setPendingVideos] = useState<Record<string, PendingVideo>>({});
  const [busySlot, setBusySlot] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linkForm, setLinkForm] = useState({ name: "", employer: "", email: "" });
  const [issuedLink, setIssuedLink] = useState<string | null>(null);

  async function refresh() {
    const [nextAssessment, nextMovements] = await Promise.all([getAssessment(assessmentId), listMovements()]);
    setAssessment(nextAssessment);
    setMovements(nextMovements);
    setDrafts((current) => seedDrafts(current, nextAssessment));
  }

  useEffect(() => {
    refresh().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Unable to load assessment.");
    });
  }, [assessmentId]);

  const completedKeys = useMemo(
    () => new Set(assessment?.movement_results.map((result) => result.movement_key) ?? []),
    [assessment]
  );
  const firstIncomplete = movements.find((movement) => !completedKeys.has(movement.key));
  const selectedMovement =
    movements.find((movement) => movement.key === selectedMovementKey) ?? firstIncomplete ?? movements[0];

  useEffect(() => {
    if (!selectedMovementKey && selectedMovement) {
      setSelectedMovementKey(selectedMovement.key);
    }
  }, [selectedMovement, selectedMovementKey]);

  const videosBySlot = useMemo(() => {
    const next: Record<string, ManualReviewVideo> = {};
    assessment?.review_videos.forEach((video) => {
      next[slotKey(video.movement_key, video.side)] = video;
    });
    return next;
  }, [assessment]);

  function setSideDraft(movementKey: string, side: Side, patch: Partial<SideDraft>) {
    setDrafts((current) => {
      const movementDraft = current[movementKey] ?? {};
      const sideDraft = movementDraft[side] ?? { score: null, faults: [] };
      return {
        ...current,
        [movementKey]: {
          ...movementDraft,
          [side]: {
            ...sideDraft,
            ...patch
          }
        }
      };
    });
  }

  function toggleFault(movementKey: string, side: Side, fault: string) {
    const currentFaults = drafts[movementKey]?.[side]?.faults ?? [];
    setSideDraft(movementKey, side, {
      faults: currentFaults.includes(fault)
        ? currentFaults.filter((item) => item !== fault)
        : [...currentFaults, fault]
    });
  }

  function setProviderNote(movementKey: string, providerNote: string) {
    setDrafts((current) => ({
      ...current,
      [movementKey]: {
        ...(current[movementKey] ?? {}),
        providerNote
      }
    }));
  }

  async function handleVideoFile(movementKey: string, side: Side, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const key = slotKey(movementKey, side);
    const previous = pendingVideos[key];
    if (previous) URL.revokeObjectURL(previous.previewUrl);
    setPendingVideos((current) => ({
      ...current,
      [key]: {
        file,
        previewUrl: URL.createObjectURL(file)
      }
    }));
  }

  async function uploadPendingVideo(movementKey: string, side: Side) {
    if (!assessment) return;
    const key = slotKey(movementKey, side);
    const pending = pendingVideos[key];
    if (!pending) return;
    setBusySlot(key);
    setError(null);
    try {
      await uploadReviewVideo(assessment.id, movementKey, side, pending.file, makeClientVideoId());
      URL.revokeObjectURL(pending.previewUrl);
      setPendingVideos((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to upload review video.");
    } finally {
      setBusySlot(null);
    }
  }

  async function handleDeleteVideo(video: ManualReviewVideo) {
    await deleteReviewVideo(video.assessment_id, video.id);
    await refresh();
  }

  async function handleSaveMovement() {
    if (!assessment || !selectedMovement) return;
    const draft = drafts[selectedMovement.key] ?? {};
    const payload: ManualScorePayload = {
      provider_note: draft.providerNote?.trim() || undefined
    };
    for (const side of selectedMovement.sides) {
      const sideDraft = draft[side];
      if (sideDraft?.score === null || sideDraft?.score === undefined) {
        setError(`Enter a score for ${sideLabel(side)} before saving.`);
        return;
      }
      payload[side] = {
        score: sideDraft.score,
        faults: sideDraft.faults
      };
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await saveManualScore(assessment.id, selectedMovement.key, payload);
      setAssessment(updated);
      const nextIncomplete = movements.find(
        (movement) =>
          movement.key !== selectedMovement.key &&
          !updated.movement_results.some((result) => result.movement_key === movement.key)
      );
      if (nextIncomplete) {
        setSelectedMovementKey(nextIncomplete.key);
      } else {
        navigate(`/assessments/${assessment.id}/results`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save score.");
    } finally {
      setSaving(false);
    }
  }

  async function handleIssueLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assessment) return;
    setError(null);
    setIssuedLink(null);
    try {
      const issued = await issueUploadSession(assessment.id, {
        name: linkForm.name.trim(),
        employer: linkForm.employer.trim(),
        email: linkForm.email.trim() || undefined
      });
      setIssuedLink(issued.url);
      setLinkForm({ name: "", employer: "", email: "" });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to issue upload link.");
    }
  }

  async function handleComplete() {
    if (!assessment) return;
    const confirmDeleteVideos = assessment.remaining_video_count > 0;
    if (confirmDeleteVideos) {
      const confirmed = window.confirm(
        `This assessment has ${assessment.remaining_video_count} temporary review video${assessment.remaining_video_count === 1 ? "" : "s"}. Delete them and mark scoring complete?`
      );
      if (!confirmed) return;
    }
    const updated = await completeAssessment(assessment.id, confirmDeleteVideos);
    setAssessment(updated);
    navigate(`/assessments/${assessment.id}/results`);
  }

  async function handleDeleteAllVideos() {
    if (!assessment) return;
    const confirmed = window.confirm(`Delete all remaining review videos for ${assessment.participant_name}?`);
    if (!confirmed) return;
    const response = await deleteAllReviewVideos(assessment.id);
    setAssessment(response.assessment);
  }

  if (!assessment || !selectedMovement) {
    return (
      <section className="card">
        <p className="text-sm text-ink/60">Loading manual session...</p>
        {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}
      </section>
    );
  }

  const movementDraft = drafts[selectedMovement.key] ?? {};
  const faultPrompts = MANUAL_FAULT_PROMPTS[selectedMovement.key] ?? [];

  return (
    <div className="grid gap-4">
      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Manual session</p>
            <h2 className="mt-1 text-2xl font-semibold">{assessment.participant_name}</h2>
            <p className="mt-2 text-sm text-ink/60">Manual scoring only</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-semibold">{assessment.total_score}/15</div>
            <p className="text-xs text-ink/50">Review videos remaining: {assessment.remaining_video_count}</p>
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
          <button className="button-secondary" onClick={() => void refresh()} type="button">
            Refresh videos
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {selectedMovement.sides.map((side) => {
            const sideDraft = movementDraft[side] ?? { score: null, faults: [] };
            const video = videosBySlot[slotKey(selectedMovement.key, side)];
            const pending = pendingVideos[slotKey(selectedMovement.key, side)];
            const isBusy = busySlot === slotKey(selectedMovement.key, side);
            return (
              <section className="rounded-2xl border border-rim bg-panel p-4" key={side}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.25em] text-ink/40">{side}</p>
                    <h3 className="font-semibold">{sideLabel(side)} score</h3>
                  </div>
                  <span className="rounded-full bg-panel-mid px-3 py-1 text-xs font-semibold text-ink/70">
                    {sideDraft.score === null ? "Not set" : `${sideDraft.score}/3`}
                  </span>
                </div>

                <div className="mt-4 grid grid-cols-4 gap-2">
                  {[0, 1, 2, 3].map((score) => (
                    <button
                      className={`rounded-full border py-2 text-sm font-semibold transition ${
                        sideDraft.score === score
                          ? "border-ink bg-ink text-white"
                          : "border-rim bg-panel text-ink hover:border-accent hover:text-accent"
                      }`}
                      key={score}
                      onClick={() => setSideDraft(selectedMovement.key, side, { score })}
                      type="button"
                    >
                      {score}
                    </button>
                  ))}
                </div>

                <div className="mt-4 grid gap-2">
                  {faultPrompts.map((fault) => (
                    <label className="flex items-center gap-2 rounded-xl bg-panel-mid px-3 py-2 text-sm" key={fault.key}>
                      <input
                        checked={sideDraft.faults.includes(fault.key)}
                        className="h-4 w-4 rounded border-slate-300 text-accent"
                        onChange={() => toggleFault(selectedMovement.key, side, fault.key)}
                        type="checkbox"
                      />
                      <span>{fault.label}</span>
                    </label>
                  ))}
                </div>

                <div className="mt-4 rounded-2xl border border-rim bg-panel p-3">
                  <p className="text-sm font-semibold">Optional review video</p>
                  {pending ? (
                    <video className="mt-3 aspect-video w-full rounded-2xl bg-slate-900 object-cover" controls playsInline src={pending.previewUrl} />
                  ) : video?.video_url ? (
                    <video className="mt-3 aspect-video w-full rounded-2xl bg-slate-900 object-cover" controls playsInline src={video.video_url} />
                  ) : video?.deleted_at ? (
                    <p className="mt-3 rounded-2xl bg-panel-mid px-3 py-3 text-sm text-ink/60">Video deleted or expired.</p>
                  ) : (
                    <div className="mt-3 flex aspect-video items-center justify-center rounded-2xl border border-dashed border-rim bg-panel-mid px-4 text-center text-sm text-ink/60">
                      No review video saved for this side.
                    </div>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <label className="button-secondary py-2">
                      {video?.video_url || pending ? "Replace video" : "Add video"}
                      <input
                        accept="video/*"
                        className="sr-only"
                        onChange={(event) => void handleVideoFile(selectedMovement.key, side, event)}
                        type="file"
                      />
                    </label>
                    {pending ? (
                      <button className="button-primary py-2" disabled={isBusy} onClick={() => void uploadPendingVideo(selectedMovement.key, side)} type="button">
                        {isBusy ? "Uploading..." : "Save video"}
                      </button>
                    ) : null}
                    {video?.video_url ? (
                      <button className="button-secondary py-2" onClick={() => void handleDeleteVideo(video)} type="button">
                        Delete video
                      </button>
                    ) : null}
                  </div>
                </div>
              </section>
            );
          })}
        </div>

        <textarea
          className="w-full resize-none rounded-2xl border border-rim bg-panel px-3 py-2 text-sm text-ink placeholder:text-ink/40 focus:border-accent focus:outline-none"
          maxLength={2000}
          onChange={(event) => setProviderNote(selectedMovement.key, event.target.value)}
          placeholder="Optional provider note"
          rows={2}
          value={movementDraft.providerNote ?? ""}
        />

        {error ? <p className="text-sm text-rose-600">{error}</p> : null}

        <div className="flex flex-wrap gap-3">
          <button className="button-primary" disabled={saving} onClick={() => void handleSaveMovement()} type="button">
            {saving ? "Saving..." : "Save movement score"}
          </button>
          <Link className="button-secondary" to={`/assessments/${assessment.id}/results`}>
            Review results
          </Link>
        </div>
      </section>

      <section className="card">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Employee upload link</p>
        <h2 className="mt-1 text-lg font-semibold">Issue mobile video request</h2>
        <form className="mt-4 grid gap-3 sm:grid-cols-3" onSubmit={handleIssueLink}>
          <input
            className="rounded-2xl border border-rim bg-panel px-4 py-3 text-ink outline-none focus:border-accent"
            onChange={(event) => setLinkForm((current) => ({ ...current, name: event.target.value }))}
            placeholder="Employee name"
            required
            value={linkForm.name}
          />
          <input
            className="rounded-2xl border border-rim bg-panel px-4 py-3 text-ink outline-none focus:border-accent"
            onChange={(event) => setLinkForm((current) => ({ ...current, employer: event.target.value }))}
            placeholder="Employer"
            required
            value={linkForm.employer}
          />
          <input
            className="rounded-2xl border border-rim bg-panel px-4 py-3 text-ink outline-none focus:border-accent"
            onChange={(event) => setLinkForm((current) => ({ ...current, email: event.target.value }))}
            placeholder="Email optional"
            type="email"
            value={linkForm.email}
          />
          <button className="button-primary sm:col-span-3" type="submit">
            Issue upload link
          </button>
        </form>
        {issuedLink ? (
          <div className="mt-4 rounded-2xl border border-accent/30 bg-accent/10 px-4 py-4">
            <p className="text-xs uppercase tracking-[0.25em] text-ink/45">Secure link</p>
            <code className="mt-2 block break-all rounded-xl bg-panel px-3 py-2 text-xs">{issuedLink}</code>
            <button
              className="button-secondary mt-3 py-2"
              onClick={() => navigator.clipboard.writeText(issuedLink)}
              type="button"
            >
              Copy link
            </button>
          </div>
        ) : null}
      </section>

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Completion</p>
            <h2 className="mt-1 text-lg font-semibold">Finish manual scoring</h2>
            <p className="mt-2 text-sm text-ink/65">
              Scoring completion requires deletion confirmation when review videos remain.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {assessment.remaining_video_count > 0 ? (
              <button className="button-secondary" onClick={() => void handleDeleteAllVideos()} type="button">
                Delete all videos
              </button>
            ) : null}
            <button className="button-primary" onClick={() => void handleComplete()} type="button">
              Complete assessment
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

function seedDrafts(current: Record<string, MovementDraft>, assessment: ManualAssessmentDetail) {
  const next = { ...current };
  for (const result of assessment.movement_results) {
    next[result.movement_key] = {
      ...(next[result.movement_key] ?? {}),
      right: {
        score: result.right_score,
        faults: result.faults.right ?? []
      },
      left: {
        score: result.left_score,
        faults: result.faults.left ?? []
      },
      providerNote: result.provider_note ?? ""
    };
  }
  return next;
}
