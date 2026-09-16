# gui/ -- frontend

Scoped guidance for the frontend. Application-wide contracts live in the root `../CLAUDE.md`.

## Stack
- **Framework:** Nuxt 4 (Vite).
- **Component framework:** Vuetify 4, SSR-enabled via `vite-plugin-vuetify`. Use raw Vuetify
  components (`VTextField`/`VSelect`/`VDataTable`/`VBtn` etc.) configured via global `defaults`
  in `app/plugins/vuetify.ts` rather than hand-rolled CSS wrappers.
- **Styling:** UnoCSS (`presetWind4` + `presetAttributify` + `presetIcons`).
- **Validation:** Valibot (Standard Schema -> Vuetify `useRules`).
- **State:** Pinia.
- **API codegen:** `@hey-api/openapi-ts` + the Valibot plugin -- typed client, TS types and
  Valibot schemas generated from the backend's `/rest` OpenAPI schema. `/api` is never
  consumed by the frontend (server-to-server integrations generate their own client). The
  client is `@hey-api/client-fetch`, configured with `throwOnError` + `responseStyle: 'data'`,
  so every SDK call resolves to the response body and throws on a non-2xx.
- **Auth:** httpOnly cookie session; `stores/auth.ts` + `middleware/auth.global.ts`. The
  middleware denies by default -- a new page is protected unless its path is listed public.

## Conventions
- **Functions are camelCase, not snake_case** -- the root's snake_case rule scopes to Python;
  frontend TS/JS follows Vue idiom (composables, utilities, event handlers all camelCase).
- **Vuetify-first.** Reach for native Vuetify components/composables (`useTheme`,
  `useDisplay`, `VForm`) before writing custom logic.
- **The API layer is generated.** Never hand-write API types or a bespoke fetcher. Regenerate
  after a backend schema change: `npm run openapi` (curls the live `/rest/openapi.json` into a
  committed snapshot, then runs `openapi-ts` against that snapshot -- deterministic, diff-reviewable).
- **Console calls `/rest` only.** Never call `/api` from the browser -- that surface is for
  server-to-server integrations.
- **Never configure per-visitor state on the generated API client.** `client` is a
  module-level singleton shared by every request the Nuxt server renders, so anything
  request-specific written into it -- above all the `Cookie` header -- leaks between
  visitors. Pass such things per call; `middleware/auth.global.ts` shows the pattern.
- **Route guards are UX, not security.** The API enforces access (`routers/rest/deps.py`);
  the middleware only spares the user a screen of failed requests.
- **Server-side validation is authoritative.** Form rules here are for fast feedback; rules
  that exist only in `schemas/rest.py` (password complexity) reach the user through
  `utils/apiError.ts` rather than being duplicated and left to drift.

## Running & verifying
```bash
npm install
npm run dev
npm run typecheck
npm run lint
npm run openapi   # requires the backend running locally on the port in package.json's script
```
