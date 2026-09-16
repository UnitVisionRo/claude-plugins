// Destination: gui/app/utils/cookies.ts

/**
 * Cookie names the backend sets (`api/lib/security.py`). Only the refresh cookie's presence is
 * ever read here, and only on the server: these are httpOnly, so the browser cannot see them
 * and nothing in the frontend should try to.
 */
export const REFRESH_TOKEN_COOKIE = 'refresh_token'
