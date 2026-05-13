import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createAssessment } from "../lib/api";
import { buildConsentPayload, PRIVACY_POSTURE_STATEMENT } from "../lib/privacy";

export function NewAssessmentPage() {
  const navigate = useNavigate();
  const [participantName, setParticipantName] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const assessment = await createAssessment(participantName.trim(), buildConsentPayload());
      navigate(`/assessments/${assessment.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create assessment.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-4">
      <section className="card">
        <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Assessment setup</p>
        <h2 className="mt-2 text-2xl font-semibold">Start a new manual assessment</h2>
        <p className="mt-3 text-sm text-ink/70">
          Structured manual scores are retained under policy. Review videos are optional and temporary.
        </p>
        <p className="mt-3 rounded-2xl bg-panel px-4 py-3 text-sm text-ink/75">{PRIVACY_POSTURE_STATEMENT}</p>
      </section>
      <form className="card grid gap-4" onSubmit={handleSubmit}>
        <label className="grid gap-2">
          <span className="text-sm font-semibold">Participant name or ID</span>
          <input
            className="rounded-2xl border border-rim bg-panel px-4 py-3 text-ink outline-none transition focus:border-accent"
            maxLength={120}
            onChange={(event) => setParticipantName(event.target.value)}
            required
            value={participantName}
          />
        </label>
        <label className="flex items-start gap-3 rounded-2xl bg-panel px-4 py-4 text-sm text-ink/75">
          <input
            checked={accepted}
            className="mt-1 h-4 w-4 rounded border-slate-300 text-accent"
            onChange={(event) => setAccepted(event.target.checked)}
            type="checkbox"
          />
          <span>
            I confirm participation is voluntary, temporary review-video retention has been explained, and results are
            not used as a stand-alone basis for employment decisions.
          </span>
        </label>
        {error ? <p className="text-sm text-rose-600">{error}</p> : null}
        <button className="button-primary" disabled={!accepted || !participantName.trim() || saving} type="submit">
          {saving ? "Creating..." : "Create manual assessment"}
        </button>
      </form>
    </div>
  );
}
