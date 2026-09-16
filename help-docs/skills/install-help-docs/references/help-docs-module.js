// Destination: <nuxtDir>/modules/help-docs.js
import { watch } from 'node:fs'
import { generateHelpDocs, HELP_SOURCE_DIR } from '../scripts/generate-help.mjs'

// Regenerates the help documentation (docs/help/*.md -> app/help/generated) on every dev
// server start and before every build. Nuxt auto-registers everything in `modules/`, so this
// file needs no entry in `nuxt.config.ts` -- but it IS read at startup only, so adding or
// changing it requires restarting the dev server.
//
// The generated files are not kept in git, so they must exist after generation: an invalid
// document stops a build, catching the mistake before delivery. In development it only warns,
// so a typo does not kill a server that is already running.
export default async function helpDocsModule(_options, nuxt) {
    async function regenerate({ fatal }) {
        try {
            const count = await generateHelpDocs()
            if (count) {
                console.info(`[help] ${count} help documents generated`)
            }
        } catch (error) {
            if (fatal) {
                throw new Error(`[help] generating the documentation failed: ${error.message}`, { cause: error })
            }
            console.warn(`[help] WARNING: generating the documentation failed, the documents are unchanged -- ${error.message}`)
        }
    }

    await regenerate({ fatal: !nuxt.options.dev })

    if (!nuxt.options.dev) {
        return
    }

    // In development, editing a document shows up immediately: the generated files live under
    // the app's source root, so Vite picks them up through HMR once they are rewritten.
    let pending = null
    try {
        watch(HELP_SOURCE_DIR, { recursive: true }, () => {
            clearTimeout(pending)
            pending = setTimeout(() => regenerate({ fatal: false }), 150)
        })
    } catch {
        // No source folder means nothing to watch -- generation has already reported why.
    }
}
