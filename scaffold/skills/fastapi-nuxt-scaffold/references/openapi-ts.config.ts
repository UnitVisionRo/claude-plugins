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
    plugins: ['@hey-api/typescript', '@hey-api/sdk', '@hey-api/client-nuxt', 'valibot'],
})
