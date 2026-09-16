// Destination: gui/app/middleware/auth.global.ts
import { REFRESH_TOKEN_COOKIE } from '~/utils/cookies'
import { isPublicPath } from '~/utils/routeAccess'
import { useAuthStore } from '~/stores/auth'

export default defineNuxtRouteMiddleware(async (to) => {
    const auth = useAuthStore()

    // Asked once per page load. During SSR the visitor's own cookies are forwarded explicitly
    // (`useRequestHeaders` is request-scoped; the API client is not -- see plugins/api.ts).
    if (!auth.loaded) {
        await auth.resolve(
            import.meta.server ? useRequestHeaders(['cookie']) : undefined,
            import.meta.server ? Boolean(useCookie(REFRESH_TOKEN_COOKIE).value) : false,
        )
    }

    // Still no verdict: the access token has expired and only the browser can renew it (see
    // `stores/auth.ts`). Render the shell -- the server has no session, so there is nothing
    // private in it -- and let `plugins/auth.client.ts` settle this after hydration.
    if (!auth.loaded) {
        return
    }

    if (isPublicPath(to.path)) {
        // Someone already signed in has no business on the login page.
        if (to.path === '/login' && auth.isAuthenticated) {
            return navigateTo('/')
        }
        return
    }

    if (!auth.isAuthenticated) {
        // `redirect` brings them back where they were headed once they sign in.
        return navigateTo({ path: '/login', query: to.fullPath === '/' ? undefined : { redirect: to.fullPath } })
    }

    if (to.meta.requiresAdmin && !auth.isAdmin) {
        return navigateTo('/')
    }
})
