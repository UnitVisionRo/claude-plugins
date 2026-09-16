# CLAUDE.md

## What this is
__APP_NAME__ -- <one-line description of the app's purpose>. Layout: `api/` (Python backend)
· `gui/` (Nuxt frontend).

## Front <-> API contract
FastAPI's generated OpenAPI schema is the source of the contract between `gui/` and `api/`.
Each API surface is its own FastAPI sub-app with its own OpenAPI schema (`/rest/openapi.json`,
`/api/openapi.json`). The frontend generates its TS types, Valibot schemas, and a typed Nuxt
client from the `/rest` schema via `@hey-api/openapi-ts` -- no hand-maintained API types, no drift.

## API surfaces (grouped by consumer)
- **`/rest`** -- the browser-facing console (`gui/`). CORS locked to the frontend origin(s),
  with credentials allowed. Authenticated by an httpOnly session cookie (JWT) with a rotating
  refresh token, optionally behind two-factor auth; the dependency is in
  `api/routers/rest/deps.py`. Access is invite-only -- there is no public sign-up.
- **`/api`** -- server-to-server integrations. CORS open (a browser is never the caller);
  guarded by an API-key header instead. The placeholder check is a static key list in
  settings -- replace with a scoped/rotatable DB-backed model when you need real key management.

Never cross the streams: the GUI only calls `/rest`; an integration only calls `/api`. If a
route is genuinely needed on both surfaces, implement it separately on each with its own auth
dependency and OpenAPI schema, sharing logic via a `services/` function.

## Authentication
The session is an httpOnly cookie, never a token in JavaScript. Endpoints depend on
`routers/rest/deps.py`'s `CurrentUser` / `AdminUser`; the frontend's route middleware is a
convenience for the user, never the boundary. The access token names the session that issued
it, and that dependency joins against a live `user_sessions` row -- so revoking a session,
logging out, or resetting a password takes effect on the next request rather than whenever the
token would have expired. Secrets are stored in the weakest form that
still works: Argon2 for passwords, keyed HMAC fingerprints for refresh and invite tokens,
and reversible Fernet encryption only for TOTP secrets, which must be readable to verify a
code.

## Coding style
- Indentation: 4 spaces. Line length: 120 characters.
- Naming: camelCase for variables, table columns, and JSON keys; snake_case for Python
  functions and table names; PascalCase for classes and types; SCREAMING_SNAKE_CASE for
  constants and enum keys.

## Timestamps & timezones
- All timestamp columns: `timestamptz`, never `timestamp`.
- Python: only `datetime.now(timezone.utc)` (aware). Never `datetime.now()` or `datetime.utcnow()`.
- Browser -> backend: serialize with `date.toISOString()`. Never send naive datetime strings.

## Coding principles
Apply DRY/SOLID where they materially improve the code -- not as a reflex. Before writing an
inline function, check whether a similar capability already exists in `api/lib`,
`api/services`, `gui/app/composables`, or `gui/app/utils`. Never extract a reusable
function/service for a single call site -- do the work inline there instead.

## Spec and plan files locations
- **Functional spec**: `docs/spec/<feature name>/` -> the source of truth for the platform's behavior
- **Plans**: `docs/plans/<feature name>/<phase name>?/` -> the implementation plan for a feature, derived from the spec. Kind of like a "compiler" for the spec: it translates the spec into a concrete, actionable plan for implementation. Each plan is **phase-specific** and may be broken into multiple chunks, each with its own independently testable deliverable.

## Spec-grounded features

When building a feature grounded in the functional spec, add a code comment referencing the relevant spec section (e.g. `# spec §06 R6.3` or `// spec §06 R6.3`) — reference only, never the full spec text. This maintains traceability between code and the functional spec.
