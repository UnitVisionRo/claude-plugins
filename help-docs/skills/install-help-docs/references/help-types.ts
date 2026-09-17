// Destination: <appSrc>/help/types.ts
// The help documentation's types. Consumed by the generated `generated/manifest.ts` and by the
// utilities in `~/utils/helpDocs`.

/** A heading in a document, used for the outline and for links to sections. */
export interface HelpHeading {
    id: string
    text: string
    level: number
    /**
     * The module of the `:::module` block this heading sits in, if any. The heading does NOT
     * inherit its document's `module` -- the two are separate facts, and the generator checks
     * links against both.
     */
    module?: string
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
    /**
     * The module that hides this section: its `:::module` block's, or failing that its
     * document's. Unlike `HelpHeading.module` this DOES inherit from the document, because here
     * either reason to hide the section should keep it out of the results.
     */
    module?: string
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
    /**
     * The optional module this whole document belongs to; absent means always visible. Declared
     * in `docs/help/modules.json` and switched on or off by `~/utils/helpModules`.
     */
    module?: string
    headings: HelpHeading[]
}
