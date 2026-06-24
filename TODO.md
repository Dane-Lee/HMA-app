# HMA App — TODO

Consolidated task list for both the AI app (`api/` + `web/`) and the Manual sister app (`HMA-Manual/`).
Source of truth for the AI roadmap is [docs/self-guided-assessment/phase-plan.md](docs/self-guided-assessment/phase-plan.md).

Last reviewed: 2026-06-24

---

## AI App (Self-Guided Employee Assessment)

### ✅ Done
- **Phase 1 — Identity, magic links, role separation.** Employee/magic-link/session tables,
  `auth_tokens`, provider + self-session routes, role-aware middleware, and the self-flow frontend.
- **Phase 2 (capture mechanics)** — recorder, quality gate, mobile capture, provider pose overlays.

### 🔲 Phase 0 — Groundwork (blocking; long lead time)
- [ ] Shoot the **demo videos** (5 looping clips, both sides) and drop into `web/public/`.
      None present yet — only the logo.
- [ ] Add content-schema fields to `config/movements.json` (`demo_video_url`, `coaching_cues`,
      `camera_setup_self`, `common_mistakes`, `recording_seconds_min/max`).
- [ ] **Legal / consent review**; add the `employer_distribution_acknowledged` consent flag.
- [ ] Confirm **HIPAA scope** for self-administered + employer-distributed flow.
- [ ] Confirm **MediaPipe is the production scoring path**, not the deterministic fallback
      (`README.md`). The quality gate is meaningless without it.
- [ ] Personal **mobile camera-prop reality test** for all 5 movements to calibrate coaching copy.

### 🔲 Phase 2 — Remaining
- [ ] Wire demo videos + content schema into the per-movement screens.
- [ ] Replace **scoring placeholders** with real logic — `excessive_effort_placeholder`,
      `finger_walking_placeholder` in `api/app/services/scoring/movements/`.

### 🔲 Phase 3 — Provider review queue (~1 week) — NOT STARTED
- [ ] Add `submission_status` field to assessments.
- [ ] `POST /api/provider/assessments/{id}/return-for-retake`.
- [ ] `POST /api/provider/assessments/{id}/publish`.
- [ ] `/provider/inbox` page (filterable, pain-flag first, then oldest unreviewed).
- [ ] Per-submission review view: per-side playback, score override, summary-text field.

### 🔲 Phase 4 — Employee status & summary view (~0.5 week) — NOT STARTED
- [ ] `GET /api/self/assessment` returning current state + published provider summary.
- [ ] Employee landing shows status (`submitted` / `returned_for_retake` / `reviewed`).
- [ ] `returned_for_retake` deep-links into just the flagged movements.
- [ ] `reviewed` shows plain-English summary (no numbers, no fault list).

### ⏸ Deferred / out of scope
- [ ] Phase 5 — Email notifications (deferred until volume justifies it).
- [ ] Phase 6 — Corrective exercises (separate project; own decision doc).

---

## Manual App (`HMA-Manual/`)

Provider-scored, no AI. Manual scoring workflow already added. Remaining work is deployment/hardening
(see [HMA-Manual/README.md](HMA-Manual/README.md)):

- [ ] Run HMA + HMA-Manual behind a **reverse proxy** with separate hostnames + HTTPS termination.
- [ ] Enable **provider MFA**.
- [ ] Move from single bootstrap password to **named provider accounts**.
- [ ] Complete **compliance review** for employee movement video handling and retention.
