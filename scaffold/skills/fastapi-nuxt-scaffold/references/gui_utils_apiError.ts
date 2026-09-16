// Destination: gui/app/utils/apiError.ts

/**
 * Turn whatever the generated client threw into one line a user can read.
 *
 * The backend answers with FastAPI's two shapes: `{detail: "..."}` for a deliberate
 * HTTPException, and `{detail: [{loc, msg, ...}]}` for a 422 from schema validation. Showing
 * the raw object (or a bare "Request failed") wastes messages the API went to the trouble of
 * writing -- the password-complexity rule, for instance, exists only server-side and reaches
 * the user through here.
 */
export function apiErrorMessage(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
    const detail = (error as { data?: { detail?: unknown } })?.data?.detail

    if (typeof detail === 'string') {
        return detail
    }

    if (Array.isArray(detail)) {
        const messages = detail
            .map(item => (item as { msg?: string })?.msg)
            .filter((message): message is string => Boolean(message))
            .map(message => message.replace(/^Value error, /, ''))
        if (messages.length) {
            return messages.join('. ')
        }
    }

    return fallback
}
