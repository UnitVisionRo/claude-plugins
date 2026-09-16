// Destination: gui/app/stores/auth.ts
import { defineStore } from 'pinia'

import {
    getMe,
    login as loginRequest,
    logout as logoutRequest,
    refreshSession,
    verifyTwoFactor,
} from '~/generated/rest'
import type { CurrentUserResult, TwoFactorMethod } from '~/generated/rest'

/**
 * Who is signed in, and the two-step login that gets them there.
 *
 * The store holds no token: the session is an httpOnly cookie the browser attaches on its
 * own, which is the whole point of that design -- there is nothing here for an XSS to steal.
 * `currentUser` is a cache of `GET /auth/me`, and the server stays the authority.
 */
export const useAuthStore = defineStore('auth', () => {
    const currentUser = ref<CurrentUserResult | null>(null)
    // Distinguishes "not signed in" from "no verdict yet", so the route guard doesn't bounce
    // a navigation to /login while the answer is still in flight -- or, during SSR, while the
    // answer can only be reached in the browser (see `resolve`).
    const loaded = ref(false)

    // Set between a correct password and a correct code. No session exists in this window.
    const pendingTwoFactor = ref<TwoFactorMethod | null>(null)

    const isAuthenticated = computed(() => currentUser.value !== null)
    const isAdmin = computed(() => currentUser.value?.role === 'ADMIN')

    /**
     * Work out who the visitor is, renewing an expired access token if that is all that is wrong.
     *
     * `requestHeaders` carries the visitor's `Cookie` header when this runs during SSR, where
     * there is no browser to attach it. It is passed per call rather than configured on the
     * client, because that client is shared by every request the server handles -- see
     * `plugins/api.ts`.
     *
     * The access token expires long before the session does, so a 401 usually just means
     * "spend the refresh cookie". That renewal is **only ever attempted in the browser**, and
     * that is not an optimisation: `POST /auth/refresh` ROTATES the refresh token, returning
     * the replacement in a `Set-Cookie`. Run during SSR, that header lands on the Nuxt
     * server's own fetch response and never reaches the browser -- leaving the browser holding
     * a token the backend has already revoked, which logs the user out *harder* than doing
     * nothing. So when SSR meets a 401 and `canRefresh` says a refresh cookie exists, it
     * records no verdict at all (`loaded` stays false) and `plugins/auth.client.ts` finishes
     * the job after hydration.
     */
    async function resolve(requestHeaders?: Record<string, string>, canRefresh = false): Promise<void> {
        try {
            currentUser.value = await getMe({ headers: requestHeaders })
            loaded.value = true
            return
        } catch {
            // A 401 here is the normal answer for an anonymous visitor, not an error.
            currentUser.value = null
        }

        if (import.meta.server) {
            loaded.value = !canRefresh
            return
        }

        try {
            await refreshSession()
            currentUser.value = await getMe()
        } catch {
            currentUser.value = null
        } finally {
            loaded.value = true
        }
    }

    /** Returns true when the session is live; false means a code is still needed. */
    async function signIn(username: string, password: string): Promise<boolean> {
        const result = await loginRequest({ body: { username, password } })
        if (result.twofaRequired) {
            pendingTwoFactor.value = result.twofaMethod ?? null
            return false
        }
        pendingTwoFactor.value = null
        await resolve()
        return true
    }

    async function submitTwoFactorCode(code: string): Promise<void> {
        await verifyTwoFactor({ body: { code } })
        pendingTwoFactor.value = null
        await resolve()
    }

    function cancelTwoFactor(): void {
        pendingTwoFactor.value = null
    }

    async function signOut(): Promise<void> {
        try {
            await logoutRequest()
        } finally {
            // Drop the local copy even if the call failed -- the cookie may already be gone,
            // and leaving a stale user on screen is worse than an extra 401 later.
            currentUser.value = null
            pendingTwoFactor.value = null
        }
    }

    return {
        cancelTwoFactor,
        currentUser,
        isAdmin,
        isAuthenticated,
        loaded,
        pendingTwoFactor,
        resolve,
        signIn,
        signOut,
        submitTwoFactorCode,
    }
})
