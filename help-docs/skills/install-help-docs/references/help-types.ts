// Destination: <nuxtDir>/<srcDir>/help/types.ts
// The help documentation's types. Consumed by the generated `generated/manifest.ts` and by the
// utilities in `~/utils/helpDocs`.

/** A heading in a document, used for the outline and for links to sections. */
export interface HelpHeading {
    id: string
    text: string
    level: number
}

/**
 * The help target of a tab on a tabbed page: the document that explains it and, optionally, the
 * section to scroll to.
 */
export interface HelpTabTarget {
    slug: string
    section?: string
}

/** One search index entry: the text of one section of one document. */
export interface HelpSearchEntry {
    slug: string
    /** The id of the section's heading; reaches the address as /help/<slug>?s=<section>. */
    section: string
    /** The section's heading, shown as the result's title. */
    heading: string
    /** The section's visible text, diacritics intact: the search folds them at runtime. */
    text: string
}

/** A help document's metadata, taken from the Markdown file's frontmatter. */
export interface HelpDocMeta {
    /** The file name without its extension; appears in the address as /help/<slug>. */
    slug: string
    title: string
    /** Position in the help menu (ascending). */
    order: number
    /** The menu section the document appears in. */
    group?: string
    summary?: string
    /** The application paths this document is the contextual help for. */
    routes: string[]
    /**
     * The help for each tab of the pages covered by `routes`, keyed by the tab's value in the
     * address (`?activeTab=`). The Help button opens the active tab's target directly.
     */
    tabs?: Record<string, HelpTabTarget>
    headings: HelpHeading[]
}
