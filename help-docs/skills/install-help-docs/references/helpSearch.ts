// Destination: <appSrc>/utils/helpSearch.ts
import type { HelpSearchEntry } from '~/help/types'
import { helpDocs, isHelpModuleEnabled } from '~/utils/helpDocs'

// Searching the help documentation. The index is generated at build time, one entry per section
// of each document (see `scripts/generate-help.mjs`), and is fetched only on the first search:
// it is the documents' whole text, and the Help button sits in the app bar of every page, so it
// has no business in the startup bundle.

/** The minimum number of characters before the search returns anything. */
export const HELP_SEARCH_MIN_LENGTH = 2

/** How many results are shown. More does not help: nobody scrolls a list of matches. */
const HELP_SEARCH_MAX_RESULTS = 20

/**
 * How many characters of each searched word are compared. The user types the form that comes to
 * mind, so "booking" should find "bookings" and "invoices" should find "invoice". Comparing only
 * the start of the word makes the ending irrelevant -- without a dictionary of forms and without
 * fuzzy matching.
 *
 * The price is that a long word is compared on its stem only, so "contravention" also brings up
 * sections about contracts. Those are extra results, scored low, not missing ones -- the right
 * trade-off for a documentation search.
 */
const TERM_PREFIX_LENGTH = 6

/**
 * Filler words are dropped from the search. In a naturally typed question ("how do I cancel a
 * booking") they say nothing about the subject but appear in almost any text, so they would
 * dilute the score of the words that matter.
 *
 * This list is English. If the documentation is written in another language, replace it --
 * nothing else in this file is language-specific.
 */
const STOP_WORDS = new Set([
    'a', 'about', 'after', 'all', 'am', 'an', 'and', 'any', 'are', 'as', 'at', 'be', 'been',
    'but', 'by', 'can', 'do', 'does', 'each', 'for', 'from', 'get', 'has', 'have', 'how', 'i',
    'if', 'in', 'into', 'is', 'it', 'its', 'me', 'my', 'no', 'not', 'of', 'on', 'one', 'only',
    'or', 'other', 'our', 'out', 'so', 'some', 'than', 'that', 'the', 'their', 'them', 'then',
    'there', 'these', 'they', 'this', 'to', 'up', 'was', 'we', 'what', 'when', 'where', 'which',
    'who', 'why', 'will', 'with', 'you', 'your',
])

/** How much text is shown around the match, in characters. */
const SNIPPET_BEFORE = 60
const SNIPPET_AFTER = 140

// A match's score, by where it appears. The document title weighs most, because it says what the
// subject is; the section's body weighs least.
const TOKEN_SCORE = { docTitle: 8, heading: 4, text: 1 }
// Bonus when the searched words appear in exactly the order typed, one after another.
const PHRASE_SCORE = { docTitle: 12, heading: 8, text: 4 }
// Bonus for each additional searched word that matches. It weighs more than where the match is,
// because a section containing all the typed words is almost always the one being looked for,
// even if it only has them in its body.
const COVERAGE_SCORE = 10

const WORD_CHAR_RE = /[\p{L}\p{N}]/u

/** The snippet shown for a result, split so it can be highlighted without `v-html`. */
export interface HelpSnippet {
    before: string
    match: string
    after: string
}

export interface HelpSearchResult {
    slug: string
    section: string
    /** The title of the document the section comes from. */
    docTitle: string
    /** The section's heading. */
    heading: string
    snippet?: HelpSnippet
    score: number
}

/**
 * Folds text for comparison: no diacritics, lower case, so "rezervari" finds "Rezervări". Also
 * returns, for each resulting character, its position in the original -- normalising can change
 * the length (`ﬁ` -> `fi`), and the snippet is cut out of the original using the match's
 * positions.
 */
function fold(value: string): { text: string, offsets: number[] } {
    let text = ''
    const offsets: number[] = []
    for (let index = 0; index < value.length; index++) {
        for (const char of value[index]!.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()) {
            text += char
            offsets.push(index)
        }
    }
    return { text, offsets }
}

/**
 * Looks for a term only at the start of a word. So "day" finds "daily" but not "Monday" -- a
 * match in the middle of a word is almost never the one wanted.
 */
function findAtWordStart(haystack: string, needle: string): number {
    let at = haystack.indexOf(needle)
    while (at > 0 && WORD_CHAR_RE.test(haystack[at - 1]!)) {
        at = haystack.indexOf(needle, at + 1)
    }
    return at
}

/**
 * The searched terms: the folded text, split at anything that is not a letter or a digit,
 * without the filler words and cut back to the stem (see `TERM_PREFIX_LENGTH`).
 *
 * If nothing else is left in the query, the filler words are kept: someone searching for "what"
 * itself must get something back, not an empty list.
 */
function queryTerms(query: string): string[] {
    const words = fold(query).text.split(/[^\p{L}\p{N}]+/u).filter(Boolean)
    const meaningful = words.filter(word => !STOP_WORDS.has(word))
    return [...new Set((meaningful.length ? meaningful : words).map(word => word.slice(0, TERM_PREFIX_LENGTH)))]
}

/** An index entry with its texts already folded -- folded once, not on every keystroke. */
interface PreparedEntry {
    entry: HelpSearchEntry
    docTitle: string
    foldedDocTitle: string
    foldedHeading: string
    foldedText: string
    /** The document's position in the menu, used to break score ties. */
    docOrder: number
}

let preparedIndex: Promise<PreparedEntry[]> | undefined

/**
 * Fetches and prepares the index. The result is memoised: the dynamic import and the folding
 * happen once per session.
 */
