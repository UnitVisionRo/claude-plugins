// Destination: gui/app/utils/validation.ts
import * as v from 'valibot'

/**
 * Form validation, driven by the schemas generated from the backend.
 *
 * The rules themselves are NOT written here. `app/generated/rest/valibot.gen.ts` already
 * contains them, compiled from the OpenAPI schema that `api/schemas/rest.py` produces --
 * `v.regex(/^(?=.*[a-z]).../)` for a password, `v.minLength(3), v.maxLength(125)` for a
 * username, `v.email()` for an address. This module is only the adapter between those schemas
 * and Vuetify, plus the two checks a generated schema cannot express.
 *
 * Why an adapter at all: Vuetify's `ValidationRule` is
 * `string | boolean | ((value) => string | boolean) | ...` -- there is no Standard Schema
 * branch in Vuetify 4 and no `useRules` export, so a schema cannot be handed to `:rules`
 * directly. `ruleFrom` is that bridge and it is deliberately three lines.
 *
 * Keep it this way. The moment a rule is re-typed here it can drift from the server, and the
 * server is the one that actually decides.
 */

export type Rule = (value: unknown) => true | string

/** Adapt any valibot schema to a Vuetify rule. */
export function ruleFrom(schema: v.GenericSchema, message?: string): Rule {
    return (value) => {
        const result = v.safeParse(schema, value)
        return result.success ? true : (message ?? result.issues[0]!.message)
    }
}

/**
 * The rule for one field of a generated request schema.
 *
 *     :rules="[required(), fieldRule(vSignupRequest, 'username')]"
 *
 * `message` overrides valibot's wording, which for a regex is the pattern itself -- accurate
 * and useless to a human. See `MESSAGES` below.
 */
export function fieldRule<TEntries extends v.ObjectEntries>(
    schema: v.ObjectSchema<TEntries, undefined>,
    key: keyof TEntries & string,
    message?: string,
): Rule {
    return ruleFrom(schema.entries[key] as v.GenericSchema, message)
}

/**
 * Presence. Needed separately because a required string field generates as `v.string()`,
 * which happily accepts `''` -- "this key must be present" and "the user typed something" are
 * different questions, and only the first one survives the trip through JSON Schema.
 */
export function required(message = 'Required'): Rule {
    return value => (value !== null && value !== undefined && String(value).trim() !== '' ? true : message)
}

/**
 * Cross-field equality (password confirmation).
 *
 * The server checks this in a `model_validator`, which produces no JSON Schema, so it cannot
 * be generated. It is the one rule in the app deliberately stated twice.
 */
export function matches(getOther: () => unknown, message = 'Passwords do not match'): Rule {
    return value => (value === getOther() ? true : message)
}

/**
 * Human wording for rules whose generated message is a regular expression.
 *
 * The only thing that does not cross the wire. The backend carries the same sentence in its
 * `Field(description=...)`, so OpenAPI and the API docs agree with what is shown here; if you
 * change one, change the other. Everything else -- which characters, how many, what shape --
 * lives solely in `api/schemas/rest.py`.
 */
export const MESSAGES = {
    password: 'At least 8 characters, including a lowercase and an uppercase letter, a digit and a symbol',
    username: '3-125 characters: letters, digits, dot, dash or underscore',
    code: 'Enter the 6-digit code',
} as const

export type FieldIssues<T> = Partial<Record<keyof T, string>>

/**
 * Validate a whole payload before sending it.
 *
 * This replaces the hand-written "are all the boxes filled in" guard that submit handlers
 * used to carry: that guard restated the rules a third time, in boolean form, and could
 * silently fall out of step with both the field rules and the server.
 *
 * `abortPipeEarly` keeps one issue per field, which is what a form can display.
 */
export function validatePayload<TEntries extends v.ObjectEntries, TPayload>(
    schema: v.ObjectSchema<TEntries, undefined>,
    payload: TPayload,
): { ok: boolean, issues: FieldIssues<TPayload> } {
    const result = v.safeParse(schema, payload, { abortPipeEarly: true })
    if (result.success) {
        return { ok: true, issues: {} }
    }

    const issues: Record<string, string> = {}
    for (const issue of result.issues) {
        const key = issue.path?.[0]?.key
        if (typeof key === 'string' && !(key in issues)) {
            issues[key] = MESSAGES[key as keyof typeof MESSAGES] ?? issue.message
        }
    }
    return { ok: false, issues: issues as FieldIssues<TPayload> }
}
