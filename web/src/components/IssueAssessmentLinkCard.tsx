import { type FormEvent, useState } from "react";

import { createEmployee, issueMagicLink } from "../lib/api";

type Issued = {
  url: string;
  expires_at: string;
  employee_name: string;
};

export function IssueAssessmentLinkCard() {
  const [name, setName] = useState("");
  const [employer, setEmployer] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState<Issued | null>(null);
  const [copied, setCopied] = useState(false);

  const trimmedName = name.trim();
  const trimmedEmployer = employer.trim();
  const canSubmit = !submitting && trimmedName.length > 0 && trimmedEmployer.length > 0;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setIssued(null);
    setCopied(false);
    try {
      const employee = await createEmployee({
        name: trimmedName,
        employer: trimmedEmployer,
        email: email.trim() || undefined
      });
      const link = await issueMagicLink(employee.id);
      setIssued({
        url: link.url,
        expires_at: link.expires_at,
        employee_name: employee.name
      });
      setName("");
      setEmployer("");
      setEmail("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to issue link.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCopy() {
    if (!issued) return;
    try {
      await navigator.clipboard.writeText(issued.url);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section className="card">
      <p className="text-xs uppercase tracking-[0.3em] text-ink/45">Self-guided</p>
      <h2 className="mt-2 text-lg font-semibold">Issue Assessment Link</h2>
      <p className="mt-2 text-sm text-ink/70">
        Generate a link an employee can open on their own phone to complete the
        assessment at their own pace.
      </p>

      <form className="mt-5 grid gap-3" onSubmit={handleSubmit}>
        <label className="grid gap-1 text-sm">
          <span className="text-ink/70">Name</span>
          <input
            className="rounded-2xl border border-rim bg-panel px-4 py-3 text-ink focus:border-accent focus:outline-none"
            disabled={submitting}
            onChange={(e) => setName(e.target.value)}
            required
            type="text"
            value={name}
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-ink/70">Employer</span>
          <input
            className="rounded-2xl border border-rim bg-panel px-4 py-3 text-ink focus:border-accent focus:outline-none"
            disabled={submitting}
            onChange={(e) => setEmployer(e.target.value)}
            required
            type="text"
            value={employer}
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-ink/70">Email (optional)</span>
          <input
            className="rounded-2xl border border-rim bg-panel px-4 py-3 text-ink focus:border-accent focus:outline-none"
            disabled={submitting}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            value={email}
          />
        </label>
        {error ? <p className="text-sm text-rose-400">{error}</p> : null}
        <button
          className="button-primary disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!canSubmit}
          type="submit"
        >
          {submitting ? "Issuing…" : "Issue Link"}
        </button>
      </form>

      {issued ? (
        <div className="mt-5 grid gap-3 rounded-2xl border border-accent/30 bg-accent/5 px-4 py-4">
          <p className="text-xs uppercase tracking-[0.3em] text-ink/45">
            Link for {issued.employee_name}
          </p>
          <code className="break-all rounded-xl bg-panel px-3 py-2 text-xs text-ink">
            {issued.url}
          </code>
          <p className="text-xs text-ink/60">
            Expires {new Date(issued.expires_at).toLocaleString()}
          </p>
          <button
            className="self-start rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
            onClick={handleCopy}
            type="button"
          >
            {copied ? "Copied" : "Copy link"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