function loadIndex(): Promise<PreparedEntry[]> {
    preparedIndex ??= import('~/help/generated/search-index').then(({ helpSearchIndex }) => {
        // Deliberately the unfiltered list: this runs once and is memoised, so filtering by
        // module here would freeze whatever the module state happened to be at the first
        // search. Modules are filtered per query, below.
        const docs = new Map(helpDocs.map(doc => [doc.slug, doc]))
        const prepared: PreparedEntry[] = []
        for (const entry of helpSearchIndex) {
            const doc = docs.get(entry.slug)
            if (!doc) {
                continue
            }
            prepared.push({
                entry,
                docTitle: doc.title,
                foldedDocTitle: fold(doc.title).text,
                foldedHeading: fold(entry.heading).text,
                foldedText: fold(entry.text).text,
                docOrder: doc.order,
            })
        }
        return prepared
    })
    return preparedIndex
}

/**
 * An entry's score for the given terms, or `undefined` if none of them appear in it.
 *
 * A single matching word is enough, and coverage is rewarded through the score instead: a
 * naturally typed question almost always contains a word that appears nowhere in the
 * documentation, and requiring every word would answer with an empty list exactly when the user
 * most needs an answer.
 */
function scoreEntry(prepared: PreparedEntry, terms: string[], phrase: string): number | undefined {
    let score = 0
    let matched = 0
    for (const term of terms) {
        const inDocTitle = findAtWordStart(prepared.foldedDocTitle, term) !== -1
        const inHeading = findAtWordStart(prepared.foldedHeading, term) !== -1
        const inText = findAtWordStart(prepared.foldedText, term) !== -1
        if (!inDocTitle && !inHeading && !inText) {
            continue
        }
        matched++
        score += (inDocTitle ? TOKEN_SCORE.docTitle : 0)
            + (inHeading ? TOKEN_SCORE.heading : 0)
            + (inText ? TOKEN_SCORE.text : 0)
    }
    if (!matched) {
        return undefined
    }
    score += COVERAGE_SCORE * (matched - 1)
    if (terms.length > 1) {
        if (findAtWordStart(prepared.foldedDocTitle, phrase) !== -1) {
            score += PHRASE_SCORE.docTitle
        }
        if (findAtWordStart(prepared.foldedHeading, phrase) !== -1) {
            score += PHRASE_SCORE.heading
        }
        if (findAtWordStart(prepared.foldedText, phrase) !== -1) {
            score += PHRASE_SCORE.text
        }
    }
    return score
}

/**
 * Cuts the snippet around the first match out of the section's text. `needles` are the terms in
 * preferred order (the whole phrase first, then the separate words): the first one that appears
 * in the text is used.
 */
function buildSnippet(text: string, needles: string[]): HelpSnippet | undefined {
    if (!text) {
        return undefined
    }
    const { text: folded, offsets } = fold(text)
    const needle = needles.find(candidate => findAtWordStart(folded, candidate) !== -1)
    if (!needle) {
        return undefined
    }
    const foldedAt = findAtWordStart(folded, needle)
    // The whole word is highlighted, not just the searched stem: "bookin" found inside
    // "bookings" shows highlighted to the end, the way the user reads it.
    let foldedEnd = foldedAt + needle.length
    while (foldedEnd < folded.length && WORD_CHAR_RE.test(folded[foldedEnd]!)) {
        foldedEnd++
    }
    const start = offsets[foldedAt]!
    const end = offsets[foldedEnd] ?? text.length

    // The edges move to the nearest space, so the snippet neither starts nor ends in the middle
    // of a word.
    let from = Math.max(0, start - SNIPPET_BEFORE)
    if (from > 0) {
        const space = text.indexOf(' ', from)
        from = space !== -1 && space < start ? space + 1 : from
    }
    let to = Math.min(text.length, end + SNIPPET_AFTER)
    if (to < text.length) {
        const space = text.lastIndexOf(' ', to)
        to = space > end ? space : to
    }

    return {
        before: (from > 0 ? '… ' : '') + text.slice(from, start),
        match: text.slice(start, end),
        after: text.slice(end, to) + (to < text.length ? ' …' : ''),
    }
}

/**
 * Searches the help documentation. Returns the best-matching sections, each with the document it
 * comes from and the snippet the search appears in.
 */
export async function searchHelpDocs(query: string): Promise<HelpSearchResult[]> {
    const terms = queryTerms(query)
    if (!terms.length || query.trim().length < HELP_SEARCH_MIN_LENGTH) {
        return []
    }
    // The whole phrase is compared unshortened: it is only a bonus, and one stem glued to the
    // next would match nothing.
    const phrase = fold(query).text.trim().replace(/\s+/gu, ' ')
    const needles = terms.length > 1 ? [phrase, ...terms] : terms

    const matches: { prepared: PreparedEntry, score: number }[] = []
    for (const prepared of await loadIndex()) {
        // A section hidden with its module must not be findable either -- otherwise search
        // sends the reader to a place where the thing they searched for is not shown. The
        // entry's module is its `:::module` block's, or failing that its document's, so this
        // one check covers a hidden passage and a hidden document alike.
        if (!isHelpModuleEnabled(prepared.entry.module)) {
            continue
        }
        const score = scoreEntry(prepared, terms, phrase)
        if (score !== undefined) {
            matches.push({ prepared, score })
        }
    }

    matches.sort((a, b) => b.score - a.score || a.prepared.docOrder - b.prepared.docOrder)

    return matches.slice(0, HELP_SEARCH_MAX_RESULTS).map(({ prepared, score }) => ({
        slug: prepared.entry.slug,
        section: prepared.entry.section,
        docTitle: prepared.docTitle,
        heading: prepared.entry.heading,
        snippet: buildSnippet(prepared.entry.text, needles),
        score,
    }))
}
