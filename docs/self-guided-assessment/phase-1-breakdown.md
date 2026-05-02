# Phase 1 — Identity, Magic Links, Role Separation

Detailed task breakdown. Ordered so each step is independently testable.

## Goal

Per-employee identity in the app, plus a magic-link auth path for employees, without disturbing the existing PIN-protected provider flow.

By the end of Phase 1:
- Provider (PIN-authed) can create an `employee` record and issue a magic-link URL.
- Employee can click the URL and land authenticated as themselves (no UI for the assessment itself yet — that's Phase 2).
- Provider routes still require PIN. Employee routes still require an employee session.
- Existing in-clinic flow keeps working unchanged.

## Out of scope for Phase 1

- The assessment UI for employees (Phase 2).
- Provider inbox / review queue (Phase 3).
- Employee summary view (Phase 4).
- Email sending (Phase 5; manual link copy/paste only).
- Demo videos and the new movement content schema (Phase 2).

## Pre-flight checks

- [ ] Confirm `MediaPipe` and `OpenCV` are installed in the production runtime path. The fallback heuristic noted in [README.md:110](../../README.md#L110) won't be sufficient for the Phase 2 quality gate, but Phase 1 doesn't need it — flagging now so it's not surprise-blocking later.
- [ ] Decide on a magic-link lifetime. Recommended default: **7 days, multi-use within that window.** Single-use locks the employee out if their session cookie is dropped. Multi-use within a window matches normal "passwordless" patterns and aligns with the accepted risk that link sharing is permitted (Q11 in the critique).
- [ ] Decide on the employee session lifetime. Recommended: **session cookie expires after 12 hours of inactivity, or when the magic-link window expires — whichever comes first.** Matches the existing 12-hour cap on PIN sessions ([api/app/routes/auth.py:43](../../api/app/routes/auth.py#L43)).

---

## Backend tasks

All file paths are relative to repo root. New files are clearly labeled.

### B1. Add `employees` table

File: [api/app/database.py](../../api/app/database.py)

- Append a `CREATE TABLE IF NOT EXISTS employees` block to `SCHEMA_SQL`:
  ```
  id TEXT PRIMARY KEY
  name TEXT NOT NULL
  email TEXT
  employer TEXT NOT NULL
  created_at TEXT NOT NULL
  created_by TEXT       -- session id or "manual" for now; structured for future provider users
  notes TEXT
  ```
- Add `CREATE INDEX idx_employees_employer ON employees(employer)` for future multi-tenant filtering.
- No column-migration entries needed for first creation; the `IF NOT EXISTS` form is sufficient.

**Test:** boot the API against a fresh SQLite file, confirm the `employees` table exists. Boot it again against an existing DB, confirm no errors.

### B2. Add `magic_link_tokens` table

File: [api/app/database.py](../../api/app/database.py)

- Append:
  ```
  id TEXT PRIMARY KEY                   -- internal id; not the token itself
  token_hash TEXT NOT NULL UNIQUE       -- SHA-256 of the URL token (never store plaintext)
  employee_id TEXT NOT NULL
  created_at TEXT NOT NULL
  expires_at TEXT NOT NULL
  revoked_at TEXT
  last_used_at TEXT
  use_count INTEGER NOT NULL DEFAULT 0
  FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
  ```
- Add `CREATE INDEX idx_magic_link_tokens_employee ON magic_link_tokens(employee_id, expires_at)`.

**Storing a hash, not the plaintext token, matters.** If the database leaks, tokens can't be reused. The plaintext lives only in the URL the provider copies.

**Test:** insert a token row, query by token_hash, confirm cascade delete when the employee row is deleted.

### B3. Add `sessions` table (replaces in-memory set)

File: [api/app/database.py](../../api/app/database.py)

The current `runtime.session_tokens: set[str]` ([api/app/runtime.py:17](../../api/app/runtime.py#L17)) is in-memory and clears on restart. For employee sessions tied to one-time magic-link consumption, persistence matters. Move both PIN and employee sessions into a table.

- Schema:
  ```
  token_hash TEXT PRIMARY KEY
  role TEXT NOT NULL              -- 'provider' or 'employee'
  subject_id TEXT                 -- employee_id when role='employee'; NULL for PIN
  created_at TEXT NOT NULL
  expires_at TEXT NOT NULL
  last_seen_at TEXT NOT NULL
  ```
- Update [api/app/runtime.py](../../api/app/runtime.py) to drop `session_tokens` (or keep as a transitional warm cache; recommended to just drop it).

**Test:** create session row, look up by hash, confirm expiration check filters it out.

### B4. Repository methods for employees, links, sessions

File: [api/app/repository.py](../../api/app/repository.py)

Add methods, mirroring the style already in the file:
- `create_employee(name, employer, email=None, notes=None) -> dict`
- `get_employee(employee_id) -> dict | None`
- `list_employees(employer=None) -> list[dict]`
- `create_magic_link_token(employee_id, plaintext_token, expires_at) -> dict` — hashes the token, never stores plaintext.
- `consume_magic_link_token(plaintext_token) -> dict | None` — looks up by hash, validates not expired/revoked, increments `use_count`, sets `last_used_at`, returns the employee row. Does NOT return the token row itself.
- `revoke_magic_link_token(token_id)` and `revoke_employee_links(employee_id)`.
- `create_session(role, subject_id, plaintext_token, expires_at) -> dict` — stores hash only.
- `get_session(plaintext_token) -> dict | None` — returns the session if valid (not expired), else None. Updates `last_seen_at`.
- `delete_session(plaintext_token)`.
- `purge_expired_sessions()` and `purge_expired_magic_link_tokens()` — called periodically (mirror `_purge_expired_assessments` pattern in [api/app/routes/assessments.py:136](../../api/app/routes/assessments.py#L136)).

**Test:** unit-test each method against a temp SQLite DB, especially the hash-lookup paths and expiration filtering.

### B5. New auth utilities module

New file: `api/app/auth_tokens.py`

- `generate_token() -> str` — `secrets.token_urlsafe(32)` (44 chars, URL-safe).
- `hash_token(plaintext: str) -> str` — `hashlib.sha256(plaintext.encode()).hexdigest()`.
- `compare_tokens(plaintext: str, stored_hash: str) -> bool` — `hmac.compare_digest`.

Keep this tiny and dependency-free. It's the only place that knows the hashing strategy.

### B6. Refactor existing PIN auth onto the new sessions table

File: [api/app/routes/auth.py](../../api/app/routes/auth.py)

The current PIN auth issues a token and adds it to `runtime.session_tokens`. Refactor:
- `POST /api/auth` (PIN) → on success, generate token, call `repository.create_session(role='provider', subject_id=None, plaintext_token=token, expires_at=now+12h)`. Set the same `hma_session` cookie.
- `GET /api/auth` → look up the cookie's plaintext token via `repository.get_session`. Return `auth_required` + `authenticated`. (Optionally include `role` so the frontend can branch.)
- `DELETE /api/auth` → `repository.delete_session(token)` and clear cookie.

Leave the cookie name `hma_session` and behavior identical from the client's perspective. The migration is internal.

**Test:** existing auth tests in `api/tests` should still pass with no changes to test code. If they do, refactor is clean.

### B7. New employee session endpoints

File: new `api/app/routes/self_session.py`

- `POST /api/self/session` — body `{"token": "<plaintext>"}`.
  - Calls `repository.consume_magic_link_token(plaintext)`. If valid, generate a *separate* session token, call `repository.create_session(role='employee', subject_id=employee_id, plaintext_token=session_token, expires_at=now+12h)`, set a NEW cookie `hma_employee_session`.
  - Two cookies (`hma_session` for provider, `hma_employee_session` for employee) keep the roles cleanly separated. Prevents accidental privilege bleed if a single device is used by both.
  - Return `{ok: true, employee: {id, name, employer}}`.
- `GET /api/self/me` — reads `hma_employee_session` cookie, looks up session, returns the employee row + the linked assessment id (null in Phase 1; Phase 2 will populate).
- `DELETE /api/self/session` — clears the employee cookie and deletes the session row.

Register this router in [api/app/main.py](../../api/app/main.py).

### B8. Provider endpoints to manage employees and links

File: new `api/app/routes/provider.py`

- `POST /api/provider/employees` — body `{name, employer, email?, notes?}`. PIN-protected. Returns the new employee row.
- `GET /api/provider/employees` — PIN-protected. Returns list, sortable by created_at desc. Optional `employer` query param.
- `POST /api/provider/employees/{id}/magic-link` — PIN-protected. Generates a token, stores hash, returns:
  ```
  {
    "url": "https://<host>/self/start/<plaintext_token>",
    "expires_at": "<iso>"
  }
  ```
  Plaintext token is returned ONCE here. Subsequent GETs of the employee never include it.
- `POST /api/provider/employees/{id}/revoke-links` — revokes all unexpired tokens for the employee. Useful for "regenerate."

Register the router in [api/app/main.py](../../api/app/main.py).

**The base URL for the magic link:** read from a new env var `PUBLIC_BASE_URL` (default `http://localhost:5181` for dev). Add to [api/app/settings.py](../../api/app/settings.py).

### B9. Replace `PinAuthMiddleware` with role-aware middleware

File: [api/app/middleware/pin_auth.py](../../api/app/middleware/pin_auth.py)

Rename to `auth.py` (or add alongside). Logic:
- Skip non-API paths (unchanged).
- `/api/health`, `/api/auth`, `/api/self/session` → no auth required.
- `/api/self/*` (other than the above) → require `hma_employee_session` cookie that resolves to a session with role='employee'. Attach `request.state.employee_id` from the session.
- All other `/api/*` → require `hma_session` cookie that resolves to a session with role='provider' (or no PIN configured).
- On mismatch, 401 JSON response (matches current behavior).

**Test:** integration test that hits `/api/provider/employees` with only an employee cookie returns 401. And vice versa.

### B10. Audit-event types

File: [api/app/repository.py](../../api/app/repository.py) — uses an existing `log_audit_event` helper.

Add new event types fired from the new endpoints:
- `employee_create`
- `magic_link_issue` (metadata: employee_id, expires_at, NEVER the token plaintext or hash)
- `magic_link_consume` (metadata: employee_id)
- `magic_link_revoke`
- `provider_session_start` and `employee_session_start`

Mirrors the existing pattern (`assessment_create`, `provider_review`, etc.). These give you a full audit trail in the existing `audit_events` table.

### B11. Settings additions

File: [api/app/settings.py](../../api/app/settings.py)

- `magic_link_lifetime_days: int` — default 7, env `MAGIC_LINK_LIFETIME_DAYS`.
- `employee_session_hours: int` — default 12, env `EMPLOYEE_SESSION_HOURS`.
- `public_base_url: str` — default `"http://localhost:5181"`, env `PUBLIC_BASE_URL`.

---

## Frontend tasks

All paths relative to repo root.

### F1. Auth-status response includes role

Update `getAuthStatus` in [web/src/lib/api.ts](../../web/src/lib/) (file likely there — confirm) to expect optional `role` field.

In [web/src/App.tsx](../../web/src/App.tsx), branch on role to decide which UI tree to render. Provider role → existing flow. No-role / not-authenticated → existing PIN gate.

### F2. New `/self/start/:token` route

New page: `web/src/pages/SelfStartPage.tsx`.

- On mount, POST `{token}` to `/api/self/session`.
- On success, navigate to `/self/home` with the employee record stashed in route state.
- On failure (expired / revoked / unknown), show a clear "this link is no longer valid — contact your provider for a new one" page.

Register in `App.tsx` routes, *outside* the existing `AppShell` (the employee tree is a different shell).

### F3. New `AppShellSelf` component

New file: `web/src/components/AppShellSelf.tsx`. Parallel to the existing [AppShell](../../web/src/components/AppShell.tsx). Different header, no provider nav. Phase 2 fills the body.

### F4. Stub `/self/home` page

New file: `web/src/pages/SelfHomePage.tsx`. Phase 1 just shows "Hi, {name}. Your assessment will be available here." This proves the auth round-trip works end-to-end without yet building the assessment UI.

### F5. Provider UI: "Issue assessment link" card

Add to [web/src/pages/HomePage.tsx](../../web/src/pages/HomePage.tsx) (or [HistoryPage.tsx](../../web/src/pages/HistoryPage.tsx) — pick whichever is more visited).

- Form: name, employer, optional email.
- Submits to `POST /api/provider/employees`, then `POST /api/provider/employees/{id}/magic-link`.
- Displays the resulting URL with a one-click copy button. Copy-to-clipboard via `navigator.clipboard.writeText`.
- Shows "expires on {date}".

Phase 1 doesn't need an employee list view; that's nice-to-have for Phase 3.

### F6. Cookie path / SameSite

Confirm both `hma_session` and `hma_employee_session` are set with:
- `httponly=True`
- `samesite="lax"` (matches existing)
- `secure=True` when scheme is HTTPS (matches existing pattern in [api/app/routes/auth.py:36](../../api/app/routes/auth.py#L36))

Magic-link URL clicks come in via GET → `samesite=lax` allows the cookie to be set on the redirected POST.

---

## Tests to add

Following the existing pytest layout in [api/tests](../../api/tests).

- `test_auth_tokens.py` — generate/hash/compare round-trip; constant-time compare.
- `test_employees_repository.py` — create, list, filter by employer, cascade delete via tokens.
- `test_magic_links.py` — issue, consume valid, consume expired (rejected), consume revoked (rejected), consume after window (rejected).
- `test_sessions_repository.py` — create, look up, expire, delete.
- `test_provider_routes.py` — create employee + issue link round-trip, requires PIN, returns URL once.
- `test_self_session_routes.py` — POST with valid token issues employee cookie; POST with expired token returns 401; GET /api/self/me requires employee cookie.
- `test_role_isolation.py` — provider cookie cannot hit `/api/self/*`; employee cookie cannot hit `/api/provider/*`.

Frontend tests:
- `SelfStartPage.test.tsx` — happy path renders home; failure shows error state.
- Existing test suites for [App.test.tsx](../../web/src/App.test.tsx), [AssessmentSessionPage.test.tsx](../../web/src/pages/AssessmentSessionPage.test.tsx), etc. should pass unchanged.

---

## Suggested order of attack

If you do these in order, each step leaves the app in a working state.

1. **B1 + B2 + B3** (schema): all three table additions land together, with tests. App still boots and behaves identically.
2. **B5** (auth_tokens utility) + **B4** (repository methods): pure unit-tested code, no routes wired yet.
3. **B6** (refactor existing PIN auth onto sessions table): biggest risk to existing behavior. Land alone, run the existing test suite, confirm green.
4. **B11** (settings) + **B7** + **B8** (new routes): wire the actual endpoints. Test via curl/Postman.
5. **B9** (middleware role-awareness): now that role-tagged sessions exist, enforce them.
6. **B10** (audit event types): retrofit log calls into the new endpoints.
7. **F2** + **F3** + **F4** (frontend self routes): minimum to prove employee auth round-trips end-to-end.
8. **F1** (auth-status role): update App.tsx so role is visible to the frontend.
9. **F5** (provider issue-link UI): the actual usable surface for you.
10. **F6** (cookie/security audit pass): final review before declaring Phase 1 done.

---

## Acceptance criteria for "Phase 1 done"

- [ ] You, as a provider with PIN, can open the existing app, fill in name + employer, click "Issue link," and copy a URL.
- [ ] Pasting that URL in a fresh browser (no cookies) lands on a "Hi, {name}" page authenticated as the employee.
- [ ] Hitting any provider API endpoint with only an employee cookie returns 401, and vice versa.
- [ ] The existing in-clinic flow (mode select → assessment → results) works unchanged for a PIN-authed provider.
- [ ] Magic links expire after the configured window. Expired/revoked links show a clear error page.
- [ ] Existing pytest + frontend test suites pass with no regressions.
- [ ] Audit events for `employee_create`, `magic_link_issue`, `magic_link_consume`, and session starts appear in `audit_events` after a typical flow.

---

## Risks / things to keep an eye on while building

1. **Don't store plaintext tokens anywhere.** Hash on insert, hash on lookup, compare hashes. The token only ever exists as plaintext in (a) the URL during issuance, (b) the URL during consumption, and (c) the cookie value during the active session.
2. **Token URL length.** `secrets.token_urlsafe(32)` is 43 chars. Plus `/self/start/` prefix and host = comfortable, but if you ever add SMS delivery in Phase 5, watch the SMS character count.
3. **Cookie collision.** If you test as both provider and employee in the same browser, both cookies coexist. The middleware must check the right cookie for the right route prefix; do not fall back from one to the other.
4. **Mixed-mode browsers.** If a provider tests an employee link in the same browser they were just PIN-authed in, they'll have both cookies. That's correct, but document it so a future debugger doesn't get confused.
5. **Restart purges in-memory state today.** Once sessions move to the table, restart no longer kicks anyone out — that's a behavior change. Mention it in the commit/PR description.
