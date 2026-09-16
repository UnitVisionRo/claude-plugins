// Destination: gui/app/plugins/api.ts
import { client } from '~/generated/rest/client.gen'

/**
 * Point the generated client at the backend and let it carry the session cookie.
 *
 * `credentials: 'include'` is what makes the session work at all. The session is an httpOnly
 * cookie on a DIFFERENT origin (`:3000` -> `:8000`), and `fetch` sends no cookies cross-origin
 * without it -- every request would simply come back 401 with nothing in the console to say
 * why. The backend half of the same deal is `allow_credentials=True` plus an exact origin in
 * `REST_CORS_ORIGINS`; a wildcard origin cannot carry credentials.
 *
 * What is deliberately NOT configured here: the incoming request's `Cookie` header for SSR.
 * `client` is a module-level singleton, so it is shared by every request the Nuxt server
 * handles. Writing one visitor's cookie into it leaks that session to whoever is rendered
 * next -- a signed-out visitor gets served the previous user's pages. Server-side requests
 * pass their headers per call instead; `stores/auth.ts` and `middleware/auth.global.ts` show
 * the shape.
 */
export default defineNuxtPlugin(() => {
    const { apiBaseUrl } = useRuntimeConfig().public

    client.setConfig({
        baseUrl: apiBaseUrl,
        credentials: 'include',
    })
})
