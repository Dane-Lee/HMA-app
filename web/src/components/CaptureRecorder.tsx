import { useEffect, useRef, useState } from "react";

import { prettyFault } from "../lib/formatters";
import type { CaptureResult, DraftCapture, Side } from "../lib/types";

type CaptureRecorderProps = {
  sides: Side[];
  onAnalyze: (side: Side, file: File) => Promise<void>;
  busySide: Side | null;
  results: Partial<Record<Side, CaptureResult>>;
  draftCaptures?: Partial<Record<Side, DraftCapture>>;
};

type RecorderState = "idle" | "camera" | "recording";
type SideCaptureFile = {
  file: File;
  previewUrl: string;
};

export function CaptureRecorder({
  sides,
  onAnalyze,
  busySide,
  results,
  draftCaptures = {}
}: CaptureRecorderProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const previewUrlsRef = useRef<Set<string>>(new Set());
  const closeAfterStopRef = useRef(false);
  const [state, setState] = useState<RecorderState>("idle");
  const [filesBySide, setFilesBySide] = useState<Partial<Record<Side, SideCaptureFile>>>({});
  const [activeRecordingSide, setActiveRecordingSide] = useState<Side | null>(null);
  const [previewSide, setPreviewSide] = useState<Side | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      cleanupStream();
      previewUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      previewUrlsRef.current.clear();
    };
  }, []);

  async function startCamera() {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera capture is unavailable in this browser. Use the upload fallback.");
      return;
    }
    cleanupStream();
    try {
      closeAfterStopRef.current = false;
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false
      });
      streamRef.current = stream;
      setPreviewSide(null);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setState("camera");
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setError("Camera permission denied. Allow camera access in your browser settings and try again.");
      } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
        setError("No camera found on this device. Use the upload fallback.");
      } else if (name === "NotReadableError" || name === "TrackStartError") {
        setError("Camera is in use by another app. Close it and try again.");
      } else {
        setError("Unable to start camera. Use the upload fallback.");
      }
    }
  }

  function cleanupStream() {
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }

  function revokePreviewUrl(url: string) {
    URL.revokeObjectURL(url);
    previewUrlsRef.current.delete(url);
  }

  function setSelectedFile(side: Side, nextFile: File) {
    const previewUrl = URL.createObjectURL(nextFile);
    previewUrlsRef.current.add(previewUrl);
    setFilesBySide((current) => {
      const previousUrl = current[side]?.previewUrl;
      if (previousUrl) {
        revokePreviewUrl(previousUrl);
      }
      return {
        ...current,
        [side]: {
          file: nextFile,
          previewUrl
        }
      };
    });
    setPreviewSide(side);
  }

  function beginRecording(side: Side) {
    setError(null);
    if (!streamRef.current || typeof MediaRecorder === "undefined") {
      setError("Recording is unavailable. Enable the camera or use the upload fallback.");
      return;
    }
    chunksRef.current = [];
    const recorder = new MediaRecorder(streamRef.current, {
      mimeType: "video/webm"
    });
    recorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunksRef.current.push(event.data);
      }
    };
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: "video/webm" });
      setSelectedFile(
        side,
        new File([blob], `${side}-capture.webm`, { type: "video/webm" })
      );
      const shouldCloseCamera = closeAfterStopRef.current;
      closeAfterStopRef.current = false;
      setActiveRecordingSide(null);
      if (shouldCloseCamera) {
        cleanupStream();
        setState("idle");
      } else {
        setState("camera");
      }
    };
    recorder.start();
    setActiveRecordingSide(side);
    setState("recording");
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  }

  function closeCamera() {
    setError(null);
    if (state === "recording") {
      closeAfterStopRef.current = true;
      stopRecording();
      return;
    }
    cleanupStream();
    setState("idle");
    setActiveRecordingSide(null);
  }

  const activePreviewUrl =
    state === "idle" && previewSide ? filesBySide[previewSide]?.previewUrl : undefined;

  return (
    <section className="rounded-3xl border border-rim bg-surface p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-ink/40">Shared camera</p>
          <h3 className="text-lg font-semibold">Movement capture</h3>
        </div>
        <div className="rounded-full bg-mist px-3 py-1 text-sm font-semibold text-accent">
          {state === "recording" && activeRecordingSide
            ? `Recording ${activeRecordingSide}`
            : state === "camera"
              ? "Camera ready"
              : "Camera closed"}
        </div>
      </div>

      <div className="mt-4 grid gap-4">
        <div className="flex flex-wrap gap-2">
          {state === "idle" ? (
            <button className="button-secondary" onClick={startCamera} type="button">
              Enable camera
            </button>
          ) : null}
          {state !== "idle" ? (
            <button
              className="button-secondary"
              onClick={closeCamera}
              type="button"
            >
              Close camera
            </button>
          ) : null}
        </div>

        <video
          autoPlay={state !== "idle"}
          className="aspect-video w-full rounded-2xl bg-slate-900 object-cover"
          controls={Boolean(activePreviewUrl)}
          muted
          playsInline
          ref={videoRef}
          src={activePreviewUrl}
        />

        {error ? <p className="text-sm text-rose-600">{error}</p> : null}

        <div className="grid gap-3 sm:grid-cols-2">
          {sides.map((side) => {
            const file = filesBySide[side]?.file;
            const result = results[side];
            const draftCapture = draftCaptures[side];
            const isRecordingSide = state === "recording" && activeRecordingSide === side;
            const isBusy = busySide === side;
            const sideLabel = side === "left" ? "Left-side capture" : "Right-side capture";
            return (
              <section
                aria-label={sideLabel}
                className="rounded-2xl border border-rim bg-panel p-4"
                key={side}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.25em] text-ink/40">{side}</p>
                    <h4 className="font-semibold">{sideLabel}</h4>
                  </div>
                  <div className="rounded-full bg-panel-mid px-3 py-1 text-xs font-semibold text-ink/70">
                    {result ? `Score ${result.score}/3` : file ? "Ready" : "Not captured"}
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {isRecordingSide ? (
                    <button className="button-secondary" onClick={stopRecording} type="button">
                      Stop recording
                    </button>
                  ) : (
                    <button
                      className="button-secondary"
                      disabled={state !== "camera" || Boolean(busySide)}
                      onClick={() => beginRecording(side)}
                      type="button"
                    >
                      Record {side}-side
                    </button>
                  )}

                  <button
                    className="button-primary"
                    disabled={!file || isBusy || state === "recording"}
                    onClick={() => file && onAnalyze(side, file)}
                    type="button"
                  >
                    {isBusy ? "Analyzing..." : "Analyze capture"}
                  </button>
                </div>

                <label className="mt-4 block rounded-2xl border border-dashed border-rim bg-panel px-4 py-3 text-sm text-ink/70">
                  <span className="font-semibold text-ink">Upload fallback</span>
                  <input
                    accept="video/*"
                    aria-label={`${side} upload fallback`}
                    className="mt-3 block w-full text-sm"
                    disabled={state === "recording"}
                    onChange={(event) => {
                      const nextFile = event.target.files?.[0];
                      if (nextFile) {
                        cleanupStream();
                        setState("idle");
                        setActiveRecordingSide(null);
                        setSelectedFile(side, nextFile);
                      }
                    }}
                    type="file"
                  />
                </label>

                {draftCapture?.video_url ? (
                  <div className="mt-4">
                    <p className="mb-2 text-sm font-semibold">Mobile review clip</p>
                    <video
                      className="aspect-video w-full rounded-2xl bg-slate-900 object-cover"
                      controls
                      playsInline
                      src={draftCapture.video_url}
                    />
                  </div>
                ) : draftCapture?.video_deleted_at ? (
                  <p className="mt-4 rounded-2xl bg-panel px-4 py-3 text-sm text-ink/60">
                    Mobile review video expired; analyzed scores are still available.
                  </p>
                ) : null}

                {result ? (
                  <div className="mt-4 rounded-2xl bg-panel p-4">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold">Detected faults</p>
                      <p className="text-xs uppercase tracking-[0.25em] text-ink/45">
                        {result.source} | confidence {Math.round(result.confidence * 100)}%
                      </p>
                    </div>
                    <ul className="mt-3 grid gap-2 text-sm text-ink/75">
                      {result.detected_faults.length > 0 ? (
                        result.detected_faults.map((fault) => (
                          <li key={fault} className="rounded-xl bg-panel px-3 py-2 capitalize">
                            {prettyFault(fault)}
                          </li>
                        ))
                      ) : (
                        <li className="rounded-xl bg-emerald-500/20 px-3 py-2 text-emerald-300">
                          No scoring faults detected.
                        </li>
                      )}
                    </ul>
                  </div>
                ) : null}
              </section>
            );
          })}
        </div>
      </div>
    </section>
  );
}
