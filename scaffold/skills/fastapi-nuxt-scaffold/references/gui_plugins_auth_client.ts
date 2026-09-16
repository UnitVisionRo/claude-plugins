// Destination: gui/app/plugins/auth.client.ts
import { isPublicPath } from '~/utils/routeAccess'
import { useAuthStore } from '~/stores/auth'

/**
 * Finish the authentication check that SSR could not.
 *
 * When the server met an expired access token it deliberately reached no verdict, because
 * renewing one there would revoke the browser's refresh token without being able to hand back
 * the replacement (`stores/auth.ts` explains why). It rendered the page shell instead and left
 * `loaded` false.
 *
 * This runs on hydration, where `POST /auth/refresh` works properly, and settles it. A plugin
 * rather than more middleware: route middleware does not re-run in the browser for the page
 * the server already rendered, so for that first load this is the only thing standing between
 * a signed-out visitor and a protected page.
 */
export default defineNuxtPlugin(async () => {
    const auth = useAuthStore()
    if (auth.loaded) {
        return
    }

    await auth.resolve()

    const route = useRoute()
    if (!auth.isAuthenticated && !isPublicPath(route.path)) {
        await navigateTo({ path: '/login', query: route.fullPath === '/' ? undefined : { redirect: route.fullPath } })
    }
})
