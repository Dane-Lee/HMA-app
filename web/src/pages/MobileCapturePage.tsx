import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  createMobileCaptureAssessment,
  getAssessment,
  listDraftCaptures,
  listMovements,
  uploadDraftCapture
} from "../lib/api";
import {
  deleteQueuedCapturesForAssessment,
  deleteQueuedCapture,
  listQueuedCaptures,
  type QueuedCapture,
  saveQueuedCapture
} from "../lib/mobileCaptureQueue";
import { buildConsentPayload, PRIVACY_POSTURE_STATEMENT } from "../lib/privacy";
import type { AssessmentDetail, DraftCapture, MovementDefinition, Side } from "../lib/types";

type PendingFile = {
  file: File;
  previewUrl: string;
};

type CaptureSlot = {
  key: string;
  movement: MovementDefinition;
  movementIndex: number;
  side: Side;
};

const SESSION_KEY = "hma-mobile-capture-session";

function slotKey(movementKey: string, side: Side) {
  return `${movementKey}:${side}`;
}

function sideLabel(side: Side) {
  return side === "left" ? "Left side" : "Right side";
}

function makeClientCaptureId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function buildCaptureSlots(movements: MovementDefinition[]) {
  return movements.flatMap<CaptureSlot>((movement, movementIndex) =>
    movement.sides.map((side) => ({
      key: slotKey(movement.key, side),
      movement,
      movementIndex,
      side
    }))
  );
}

