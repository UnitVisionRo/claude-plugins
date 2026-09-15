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
- **API codegen:** `@hey-api/openapi-ts` + the Valibot plugin -- typed Nuxt client, TS types,
  and Valibot schemas generated from the backend's `/rest` OpenAPI schema. `/api` is never
  consumed by the frontend (server-to-server integrations generate their own client).

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

## Running & verifying
```bash
npm install
npm run dev
npm run typecheck
npm run lint
npm run openapi   # requires the backend running locally on the port in package.json's script
```
