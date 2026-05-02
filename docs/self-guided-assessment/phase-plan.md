# Self-Guided Employee Assessment — Phase Plan

Sizing is informed by the answers in [decisions.md](decisions.md) and the existing app structure (FastAPI + SQLite + React/Vite, single shared PIN, draft-capture pipeline with `client_capture_id` idempotency, per-movement provider review already wired).

Estimates assume one developer working steadily. They are realistic ranges, not commitments.

## Locked decisions (recap)

1. **Auth:** magic link only, single-use, expiring.
2. **Link delivery:** manual (provider generates URL, copies, sends out-of-band).
3. **Tenancy:** single-tenant, but employee schema includes `employer` for future multi-tenant migration.
4. **Camera:** prop-and-walk-away primary, partner fallback noted; 12–15 s countdown, frame-visibility gate.
5. **Score visibility:** plain-English summary post-provider-review, no raw scores.
6. **Retake:** per-movement, provider-initiated.
7. **Pain stop:** skip-and-flag for higher-priority provider outreach.
8. **Demo assets:** real-person video.

---

## Phase 0 — Pre-build groundwork (parallel; ~1–2 weeks elapsed)

**Not gated by code.** Run these in parallel with Phase 1 so they're ready when Phase 2 starts.

- **Demo asset production**
  - Scout / book a model (one person, hip-width range of motion, can demonstrate all 5 movements cleanly).
  - Write a shot list per movement: angle, framing, start/end positions, loopable midpoint, both sides.
  - Half-day shoot, half-day edit. Output: 5 short looping clips (≤ ~6 s each), encoded for web (H.264 MP4 + WebM fallback), sized for mobile.
  - One-page model release form signed.
- **Consent / legal review**
  - The four existing scope flags ([api/app/repository.py](../../api/app/repository.py), [api/app/routes/assessments.py](../../api/app/routes/assessments.py)) carry over: `voluntary_wellness`, `purpose_limited`, `no_employment_decision`, `video_retention_acknowledged`.
  - Employer-distributed link materially changes the "voluntary" framing. Add a fifth flag (e.g. `employer_distribution_acknowledged`) and have legal review the full consent text before Phase 2 ships.
  - Confirm whether self-administered + employer-distributed pushes this into HIPAA scope; existing privacy posture is `voluntary_ergonomic_wellness` and that label may need to change.
- **Mobile camera-prop reality test**
  - Before Phase 2 starts, you personally do a prop-and-walk run for all 5 movements. Time the actual countdown needed. Record what surfaces work (counter, chair on a table, etc.). This calibrates the in-app coaching copy.

---

## Phase 1 — Identity, magic links, role separation (~1.5–2 weeks)

The largest single phase. Today's auth is one shared PIN ([api/app/routes/auth.py:32](../../api/app/routes/auth.py#L32)); this phase introduces real per-employee identity without touching the existing in-clinic flow.

