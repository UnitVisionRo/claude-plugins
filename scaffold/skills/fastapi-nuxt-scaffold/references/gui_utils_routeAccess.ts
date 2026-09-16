// Destination: gui/app/utils/routeAccess.ts

/**
 * Which paths are reachable without a session.
 *
 * Deny by default: a new page is protected unless it is listed here, so forgetting to add a
 * rule locks a page down rather than exposing it.
 *
 * Shared by `middleware/auth.global.ts` and `plugins/auth.client.ts` because both have to
 * reach the same verdict -- route middleware does not re-run in the browser for the page the
 * server already rendered, so the plugin is what guards that first load.
 *
 * This is a convenience, not a security boundary: anyone can skip it with curl. Access control
 * is enforced by the API (`routers/rest/deps.py`); this only spares the user a screen full of
 * failed requests.
 */
const PUBLIC_PATHS = ['/login']
const PUBLIC_PREFIXES = ['/signup/', '/password-reset/']

export function isPublicPath(path: string): boolean {
    return PUBLIC_PATHS.includes(path) || PUBLIC_PREFIXES.some(prefix => path.startsWith(prefix))
}
