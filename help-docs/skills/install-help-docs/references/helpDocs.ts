// Destination: <nuxtDir>/<srcDir>/utils/helpDocs.ts
import { helpDocLoaders, helpManifest } from '~/help/generated/manifest'
import type { HelpDocMeta } from '~/help/types'

// Utilities over the generated documentation. Used by the help page and by the contextual help
// button in the app bar.

/** Every help document, in menu order. */
export const helpDocs: HelpDocMeta[] = helpManifest

export function findHelpDoc(slug: string | undefined): HelpDocMeta | undefined {
    return slug ? helpDocs.find(doc => doc.slug === slug) : undefined
}

/**
 * The slug to show for a route parameter: missing or unknown means the first topic. Used both
 * by the topic list (to highlight) and by the content page.
 */
export function resolveHelpSlug(param: string | string[] | undefined): string | undefined {
    const value = Array.isArray(param) ? param[0] : param
    return findHelpDoc(value)?.slug ?? helpDocs[0]?.slug
}

/**
 * The documents grouped for the help menu. Documents without a `group` go into an untitled
 * group, shown first.
 */
export function groupedHelpDocs(): { group: string | undefined, docs: HelpDocMeta[] }[] {
    const groups: { group: string | undefined, docs: HelpDocMeta[] }[] = []
    for (const doc of helpDocs) {
        const existing = groups.find(entry => entry.group === doc.group)
        if (existing) {
            existing.docs.push(doc)
        } else {
            groups.push({ group: doc.group, docs: [doc] })
        }
    }
    return groups
}

/**
 * Finds the help document for a page of the application. The most specific declared route wins,
 * so `/reports/daily` is not swallowed by `/reports`.
 */
export function findHelpDocForPath(path: string): HelpDocMeta | undefined {
    let best: { doc: HelpDocMeta, length: number } | undefined
    for (const doc of helpDocs) {
        for (const route of doc.routes) {
            const matches = path === route || path.startsWith(`${route}/`)
            if (matches && (!best || route.length > best.length)) {
                best = { doc, length: route.length }
            }
        }
    }
    return best?.doc
}

/**
 * Loads a document's HTML. Each document is a separate chunk, so the documentation downloads
 * nothing until the user opens it.
 */
export async function loadHelpDocHtml(slug: string): Promise<string> {
    const loader = helpDocLoaders[slug]
    if (!loader) {
        throw new Error(`Help document "${slug}" does not exist.`)
    }
    const loaded = await loader()
    return loaded.default
}
