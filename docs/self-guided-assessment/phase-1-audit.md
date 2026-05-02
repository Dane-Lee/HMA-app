# Phase 1 — F6 Security Audit

Final review pass before declaring Phase 1 done. Scope: every cookie write/read across the new auth surface, plus the path-routing logic in the role-aware middleware.

## Cookies

Two cookies, both with the same posture.

### `hma_session` (provider PIN session)

Set in [api/app/routes/auth.py:57-64](../../api/app/routes/auth.py#L57):
- `httponly=True` — no JavaScript access.
- `samesite="lax"` — survives top-level GET navigations, blocked on cross-site POSTs.
- `secure=is_secure` — TLS-only in production (HTTP fine in localhost dev).
- `max_age = PROVIDER_SESSION_HOURS * 60 * 60` (12 hours) — matches the DB session row's `expires_at`.
- `path` and `domain` left at defaults (`/` and current host).

Read in middleware ([api/app/middleware/pin_auth.py:50](../../api/app/middleware/pin_auth.py#L50)) and `auth_status` / `logout` handlers. Deleted via `response.delete_cookie("hma_session")` on logout.

### `hma_employee_session` (magic-link session)

Set in [api/app/routes/self_session.py:65-72](../../api/app/routes/self_session.py#L65) with identical posture, lifetime driven by `settings.employee_session_hours` (default 12).

Read in middleware ([api/app/middleware/pin_auth.py:39](../../api/app/middleware/pin_auth.py#L39)) and `end_session` handler. Deleted on `DELETE /api/self/session`.

### Cross-checks

- **Distinct names per role.** No collision; a single browser can hold both cookies side-by-side without confusion.
- **Role check on every read.** Middleware verifies `session["role"] == "provider"` for `hma_session` and `== "employee"` for `hma_employee_session`. An attacker who copies their employee token into `hma_session` still fails the role check. This is the defense-in-depth that makes the two-cookie split worthwhile.
- **Both cookies default `path=/`**, so a request to any URL on the host carries both cookies if both are set. The middleware never confuses them because it always reads the cookie name matching the route prefix.

## Token plaintext flow

Plaintext tokens generated via `auth_tokens.generate_token` (32 bytes, URL-safe = ~256 bits of entropy). Plaintext exists only in:

1. The HTTP response body that issues a token (the magic-link URL response in `provider.py`, the cookie value on the auth-success responses).
2. The browser cookie that the client returns on each request.
3. Internal calls to `hash_token()` for storage and lookup.

Verified there is no plaintext or hash in:
- Audit-event metadata. Reviewed [api/app/routes/auth.py:55](../../api/app/routes/auth.py#L55), [api/app/routes/self_session.py:48,60](../../api/app/routes/self_session.py#L48), [api/app/routes/provider.py:61,90,111](../../api/app/routes/provider.py#L61). Metadata is `employee_id` / `employer` / `expires_at` / `revoked_count` only.
- Server logs. The only `logger.debug` calls are in `assessments.py` for temp video paths — unrelated to auth tokens.
- Response bodies other than the one-time issuance (cookie POST and magic-link issue endpoint).

## Middleware path routing

[api/app/middleware/pin_auth.py](../../api/app/middleware/pin_auth.py)

Order:
1. Non-API path → pass through (SPA shell, static assets).
2. `/api/health`, `/api/auth`, or `/api/self/session` → pass through (always-public).
3. `/api/self/*` → require valid `hma_employee_session` with `role='employee'`. Sets `request.state.employee_id`.
4. Other `/api/*` → require valid `hma_session` with `role='provider'` (skipped only when PIN is unset, i.e. dev mode).

Edge cases verified:
- `/api/self` (no trailing slash) does not match `path.startswith("/api/self/")` and would fall through to the provider gate. No such route is registered, so it 404s after auth. Documented as a convention: every self route lives under `/api/self/`.
- `DELETE /api/self/session` (always-public) safely no-ops when the cookie is missing or invalid. CSRF-safe via SameSite-Lax: cross-site DELETEs do not carry the cookie.
- `POST /api/self/session` (always-public) is the magic-link consumption entry point. The token in the body is the credential; without it, the route returns 401 from its own validation, not the middleware.

## Frontend audit

- All `fetch` calls in [web/src/lib/api.ts](../../web/src/lib/api.ts) use `credentials: "include"` so cookies round-trip on same-origin XHR/fetch.
- [SelfStartPage](../../web/src/pages/SelfStartPage.tsx) reads the magic-link token via `useParams`, POSTs it in the JSON body to `/api/self/session`, and on success calls `navigate("/self/home", { replace: true })` — replacing the URL-with-token in browser history rather than pushing a new entry.
- The token is never written to React state, never persisted to `localStorage`, never logged.

## Risk acknowledgments (non-blocking)

These are accepted trade-offs from the decisions doc, surfaced again here so they aren't forgotten in deployment.

1. **Multi-use magic link within 7-day window.** Anyone with the link can consume it any number of times until expiry. Mitigation: 256-bit token entropy, 7-day cap, `revoke_employee_magic_links` available to the provider, audit log of every consume. Per decision Q11 of the critique.
2. **Browser URL bar exposure during consumption.** The token sits in the URL bar for the brief moment between clicking the link and `replace`-navigating to `/self/home`. Shoulder-surfers and screenshot tooling could capture it. Same risk class as any link-based auth.
3. **Production CORS hardening.** [api/app/main.py:32-39](../../api/app/main.py#L32) currently allows `localhost:*` origins for dev. Production deploy needs to restrict to the actual host. Deployment-time concern, not code.
4. **No rate limiting on `POST /api/self/session`.** An attacker could brute-force tokens, but 256-bit entropy makes this computationally infeasible. Rate limiting is a reasonable defense-in-depth addition for Phase 5 but not required for Phase 1.
5. **In-memory session restart behavior changed.** Sessions now persist across restart (B6 acceptance criterion). Documented behavior change — flag in eventual PR description.

## Acceptance criteria check

From [phase-1-breakdown.md](phase-1-breakdown.md):

- [x] Provider with PIN can issue an assessment link via the home page card.
- [x] Pasting the URL in a fresh browser lands on a "Hi, {name}" page authenticated as the employee.
- [x] Provider API endpoints return 401 with only an employee cookie, and vice versa (covered by [test_role_isolation.py](../../api/tests/test_role_isolation.py)).
- [x] Existing in-clinic flow works unchanged (covered by the original 12 backend tests + 14 frontend tests).
- [x] Magic links expire after the configured window; expired/revoked links show a clear error (covered by [test_provider_routes.py::test_revoke_links_invalidates_existing](../../api/tests/test_provider_routes.py)).
- [x] Existing pytest + frontend tests pass with no regressions. Final tally: 63 backend + 18 frontend.
- [x] Audit events fire for `employee_create`, `magic_link_issue`, `magic_link_consume`, `magic_link_revoke`, `provider_session_start`, and `employee_session_start`.

## Verdict

Phase 1 ships. No security issues found that would block.
