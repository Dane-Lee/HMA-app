import { type ChangeEvent, useEffect, useMemo, useState } from "react";

import { endSelfSession, getSelfMe, submitSelfUploads, uploadSelfReviewVideo } from "../lib/api";
import {
  deleteQueuedSelfVideo,
  listQueuedSelfVideos,
  type QueuedSelfVideo,
  saveQueuedSelfVideo
} from "../lib/selfUploadQueue";
import type { ManualReviewVideo, MovementDefinition, SelfMe, Side } from "../lib/types";

function slotKey(movementKey: string, side: Side) {
  return `${movementKey}:${side}`;
}

function sideLabel(side: Side) {
  return side === "left" ? "Left side" : "Right side";
}

function makeVideoId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

type CaptureSlot = {
  key: string;
  movement: MovementDefinition;
  side: Side;
};

export function SelfUploadPage() {
  const [me, setMe] = useState<SelfMe | null>(null);
  const [queued, setQueued] = useState<QueuedSelfVideo[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);

  async function refresh() {
    const [nextMe, nextQueued] = await Promise.all([getSelfMe(), listQueuedSelfVideos()]);
    setMe(nextMe);
    setQueued(nextQueued);
  }

  useEffect(() => {
    refresh().catch((reason: unknown) => {
      setErrors({ page: reason instanceof Error ? reason.message : "Unable to load upload session." });
    });
  }, []);

  const captureSlots = useMemo<CaptureSlot[]>(() => {
    if (!me) return [];
    const allowed = new Set(me.upload_session.allowed_slots.map((slot) => slotKey(slot.movement_key, slot.side)));
    return me.movements.flatMap((movement) =>
      movement.sides
        .filter((side) => allowed.has(slotKey(movement.key, side)))
        .map((side) => ({ key: slotKey(movement.key, side), movement, side }))
    );
  }, [me]);

  const videosBySlot = useMemo(() => {
    const next: Record<string, ManualReviewVideo> = {};
    me?.review_videos.forEach((video) => {
      if (!video.deleted_at) next[slotKey(video.movement_key, video.side)] = video;
    });
    return next;
  }, [me]);

  const queuedBySlot = useMemo(() => {
    const next: Record<string, QueuedSelfVideo> = {};
    queued.forEach((video) => {
      next[slotKey(video.movementKey, video.side)] = video;
    });
    return next;
  }, [queued]);

  const activeSlot = captureSlots[selectedIndex];
  const uploadedCount = captureSlots.filter((slot) => videosBySlot[slot.key]).length;
  const allUploaded = captureSlots.length > 0 && uploadedCount === captureSlots.length;

  async function queueFile(slot: CaptureSlot, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const queuedVideo: QueuedSelfVideo = {
      id: makeVideoId(),
      movementKey: slot.movement.key,
      side: slot.side,
      file,
      fileName: file.name,
      createdAt: new Date().toISOString()
    };
    await saveQueuedSelfVideo(queuedVideo);
    setQueued((current) => [
      ...current.filter((item) => item.movementKey !== slot.movement.key || item.side !== slot.side),
      queuedVideo
    ]);
    await uploadQueued(queuedVideo);
  }

  async function uploadQueued(video: QueuedSelfVideo) {
    const key = slotKey(video.movementKey, video.side);
    setUploadingId(video.id);
    setErrors((current) => ({ ...current, [key]: "" }));
    try {
      await uploadSelfReviewVideo(video.movementKey, video.side, video.file, video.id);
      await deleteQueuedSelfVideo(video.id);
      setQueued((current) => current.filter((item) => item.id !== video.id));
      await refresh();
      const nextIndex = captureSlots.findIndex((slot, index) => index > selectedIndex && !videosBySlot[slot.key]);
      if (nextIndex >= 0) setSelectedIndex(nextIndex);
    } catch (reason) {
      setErrors((current) => ({
        ...current,
        [key]: reason instanceof Error ? reason.message : "Upload failed. Retry when connected."
      }));
    } finally {
      setUploadingId(null);
    }
  }

  async function handleSubmit() {
    await submitSelfUploads();
    setSubmitted(true);
  }

  async function handleSignOut() {
    await endSelfSession();
    setMe(null);
  }

  if (!me) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-depth px-4">
        <section className="card max-w-md">
          <p className="text-sm text-ink/60">{errors.page ?? "Loading upload session..."}</p>
        </section>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="mx-auto flex min-h-screen max-w-2xl flex-col px-4 py-6">
        <section className="card">
          <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Submitted</p>
          <h1 className="mt-2 text-2xl font-semibold">Your videos were submitted</h1>
          <p className="mt-3 text-sm text-ink/70">Your provider can now complete manual scoring.</p>
          <button className="button-secondary mt-5" onClick={() => void handleSignOut()} type="button">
            End session
          </button>
        </section>
      </div>
    );
  }

  const activeQueued = activeSlot ? queuedBySlot[activeSlot.key] : undefined;
  const activeUploaded = activeSlot ? videosBySlot[activeSlot.key] : undefined;

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col px-4 py-6">
      <header className="card bg-brand text-white">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-white/55">HMA-Manual upload</p>
            <h1 className="mt-1 text-2xl font-semibold">Hi, {me.employee.name}</h1>
            <p className="mt-2 text-sm text-white/65">{uploadedCount}/{captureSlots.length} videos uploaded</p>
          </div>
          <img src="/ati-logo/ATI-logo.png" alt="ATI Worksite Solutions" className="h-9 rounded-xl bg-white px-2 py-1" />
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/15">
          <div className="h-full rounded-full bg-accent transition-all" style={{ width: captureSlots.length ? `${(uploadedCount / captureSlots.length) * 100}%` : "0%" }} />
        </div>
      </header>

      {activeSlot ? (
        <section className="card mt-4 grid gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-ink/45">
              Step {selectedIndex + 1} of {captureSlots.length}
            </p>
            <h2 className="mt-1 text-2xl font-semibold">{activeSlot.movement.label}</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              <span className="rounded-full bg-mist px-3 py-1 text-sm font-semibold text-accent">{sideLabel(activeSlot.side)}</span>
              <span className="rounded-full bg-panel-mid px-3 py-1 text-sm font-semibold text-ink/70">
                {activeUploaded ? "Uploaded" : activeQueued ? "Queued" : "Pending"}
              </span>
            </div>
          </div>
          <div className="rounded-2xl bg-panel px-4 py-3 text-sm text-ink/75">
            <p>{activeSlot.movement.instructions}</p>
            <p className="mt-3 text-ink/60">Keep the clip short and clear. Maximum upload size is controlled by the provider system.</p>
          </div>
          <div className="rounded-2xl border border-rim bg-panel p-4">
            <div className="flex aspect-video items-center justify-center rounded-2xl border border-dashed border-rim bg-panel-mid px-4 text-center text-sm text-ink/60">
              {activeUploaded ? "Video received." : activeQueued ? "Video is queued locally. Retry when connected." : "Record or choose a video for this movement side."}
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="button-secondary min-h-14 px-5 py-4">
                {activeUploaded || activeQueued ? "Replace video" : "Record video"}
                <input
                  accept="video/*"
                  capture="environment"
                  className="sr-only"
                  onChange={(event) => void queueFile(activeSlot, event)}
                  type="file"
                />
              </label>
              {activeQueued ? (
                <button className="button-primary min-h-14 px-5 py-4" disabled={uploadingId === activeQueued.id} onClick={() => void uploadQueued(activeQueued)} type="button">
                  {uploadingId === activeQueued.id ? "Uploading..." : "Retry upload"}
                </button>
              ) : null}
            </div>
            {errors[activeSlot.key] ? <p className="mt-3 text-sm text-rose-600">{errors[activeSlot.key]}</p> : null}
          </div>
          <div className="sticky bottom-0 z-10 -mx-5 flex gap-3 border-t border-rim bg-surface/95 px-5 py-3 backdrop-blur">
            <button className="button-secondary min-h-12 flex-1" disabled={selectedIndex === 0} onClick={() => setSelectedIndex((index) => Math.max(0, index - 1))} type="button">
              Back
            </button>
            <button className="button-primary min-h-12 flex-1" disabled={selectedIndex >= captureSlots.length - 1} onClick={() => setSelectedIndex((index) => Math.min(captureSlots.length - 1, index + 1))} type="button">
              Next
            </button>
          </div>
        </section>
      ) : null}

      <section className="card mt-4">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Checklist</p>
        <div className="mt-4 grid gap-2">
          {captureSlots.map((slot, index) => (
            <button
              className={`flex items-center justify-between rounded-2xl border px-4 py-3 text-left transition ${selectedIndex === index ? "border-accent bg-mist" : "border-rim bg-panel"}`}
              key={slot.key}
              onClick={() => setSelectedIndex(index)}
              type="button"
            >
              <div>
                <p className="font-semibold">{slot.movement.label}</p>
                <p className="text-sm text-ink/60">{sideLabel(slot.side)}</p>
              </div>
              <span className="rounded-full bg-panel-mid px-3 py-1 text-xs font-semibold">
                {videosBySlot[slot.key] ? "Uploaded" : queuedBySlot[slot.key] ? "Retry" : "Pending"}
              </span>
            </button>
          ))}
        </div>
        <button className="button-primary mt-5 w-full" disabled={!allUploaded} onClick={() => void handleSubmit()} type="button">
          Submit videos
        </button>
      </section>
    </div>
  );
}