**Schema additions**
- `employees` table: `id`, `email` (nullable — manual delivery means you may not have it), `name`, `employer` (string, single-tenant for now), `created_at`, `created_by_provider_id`, `notes`.
- `magic_link_tokens` table: `token` (random, URL-safe, 32+ bytes), `employee_id`, `assessment_id` (nullable until first use), `created_at`, `expires_at`, `consumed_at`, `revoked_at`.
- Session role: extend the existing session token store to carry a role (`provider` or `employee`) and a subject id. The existing `runtime.session_tokens` set ([api/app/routes/auth.py:35](../../api/app/routes/auth.py#L35)) becomes a map.

**API additions**
- `POST /api/provider/employees` — provider creates an employee record, returns the row.
- `POST /api/provider/employees/{id}/magic-link` — issues a token, returns the full URL (provider copies and sends manually). Configurable expiration; default 7 days.
- `POST /api/self/session` — body `{token}`. Validates, marks `consumed_at`, sets an employee session cookie. Idempotent within a window so reload doesn't break things.
- `GET /api/self/me` — returns employee info + assessment-in-progress pointer.
- Middleware: per-route role enforcement. Existing assessment endpoints stay provider-scoped; new `/api/self/*` endpoints are employee-scoped and resolve to the employee's own assessment only.

**Frontend additions**
- New route `/self/start/:token` — exchanges the token for a session, then routes into the employee flow.
- Provider UI: a small "Issue assessment link" card on the home page or history page that takes name + employer + optional email, creates the employee, and shows the magic-link URL with a copy button.

**Out of scope for this phase**
- Email sending (Phase 5 — deferred).
- Multi-tenant routing (single-tenant now; employer field is preparation only).

---

## Phase 2 — Self-guided capture flow (~1.5–2 weeks)

Reuses the existing draft-capture pipeline ([api/app/routes/assessments.py:282](../../api/app/routes/assessments.py#L282)) and per-movement finalize ([api/app/routes/assessments.py:424](../../api/app/routes/assessments.py#L424)). Most of the work is frontend + content.

**Content layer**
- Extend [config/movements.json](../../config/movements.json) (or a sibling file) with: `order`, `whats_checked` (one line), `coaching_cues[]` (3–5 short steps), `camera_setup_self[]` (prop-specific), `common_mistakes[]`, `demo_video_url`, `recording_seconds_min/max`.
- Drop the demo MP4/WebM files into [web/public/](../../web/public/) (or behind a static route on the API). Loop in a `<video>` with `loop muted playsinline autoplay`.

**Screen flow (mobile-first; gate desktop with "open on your phone + QR")**
1. Entry (after `/self/start/:token` lands them).
2. Welcome / what to expect (3 cards: time, what you'll do, what happens next).
3. Consent (four existing flags + the new employer-distribution flag).
4. Overview (5-movement checklist).
5. Per-movement card (master template, one per movement):
   - Title, "X of 5", what-this-checks line.
   - Looping demo.
   - Coaching cues (3–5 bullets).
   - Camera setup panel (prop instructions + framing).
   - Common mistakes panel.
   - "Watch again" + "I'm Ready" buttons.
   - Recording state: 12–15 s countdown with a live preview, plus a "person fully in frame" check before countdown starts.
   - After recording: preview, "Use this" / "Retake."
   - "Skip — this hurts" button always available, captures a reason (free text optional), routes the submission into the pain-flag queue.
6. Review screen (replay any clip, retake any side).
7. Submit.
8. Confirmation.

**Quality gate**
- Before a take counts, run a landmark-visibility check on the recorded video. If below threshold, force retake with a specific message ("we couldn't see your full body — please reposition the camera").
- This depends on MediaPipe being the production path, not the deterministic-fallback path noted in [README.md:110](../../README.md#L110). Confirm before this phase starts.

**Session resume**
- If the employee closes the tab, the next visit to their magic link (assuming not yet expired or consumed) lands them on the next incomplete movement. Existing `client_capture_id` idempotency makes this mostly free; the new piece is "where am I in the flow" derived from existing draft captures + a small `assessment_progress` field.

**Pain-flag handling**
- New movement-skip record with reason `pain` (or other). Assessment finalize allows missing movements when at least one was completed and the assessment carries a `pain_reported` flag at the assessment level.

---

## Phase 3 — Provider review queue (~1 week)

Today the provider can review per-assessment via URL ([api/app/routes/assessments.py:481](../../api/app/routes/assessments.py#L481)). This phase adds the inbox.

**Backend**
- New status field on assessments: `submission_status` ∈ {`in_progress`, `submitted`, `submitted_pain_flag`, `under_review`, `returned_for_retake`, `reviewed_published`}.
- New endpoint: `POST /api/provider/assessments/{id}/return-for-retake` with body `{movement_keys: [...], note}`. Marks specified movement results as `needs_retake` and flips assessment status. Issues a fresh magic-link if the previous one was consumed.
- New endpoint: `POST /api/provider/assessments/{id}/publish` — finalizes the provider summary text and flips status to `reviewed_published`.

**Frontend (provider)**
- `/provider/inbox` page: filterable list of submissions. Default sort: pain-flag first, then oldest unreviewed. Columns: name, employer, submitted-at, status, completion (5/5 / 4/5 etc.).
- Per-submission review view (extension of the existing results page): video playback for each side, score override field per movement (already exists), summary-text field for the eventual employee-facing message, "Return for retake" and "Publish" actions.

---

## Phase 4 — Employee status & summary view (~0.5 week)

**Frontend (employee)**
- After submission, the employee landing page (re-entered via the same magic link if still valid) shows status: `submitted`, `returned_for_retake`, `reviewed`.
- `returned_for_retake` deep-links into the partial flow for just the flagged movements.
- `reviewed` shows the plain-English summary the provider wrote. No numbers, no faults list. Possibly a "your provider's note" section.

**Backend**
- `GET /api/self/assessment` — returns the current state, including provider summary text once published.

---

## Phase 5 — Notifications (deferred; ~1 week when needed)

Manual delivery is fine for the pilot per Q2. Layer this in only when volume justifies the operational cost.

- Pick a transactional email provider (SES, SendGrid, Postmark, etc.).
- DKIM/SPF setup for the sending domain.
- Templates for: link issue, retake request, results published.
- Bounce/complaint handling.
- Add `email` and `phone` to `employees` (already plan to allow nullable) and gate auto-send on presence.

---

## Phase 6 — Corrective exercises (separate project; not scoped here)

Out of scope. When you're ready, treat as its own decision doc + phase plan.

---

## Risks worth re-flagging before code starts

1. **MediaPipe must be the production scoring path** for the quality gate to be meaningful. The current fallback heuristic ([README.md:110](../../README.md#L110)) won't catch bad framing. Confirm install and reliability before Phase 2.
2. **Consent text and privacy posture review must precede Phase 2 shipping.** Employer-distributed flow may change the privacy posture label and the disclosure language.
3. **Demo shoot must wrap before Phase 2 testing.** A placeholder still-image strategy is fine for in-development testing but ship-blocking otherwise.
4. **Mobile-only gating decision.** A laptop webcam can't film a side-view lunge. Either gate desktop with "open on your phone" or accept that desktop submissions will fail the quality gate.
5. **Magic-link sharing.** Anyone with the link can submit. For ergonomic screening this is acceptable; document it explicitly so it's an accepted risk, not a silent assumption.

---

## Suggested ordering of next concrete actions

1. Schedule the demo shoot (longest lead time).
2. Send consent text to legal.
3. Confirm MediaPipe is reliably available in the production runtime.
4. Start Phase 1 implementation work.

Phases 1 and 2 together are roughly 3–4 weeks of focused dev. Phases 3–4 together add another 1.5 weeks. Total to a usable pilot: ~5–6 weeks of dev time, plus the parallel asset/legal track.
