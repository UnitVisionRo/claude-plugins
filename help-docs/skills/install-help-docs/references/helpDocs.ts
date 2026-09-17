// Destination: <appSrc>/utils/helpDocs.ts
import { helpDocLoaders, helpManifest } from '~/help/generated/manifest'
import type { HelpDocMeta } from '~/help/types'
import { helpModuleFlags } from '~/utils/helpModules'

// Utilities over the generated documentation. Used by the help page and by the contextual help
// button in the app bar.

/** Every help document, in menu order, including those of switched-off modules. */
export const helpDocs: HelpDocMeta[] = helpManifest

/**
 * Whether a module's content should be shown. Content without a module is always visible.
 * Design: docs/specs/2026-09-17-help-modules.md sections 3 and 6.2 (in the help-docs plugin's repository).
 *
 *
 * An unknown module counts as switched OFF. Hiding a topic is recoverable; pointing a reader at
 * a screen their installation does not have is not.
 *
 * The documentation is generated in full regardless -- the flag is computed here, in the running
 * application, so the same build serves an installation with the module and one without, and
 * switching it takes effect without regenerating anything.
 */
export function isHelpModuleEnabled(module: string | undefined): boolean {
    if (!module) {
        return true
    }
    const isEnabled = helpModuleFlags[module as keyof typeof helpModuleFlags]
    return isEnabled ? isEnabled() : false
}

/** The documents visible right now: everything except switched-off modules. */
export function visibleHelpDocs(): HelpDocMeta[] {
    return helpDocs.filter(doc => isHelpModuleEnabled(doc.module))
}

/**
 * Strips the `:::module` blocks of switched-off modules from a document's HTML. They are
 * generated as `<div data-help-module="...">`.
 *
 * Parsing into a template element is safe here: the HTML is our own, compiled at build time with
 * raw HTML disabled in the Markdown parser. It never contains anything a user wrote.
 *
 * On a server render there is no DOM, so the HTML is returned untouched. That branch is
 * unreachable in practice -- the content component only renders the body once loading is false,
 * and loading starts true -- but an unguarded `document` in a utility is a trap for the next
 * caller.
 */
export function filterHelpModuleBlocks(html: string): string {
    if (!html || typeof document === 'undefined') {
        return html
    }
    const holder = document.createElement('template')
    holder.innerHTML = html
    for (const element of holder.content.querySelectorAll('[data-help-module]')) {
        if (!isHelpModuleEnabled(element.getAttribute('data-help-module') ?? undefined)) {
            element.remove()
        }
    }
    return holder.innerHTML
}

export function findHelpDoc(slug: string | undefined): HelpDocMeta | undefined {
    return slug ? visibleHelpDocs().find(doc => doc.slug === slug) : undefined
}

/**
 * The slug to show for a route parameter: missing or unknown means the first topic. Used both
 * by the topic list (to highlight) and by the content page.
 */
export function resolveHelpSlug(param: string | string[] | undefined): string | undefined {
    const value = Array.isArray(param) ? param[0] : param
    return findHelpDoc(value)?.slug ?? visibleHelpDocs()[0]?.slug
}

/**
 * The documents grouped for the help menu. Documents without a `group` go into an untitled
 * group, shown first.
 */
export function groupedHelpDocs(): { group: string | undefined, docs: HelpDocMeta[] }[] {
    const groups: { group: string | undefined, docs: HelpDocMeta[] }[] = []
    for (const doc of visibleHelpDocs()) {
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
    for (const doc of visibleHelpDocs()) {
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
