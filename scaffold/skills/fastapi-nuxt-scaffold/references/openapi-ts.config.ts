import { defineConfig } from '@hey-api/openapi-ts'

// Codegen for the /rest surface only -- the frontend never calls the server-to-server
// integrations surface directly (an integrating system generates its own client from
// /api's schema). Generated from a COMMITTED snapshot (refreshed by `npm run openapi`),
// not a live URL, so regeneration is deterministic and diff-reviewable.
export default defineConfig({
    input: './app/generated/rest/openapi.snapshot.json',
    output: {
        path: './app/generated/rest',
        // clean:false preserves the committed openapi.snapshot.json file in the output
        // folder (openapi-ts cleans the output dir by default, which would delete it).
        clean: false,
    },
    plugins: [
        '@hey-api/typescript',
        // `client-fetch`, not `client-nuxt`. The Nuxt client exists to return `useFetch` /
        // `useAsyncData` composables, which this app does not use -- every call here is
        // imperative, from a store action or an event handler. It also emits SDK code that
        // does not typecheck under `nuxt typecheck` (it passes its `DefaultT` generic into
        // `RequestResult`'s error slot), so adopting it would mean shipping a scaffold whose
        // own typecheck gate is red. Cookies and SSR header forwarding work the same either
        // way -- see app/plugins/api.ts.
        //
        // `throwOnError` + `responseStyle: 'data'` make each SDK function resolve to the
        // response body and throw on a non-2xx, so call sites read like ordinary async
        // functions instead of unwrapping `{ data, error }` every time. Both must be set on
        // the client AND the sdk plugin: one shapes the runtime, the other the types.
        { name: '@hey-api/client-fetch', throwOnError: true, responseStyle: 'data' },
        { name: '@hey-api/sdk', throwOnError: true, responseStyle: 'data' },
        'valibot',
    ],
})