export function MobileCapturePage() {
  const pendingUrlsRef = useRef<Set<string>>(new Set());
  const [name, setName] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [assessment, setAssessment] = useState<AssessmentDetail | null>(null);
  const [movements, setMovements] = useState<MovementDefinition[]>([]);
  const [selectedSlotIndex, setSelectedSlotIndex] = useState(0);
  const [draftCaptures, setDraftCaptures] = useState<DraftCapture[]>([]);
  const [queuedCaptures, setQueuedCaptures] = useState<QueuedCapture[]>([]);
  const [pendingFiles, setPendingFiles] = useState<Record<string, PendingFile>>({});
  const [uploadingIds, setUploadingIds] = useState<Set<string>>(new Set());
  const [slotErrors, setSlotErrors] = useState<Record<string, string>>({});
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMovements().then(setMovements).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Unable to load movement checklist.");
    });

    const storedId = localStorage.getItem(SESSION_KEY);
    if (storedId) {
      getAssessment(storedId)
        .then(setAssessment)
        .catch(() => localStorage.removeItem(SESSION_KEY));
    }
  }, []);

  useEffect(() => {
    if (!assessment) {
      return;
    }
    refreshDraftCaptures(assessment.id);
    refreshQueuedCaptures(assessment.id);
  }, [assessment]);

  useEffect(() => {
    return () => {
      pendingUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      pendingUrlsRef.current.clear();
    };
  }, []);

  const draftBySlot = useMemo(() => {
    const next: Record<string, DraftCapture> = {};
    draftCaptures.forEach((capture) => {
      next[slotKey(capture.movement_key, capture.side)] = capture;
    });
    return next;
  }, [draftCaptures]);

  const queuedBySlot = useMemo(() => {
    const next: Record<string, QueuedCapture> = {};
    queuedCaptures.forEach((capture) => {
      next[slotKey(capture.movementKey, capture.side)] = capture;
    });
    return next;
  }, [queuedCaptures]);

  const captureSlots = useMemo(() => buildCaptureSlots(movements), [movements]);

  useEffect(() => {
    if (selectedSlotIndex >= captureSlots.length) {
      setSelectedSlotIndex(Math.max(captureSlots.length - 1, 0));
    }
  }, [captureSlots.length, selectedSlotIndex]);

  const uploadedSlotCount = captureSlots.filter((slot) => draftBySlot[slot.key]).length;
  const totalSlotCount = captureSlots.length;
  const allUploaded = totalSlotCount > 0 && uploadedSlotCount === totalSlotCount;
  const activeSlot = captureSlots[selectedSlotIndex];

  async function refreshDraftCaptures(assessmentId: string) {
    try {
      setDraftCaptures(await listDraftCaptures(assessmentId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load uploaded captures.");
    }
  }

  async function refreshQueuedCaptures(assessmentId: string) {
    setQueuedCaptures(await listQueuedCaptures(assessmentId));
  }

  async function handleCreateAssessment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsCreating(true);
    try {
      const nextAssessment = await createMobileCaptureAssessment(name.trim(), buildConsentPayload());
      localStorage.setItem(SESSION_KEY, nextAssessment.id);
      setAssessment(nextAssessment);
      setSelectedSlotIndex(0);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create assessment.");
    } finally {
      setIsCreating(false);
    }
  }

  function setPendingFile(movementKey: string, side: Side, file: File) {
    const key = slotKey(movementKey, side);
    setPendingFiles((current) => {
      const existing = current[key];
      if (existing) {
        URL.revokeObjectURL(existing.previewUrl);
        pendingUrlsRef.current.delete(existing.previewUrl);
      }
      const previewUrl = URL.createObjectURL(file);
      pendingUrlsRef.current.add(previewUrl);
      return {
        ...current,
        [key]: {
          file,
          previewUrl
        }
      };
    });
    setSlotErrors((current) => ({ ...current, [key]: "" }));
  }

  function clearPendingFile(movementKey: string, side: Side) {
    const key = slotKey(movementKey, side);
    setPendingFiles((current) => {
      const existing = current[key];
      if (existing) {
        URL.revokeObjectURL(existing.previewUrl);
        pendingUrlsRef.current.delete(existing.previewUrl);
      }
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function moveToNextIncompleteSlot(uploadedKey: string) {
    const uploadedIndex = captureSlots.findIndex((slot) => slot.key === uploadedKey);
    const laterIncomplete = captureSlots.findIndex(
      (slot, index) => index > uploadedIndex && slot.key !== uploadedKey && !draftBySlot[slot.key]
    );
    if (laterIncomplete >= 0) {
      setSelectedSlotIndex(laterIncomplete);
      return;
    }
    const firstIncomplete = captureSlots.findIndex(
      (slot) => slot.key !== uploadedKey && !draftBySlot[slot.key]
    );
    if (firstIncomplete >= 0) {
      setSelectedSlotIndex(firstIncomplete);
    }
  }

  async function uploadQueued(capture: QueuedCapture) {
    const key = slotKey(capture.movementKey, capture.side);
    setUploadingIds((current) => new Set(current).add(capture.id));
    setSlotErrors((current) => ({ ...current, [key]: "" }));
    try {
      const uploaded = await uploadDraftCapture(
        capture.assessmentId,
        capture.movementKey,
        capture.side,
        capture.id,
        capture.file
      );
      await deleteQueuedCapture(capture.id);
      setDraftCaptures((current) => [
        ...current.filter(
          (item) => item.movement_key !== uploaded.movement_key || item.side !== uploaded.side
        ),
        uploaded
      ]);
      setQueuedCaptures((current) => current.filter((item) => item.id !== capture.id));
      clearPendingFile(capture.movementKey, capture.side);
      moveToNextIncompleteSlot(key);
    } catch (reason) {
      setSlotErrors((current) => ({
        ...current,
        [key]: reason instanceof Error ? reason.message : "Upload failed. Retry when connected."
      }));
    } finally {
      setUploadingIds((current) => {
        const next = new Set(current);
        next.delete(capture.id);
        return next;
      });
    }
  }

  async function confirmAndUpload(movementKey: string, side: Side) {
    if (!assessment) {
      return;
    }
    const pending = pendingFiles[slotKey(movementKey, side)];
    if (!pending) {
      return;
    }
    const queued: QueuedCapture = {
      id: makeClientCaptureId(),
      assessmentId: assessment.id,
      movementKey,
      side,
      file: pending.file,
      fileName: pending.file.name,
      createdAt: new Date().toISOString()
    };
    await saveQueuedCapture(queued);
    setQueuedCaptures((current) => [
      ...current.filter((item) => item.movementKey !== movementKey || item.side !== side),
      queued
    ]);
    await uploadQueued(queued);
  }

  async function clearLocalQueuedCaptures() {
    if (!assessment) {
      return;
    }
    await deleteQueuedCapturesForAssessment(assessment.id);
    queuedCaptures.forEach((capture) => clearPendingFile(capture.movementKey, capture.side));
    setQueuedCaptures([]);
    setSlotErrors({});
  }

  async function startNewSession() {
    if (assessment) {
      await deleteQueuedCapturesForAssessment(assessment.id);
    }
    localStorage.removeItem(SESSION_KEY);
    pendingUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    pendingUrlsRef.current.clear();
    setAssessment(null);
    setName("");
    setAccepted(false);
    setDraftCaptures([]);
    setQueuedCaptures([]);
    setPendingFiles({});
    setSelectedSlotIndex(0);
    setSlotErrors({});
  }

  function goBack() {
    setSelectedSlotIndex((current) => Math.max(current - 1, 0));
  }

  function goNext() {
    setSelectedSlotIndex((current) => Math.min(current + 1, captureSlots.length - 1));
  }

  if (!assessment) {
    return (
      <div className="grid gap-4">
        <section className="card">
          <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Mobile capture</p>
          <h2 className="mt-2 text-2xl font-semibold">Capture videos on this device</h2>
          <p className="mt-3 text-sm text-ink/70">
            Create the assessment here, then record and upload each movement side from the phone or tablet.
          </p>
          <p className="mt-3 rounded-2xl bg-panel px-4 py-3 text-sm text-ink/75">
            {PRIVACY_POSTURE_STATEMENT}
          </p>
        </section>

        <form className="card grid gap-4" onSubmit={handleCreateAssessment}>
          <label className="grid gap-2">
            <span className="text-sm font-semibold">Participant name or ID</span>
            <input
              className="rounded-2xl border border-rim bg-panel px-4 py-3 text-ink outline-none transition focus:border-accent"
              maxLength={120}
              onChange={(event) => setName(event.target.value)}
              placeholder="Enter participant name or ID"
              required
              value={name}
            />
          </label>
          <div className="rounded-2xl bg-panel px-4 py-4 text-sm text-ink/75">
            Mobile review clips are uploaded for provider review, kept temporarily
            on the server, and deleted after the configured review window. If the
            device is offline, queued clips remain on this device until they are
            uploaded or deleted.
          </div>
          <label className="flex items-start gap-3 rounded-2xl bg-panel px-4 py-4 text-sm text-ink/75">
            <input
              checked={accepted}
              className="mt-1 h-4 w-4 rounded border-slate-300 text-accent"
              onChange={(event) => setAccepted(event.target.checked)}
              type="checkbox"
            />
            <span>
              I confirm participation is voluntary, this capture is limited to
              ergonomic/wellness screening and provider support, temporary video
              retention has been explained, and results are not used as a
              stand-alone basis for employment decisions.
            </span>
          </label>
          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          <button className="button-primary" disabled={!accepted || !name.trim() || isCreating} type="submit">
            {isCreating ? "Creating..." : "Create mobile capture session"}
          </button>
        </form>
      </div>
    );
  }

  const activeDraft = activeSlot ? draftBySlot[activeSlot.key] : undefined;
  const activeQueued = activeSlot ? queuedBySlot[activeSlot.key] : undefined;
  const activePending = activeSlot ? pendingFiles[activeSlot.key] : undefined;
  const activeUploading = activeQueued ? uploadingIds.has(activeQueued.id) : false;
  const activeStatus = activeDraft
    ? `Uploaded: score ${activeDraft.score}/3`
    : activeUploading
      ? "Uploading"
      : activeQueued
        ? "Recorded locally"
        : activePending
          ? "Ready to upload"
          : "Not recorded";

  return (
    <div className="grid gap-4">
      <section className="card">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Mobile capture</p>
            <h2 className="mt-1 text-2xl font-semibold">{assessment.name}</h2>
          </div>
          <div className="rounded-full bg-mist px-3 py-1 text-sm font-semibold text-accent">
            {uploadedSlotCount}/{totalSlotCount} clips
          </div>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-panel-mid">
          <div
            className="h-full rounded-full bg-accent transition-all"
            style={{ width: totalSlotCount ? `${(uploadedSlotCount / totalSlotCount) * 100}%` : "0%" }}
          />
        </div>
        <p className="mt-4 rounded-2xl bg-panel px-4 py-3 text-sm text-ink/70">
          Mobile review clips are temporary. Queued clips that have not uploaded
          remain on this device until they are uploaded, deleted, or a new
          session is started.
        </p>
        {allUploaded ? (
          <div className="mt-4 rounded-2xl bg-emerald-500/15 px-4 py-3 text-sm text-emerald-200">
            All videos were received successfully for this assessment.
          </div>
        ) : null}
        {queuedCaptures.length > 0 ? (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-amber-500/15 px-4 py-3 text-sm text-amber-100">
            <span>{queuedCaptures.length} local queued clip{queuedCaptures.length === 1 ? "" : "s"} on this device.</span>
            <button className="button-secondary py-2" onClick={() => void clearLocalQueuedCaptures()} type="button">
              Delete local queued clips
            </button>
          </div>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          <Link className="button-secondary py-2" to={`/assessments/${assessment.id}`}>
            Provider session
          </Link>
          <button className="button-secondary py-2" onClick={() => void startNewSession()} type="button">
            New session
          </button>
        </div>
      </section>

      {activeSlot ? (
        <section className="card grid gap-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-ink/45">
                Step {selectedSlotIndex + 1} of {totalSlotCount}
              </p>
              <h2 className="mt-1 text-2xl font-semibold">{activeSlot.movement.label}</h2>
              <div className="mt-2 flex flex-wrap gap-2">
                <span className="rounded-full bg-mist px-3 py-1 text-sm font-semibold text-accent">
                  {sideLabel(activeSlot.side)}
                </span>
                <span className="rounded-full bg-panel-mid px-3 py-1 text-sm font-semibold text-ink/70">
                  {activeStatus}
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl bg-panel px-4 py-3 text-sm text-ink/75">
            <p>{activeSlot.movement.instructions}</p>
            {activeSlot.movement.capture_tips.length > 0 ? (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-semibold text-accent">
                  Framing tips
                </summary>
                <ul className="mt-2 grid gap-2">
                  {activeSlot.movement.capture_tips.map((tip) => (
                    <li className="rounded-xl bg-panel-mid px-3 py-2" key={tip}>
                      {tip}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>

          <div className="rounded-2xl border border-rim bg-panel p-4">
            {activePending ? (
              <video
                className="aspect-video w-full rounded-2xl bg-slate-900 object-cover"
                controls
                playsInline
                src={activePending.previewUrl}
              />
            ) : activeDraft?.video_url ? (
              <details>
                <summary className="cursor-pointer rounded-2xl bg-panel-mid px-4 py-3 text-sm font-semibold">
                  Review uploaded clip
                </summary>
                <video
                  className="mt-3 aspect-video w-full rounded-2xl bg-slate-900 object-cover"
                  controls
                  playsInline
                  src={activeDraft.video_url}
                />
              </details>
            ) : (
              <div className="flex aspect-video items-center justify-center rounded-2xl border border-dashed border-rim bg-panel-mid px-4 text-center text-sm text-ink/60">
                Record this clip, then confirm upload.
              </div>
            )}

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="button-secondary min-h-14 px-5 py-4">
                {activeDraft || activeQueued || activePending ? "Retake clip" : "Record clip"}
                <input
                  accept="video/*"
                  capture="environment"
                  className="sr-only"
                  onChange={(event) => {
                    const nextFile = event.target.files?.[0];
                    if (nextFile) {
                      setPendingFile(activeSlot.movement.key, activeSlot.side, nextFile);
                    }
                    event.target.value = "";
                  }}
                  type="file"
                />
              </label>

              {activePending ? (
                <button
                  className="button-primary min-h-14 px-5 py-4"
                  disabled={activeUploading}
                  onClick={() => confirmAndUpload(activeSlot.movement.key, activeSlot.side)}
                  type="button"
                >
                  {activeUploading ? "Uploading..." : "Confirm upload"}
                </button>
              ) : activeQueued ? (
                <button
                  className="button-primary min-h-14 px-5 py-4"
                  disabled={activeUploading}
                  onClick={() => uploadQueued(activeQueued)}
                  type="button"
                >
                  {activeUploading ? "Uploading..." : "Retry upload"}
                </button>
              ) : null}
            </div>

            {activeDraft ? (
              <p className="mt-3 text-sm text-ink/70">
                Analyzed with {activeDraft.source}; confidence {Math.round(activeDraft.confidence * 100)}%.
              </p>
            ) : null}
            {slotErrors[activeSlot.key] ? (
              <p className="mt-3 text-sm text-rose-600">{slotErrors[activeSlot.key]}</p>
            ) : null}
          </div>

          <div className="sticky bottom-0 z-10 -mx-5 mt-2 flex gap-3 border-t border-rim bg-surface/95 px-5 py-3 backdrop-blur">
            <button
              className="button-secondary min-h-12 flex-1"
              disabled={selectedSlotIndex === 0}
              onClick={goBack}
              type="button"
            >
              Back
            </button>
            <button
              className="button-primary min-h-12 flex-1"
              disabled={selectedSlotIndex >= totalSlotCount - 1}
              onClick={goNext}
              type="button"
            >
              Next
            </button>
          </div>
        </section>
      ) : null}

      <details className="card">
        <summary className="cursor-pointer text-sm font-semibold text-accent">
          Checklist
        </summary>
        <div className="mt-4 grid gap-2">
          {captureSlots.map((slot, index) => {
            const isSelected = selectedSlotIndex === index;
            const isUploaded = Boolean(draftBySlot[slot.key]);
            const isQueued = Boolean(queuedBySlot[slot.key]);
            return (
              <button
                className={`flex items-center justify-between rounded-2xl border px-4 py-3 text-left transition ${
                  isSelected ? "border-accent bg-mist" : "border-rim bg-panel"
                }`}
                key={slot.key}
                onClick={() => setSelectedSlotIndex(index)}
                type="button"
              >
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-ink/40">
                    Clip {index + 1}
                  </p>
                  <p className="font-semibold">{slot.movement.label}</p>
                  <p className="text-sm text-ink/60">{sideLabel(slot.side)}</p>
                </div>
                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    isUploaded
                      ? "bg-emerald-500/20 text-emerald-300"
                      : isQueued
                        ? "bg-amber-500/20 text-amber-200"
                        : "bg-panel-mid text-ink/50"
                  }`}
                >
                  {isUploaded ? "Uploaded" : isQueued ? "Retry" : "Pending"}
                </span>
              </button>
            );
          })}
        </div>
      </details>
    </div>
  );
}
