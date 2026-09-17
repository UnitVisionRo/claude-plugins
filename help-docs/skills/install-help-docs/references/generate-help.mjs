// Destination: <appRoot>/scripts/generate-help.mjs
// Generator for the user-facing help documentation.
//
// The source of truth is the Markdown in `docs/help/` (kept in git, edited by developers).
// This script compiles it to HTML and writes the result into `<srcDir>/help/generated/`,
// from where the application imports it straight out of its bundle.
//
// Why compile at build time instead of in the browser:
//   - a document that does not exist can then never be requested at runtime -- a missing
//     one is a build error here, not a blank screen in production;
//   - the Markdown parser never reaches the bundle the user downloads;
//   - a wrong link between documents becomes an error at generation time.
//
// The generated files are NOT kept in git: they are produced on every build and on dev
// server start. An invalid document stops the build.
import { copyFile, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises'
import { basename, dirname, extname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import matter from 'gray-matter'
import MarkdownIt from 'markdown-it'

// The Nuxt project directory -- the parent of this script's own folder.
const NUXT_DIR = resolve(fileURLToPath(new URL('.', import.meta.url)), '..')

// The app's source root, relative to NUXT_DIR: `app` on Nuxt 4, `.` on Nuxt 3.
const SRC_SUBDIR = 'app'

// Where the Markdown lives, relative to NUXT_DIR. The default suits a repository whose Nuxt
// app sits in a subdirectory (`gui/`, `front/`); for a Nuxt app AT the repository root this
// is `docs/help`. A Docker image that copies only the Nuxt directory sets HELP_DOCS_DIR.
const DOCS_SUBPATH = '../docs/help'

export const HELP_SOURCE_DIR = process.env.HELP_DOCS_DIR
    ? resolve(process.env.HELP_DOCS_DIR)
    : resolve(NUXT_DIR, DOCS_SUBPATH)

// Images are written in the documents as paths relative to the Markdown file (usually
// `../screenshots/<id>.png`) and must stay inside the documents' parent folder. That way what
// GitHub and an editor show from the `.md` is exactly what the application shows, and a
// Docker image copies `docs/help` and `docs/screenshots` next to each other.
const IMAGES_ROOT_DIR = dirname(HELP_SOURCE_DIR)

const IMAGE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'])

const OUTPUT_DIR = join(NUXT_DIR, SRC_SUBDIR, 'help', 'generated')
const DOCS_OUTPUT_DIR = join(OUTPUT_DIR, 'docs')
const IMAGES_OUTPUT_DIR = join(OUTPUT_DIR, 'images')

// Placed in the HTML instead of an image's address. The final address (with its hash, and
// with the `baseURL` that differs between development and production) is Vite's to decide, so
// images are imported from the generated module and substituted on load -- see `renderDocModule`.
const IMAGE_PLACEHOLDER = index => `__HELP_IMAGE_${index}__`
const IMAGE_PLACEHOLDER_RE = /__HELP_IMAGE_(\d+)__/g

const GENERATED_HEADER = [
    '// AUTOMATICALLY GENERATED FILE -- do not edit by hand.',
    '// Source: docs/help/*.md -- regenerate with `npm run help:generate`.',
].join('\n')

// Design: docs/specs/2026-09-17-help-modules.md sections 7 and 9 (in the help-docs plugin's repository).
//
// The optional modules this documentation set declares. This file is the ONE place module
// names are written down: the generator validates every use against it, and emits it as the
// `HelpModuleName` union so the application's predicates are checked against the same list. A
// missing file means no modules, so this costs an application that has none exactly nothing.
const MODULES_FILE_NAME = 'modules.json'

async function readDeclaredModules() {
    let raw
    try {
        raw = await readFile(join(HELP_SOURCE_DIR, MODULES_FILE_NAME), 'utf8')
    } catch (error) {
        if (error.code === 'ENOENT') {
            return new Set()
        }
        throw error
    }
    let parsed
    try {
        parsed = JSON.parse(raw)
    } catch (error) {
        throw new Error(`docs/help/${MODULES_FILE_NAME}: not valid JSON -- ${error.message}`)
    }
    if (!Array.isArray(parsed) || parsed.some(name => typeof name !== 'string' || !name.trim())) {
        throw new Error(`docs/help/${MODULES_FILE_NAME}: must be a list of module names, for example ["gdpr"]`)
    }
    return new Set(parsed)
}

/** One message for an undeclared module, so it reads the same wherever it is raised. */
function undeclaredModuleError(fileName, name, declared) {
    const list = declared.size
        ? [...declared].sort().map(module => `"${module}"`).join(', ')
        : 'none are declared'
    return new Error(`docs/help/${fileName}: unknown module "${name}". Declared in ${MODULES_FILE_NAME}: ${list}.`)
}

/**
 * Turns a heading into a section identifier: no diacritics, usable in the `?s=` route
 * parameter.
 */
function slugify(text) {
    return text
        .normalize('NFD')
        .replace(/\p{M}/gu, '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
}

// Instruction files for developers and agents may sit in the documents folder without being
// content for users. Compared lower-cased, so `CLAUDE.MD` is caught too.
const IGNORED_FILE_NAMES = new Set(['claude.md', 'agents.md', 'readme.md'])

/**
 * Reads the Markdown documents from the source folder. Files starting with `_` and the
 * instruction files above are skipped -- notes for developers, not content for users.
 */
async function readSourceDocs(declaredModules) {
    const entries = await readdir(HELP_SOURCE_DIR, { withFileTypes: true })
    const files = entries
        .filter(entry => {
            const name = entry.name.toLowerCase()
            return entry.isFile()
                && name.endsWith('.md')
                && !name.startsWith('_')
                && !IGNORED_FILE_NAMES.has(name)
        })
        .map(entry => entry.name)
        .sort()

    const docs = []
    for (const fileName of files) {
        const slug = fileName.replace(/\.md$/i, '')
        if (slug !== slugify(slug)) {
            throw new Error(`docs/help/${fileName}: the file name must be lowercase, without diacritics (suggestion: "${slugify(slug)}.md")`)
        }
        const raw = await readFile(join(HELP_SOURCE_DIR, fileName), 'utf8')
        const { data, content } = matter(raw)
        if (!data.title) {
            throw new Error(`docs/help/${fileName}: "title" is missing from the frontmatter`)
        }
        if (data.routes !== undefined && !Array.isArray(data.routes)) {
            throw new Error(`docs/help/${fileName}: "routes" must be a list of application paths`)
        }
        if (data.module !== undefined && !declaredModules.has(String(data.module))) {
            throw undeclaredModuleError(fileName, String(data.module), declaredModules)
        }
        const rawTabs = readRawTabs(fileName, data.tabs)
        docs.push({
            slug,
            fileName,
            content,
            rawTabs,
            meta: {
                slug,
                title: String(data.title),
                order: Number(data.order ?? 999),
                group: data.group ? String(data.group) : undefined,
                summary: data.summary ? String(data.summary) : undefined,
                routes: (data.routes ?? []).map(String),
                module: data.module ? String(data.module) : undefined,
            },
        })
    }
    return docs
}

const MODULE_OPEN_RE = /^:::module\s+(\S+)\s*$/
const MODULE_CLOSE_RE = /^:::\s*$/

/**
 * A Markdown extension for passages belonging to an optional module.
 * Design: docs/specs/2026-09-17-help-modules.md section 4 (authoring).
 *
 *     :::module gdpr
 *     ... shown only where the GDPR module is switched on ...
 *     :::
 *
 * The block becomes `<div data-help-module="gdpr">`, which the application removes from the page
 * when the module is off. The content is compiled either way -- see the head of this file.
 *
 * Blocks do not nest: a module inside a module has no meaning and would make the filtering
 * ambiguous about which flag governs what.
 */
function helpModulePlugin(md, fileName, declaredModules) {
    md.block.ruler.before('fence', 'help_module', (state, startLine, endLine, silent) => {
        const lineAt = line => state.src.slice(state.bMarks[line] + state.tShift[line], state.eMarks[line])
        const open = MODULE_OPEN_RE.exec(lineAt(startLine))
        if (!open) {
            return false
        }
        if (silent) {
            return true
        }
        const name = open[1]
        if (!declaredModules.has(name)) {
            throw undeclaredModuleError(fileName, name, declaredModules)
        }

        let closeLine = -1
        for (let line = startLine + 1; line < endLine; line++) {
            const text = lineAt(line)
            if (MODULE_OPEN_RE.test(text)) {
                throw new Error(`docs/help/${fileName}: ":::module" blocks cannot be nested`)
            }
            if (MODULE_CLOSE_RE.test(text)) {
                closeLine = line
                break
            }
        }
        if (closeLine === -1) {
            throw new Error(`docs/help/${fileName}: ":::module ${name}" is never closed (a line reading ":::" is missing)`)
        }

        const openToken = state.push('help_module_open', 'div', 1)
        openToken.attrSet('data-help-module', name)
        openToken.block = true

        state.md.block.tokenize(state, startLine + 1, closeLine)

        state.push('help_module_close', 'div', -1).block = true
        state.line = closeLine + 1
        return true
    })
}

/**
 * The module each token belongs to: `undefined` outside `:::module` blocks, the module's name
 * inside one. Used to label the headings of the outline and to validate links into a module.
 */
function moduleContextByToken(tokens) {
    const context = new Array(tokens.length)
    let current
    tokens.forEach((token, index) => {
        if (token.type === 'help_module_open') {
            current = token.attrGet('data-help-module')
            context[index] = undefined
            return
        }
        if (token.type === 'help_module_close') {
            context[index] = undefined
            current = undefined
            return
        }
        context[index] = current
    })
    return context
}

/**
 * Adds an `id` to every heading and returns the document's outline. The ids are what links to
 * sections use (`/help/<slug>?s=<id>`). A heading inside a module block carries that module, so
 * it leaves the outline together with its section.
 */
function applyHeadingIds(tokens, modules) {
    const headings = []
    const used = new Map()
    tokens.forEach((token, index) => {
        if (token.type !== 'heading_open') {
            return
        }
        const text = tokens[index + 1]?.content ?? ''
        const base = slugify(text) || 'section'
        const seen = used.get(base) ?? 0
        used.set(base, seen + 1)
        const id = seen === 0 ? base : `${base}-${seen + 1}`
        token.attrSet('id', id)
        headings.push({ id, text, level: Number(token.tag.slice(1)), module: modules[index] })
    })
    return headings
}

/**
 * Checks an anchor before rewriting it: the section has to exist in the target document, and it
 * has to be visible whenever the place linking to it is. Without the first check a renamed
 * heading leaves links that lead nowhere -- their form stays valid, so nothing else would catch
 * them. Without the second, switching a module off turns a live link into a dead one.
 */
function assertSectionExists({ sourceDoc, section, href, headings, linkModule }) {
    const heading = headings.find(item => item.id === section)
    if (!heading) {
        const available = headings.map(item => item.id)
        const list = available.length
            ? ` Available sections: ${available.map(id => `"#${id}"`).join(', ')}.`
            : ' The target document has no sections.'
        throw new Error(`docs/help/${sourceDoc.fileName}: link to a section that does not exist ("${href}").${list}`)
    }
    // A section written inside a `:::module` block disappears with its module. A link to it is
    // only safe if it disappears at the same time -- because it too is inside that module, or
    // because the whole document linking from it belongs to that module.
    const sectionModule = heading.module
    if (sectionModule && sourceDoc.meta.module !== sectionModule && linkModule !== sectionModule) {
        throw new Error(`docs/help/${sourceDoc.fileName}: link to the section "${href}", which belongs to the module "${sectionModule}". Put the link inside a ":::module ${sectionModule}" block, or mark the document with "module: ${sectionModule}".`)
    }
}

/**
 * Reads `tabs` from the frontmatter: pairs of "the tab's value in the address" -> help target.
 * The target is written like any other documentation link (`#section`, `other.md` or
 * `other.md#section`), so the author does not have to learn a second syntax.
 */
function readRawTabs(fileName, value) {
    if (value === undefined) {
        return undefined
    }
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
        throw new Error(`docs/help/${fileName}: "tabs" must be a list of "tab: target" pairs`)
    }
    const entries = Object.entries(value)
    for (const [tab, target] of entries) {
        if (typeof target !== 'string' || !target.trim()) {
            throw new Error(`docs/help/${fileName}: the target of tab "${tab}" must be text ("#section" or "document.md#section")`)
        }
    }
    return Object.fromEntries(entries.map(([tab, target]) => [tab, String(target).trim()]))
}

/**
 * Resolves the `tabs` targets into {slug, section}, checking each one exists -- exactly like a
 * link in the text. Without this check, renaming a heading would leave the Help button opening
 * the document unscrolled, with no sign that the target had been lost.
 */
function resolveTabTargets({ sourceDoc, docsBySlug, headingsBySlug }) {
    const rawTabs = sourceDoc.rawTabs
    if (!rawTabs) {
        return undefined
    }
    const resolved = {}
    for (const [tab, target] of Object.entries(rawTabs)) {
        const [rawTarget, section] = target.split('#')
        const targetSlug = rawTarget ? rawTarget.replace(/\.md$/i, '') : sourceDoc.slug
        const targetDoc = docsBySlug.get(targetSlug)
        if (!targetDoc) {
            throw new Error(`docs/help/${sourceDoc.fileName}: tab "${tab}" points at the non-existent document "${rawTarget}"`)
        }
        // A tab is always on screen, so the Help button must always have something to open for
        // it. Pointing it at a document that disappears with a module would leave the button
        // falling back to the topic list on a screen that has a document.
        if (targetDoc.meta.module) {
            throw new Error(`docs/help/${sourceDoc.fileName}: tab "${tab}" points at "${targetSlug}", a document of the module "${targetDoc.meta.module}". A tab is always visible, so its help cannot depend on a module.`)
        }
        if (section) {
            assertSectionExists({
                sourceDoc,
                section,
                href: target,
                headings: headingsBySlug.get(targetSlug) ?? [],
                // The tab's target must be visible whenever the tab is, i.e. unconditionally.
                linkModule: undefined,
            })
        }
        resolved[tab] = section ? { slug: targetSlug, section } : { slug: targetSlug }
    }
    return resolved
}

/**
 * Rewrites the links in the documents. Only the forms below are accepted; anything else stops
 * generation, so that no dead link reaches a user.
 *
 * Accepted in Markdown:
 *   [text](#heading)            a section of the current document
 *   [text](other.md)            another help document, optionally with #section
 *   [text](app:/users)          a page of the application
 *   [text](https://...)         an external address, opened in a new tab
 *
 * A section is addressed with the `?s=` query parameter rather than a real `#anchor`, because
 * the same HTML is also rendered inside the contextual help dialog, where the browser has no
 * anchor to jump to -- `HelpContent.vue` scrolls to it itself, identically in both places.
 */
function rewriteLinks(tokens, doc, docsBySlug, headingsBySlug, modules) {
    tokens.forEach((token, index) => {
        const linkModule = modules[index]
        const children = token.type === 'inline' ? token.children ?? [] : []
        for (const child of children) {
            if (child.type !== 'link_open') {
                continue
            }
            const href = child.attrGet('href') ?? ''

            if (/^https?:\/\//.test(href) || href.startsWith('mailto:')) {
                child.attrSet('target', '_blank')
                child.attrSet('rel', 'noopener noreferrer')
                continue
            }
            if (href.startsWith('app:')) {
                child.attrSet('href', href.slice('app:'.length))
                continue
            }
            if (href.startsWith('#')) {
                const localSection = href.slice(1)
                assertSectionExists({
                    sourceDoc: doc,
                    section: localSection,
                    href,
                    headings: headingsBySlug.get(doc.slug) ?? [],
                    linkModule,
                })
                child.attrSet('href', `/help/${doc.slug}?s=${localSection}`)
                continue
            }
            const [target, section] = href.split('#')
            if (target?.endsWith('.md')) {
                const targetSlug = target.replace(/^\.\//, '').replace(/\.md$/, '')
                if (!docsBySlug.has(targetSlug)) {
                    throw new Error(`docs/help/${doc.fileName}: link to a document that does not exist ("${href}")`)
                }
                if (section) {
                    assertSectionExists({
                        sourceDoc: doc,
                        section,
                        href,
                        headings: headingsBySlug.get(targetSlug) ?? [],
                        linkModule,
                    })
                }
                child.attrSet('href', `/help/${targetSlug}${section ? `?s=${section}` : ''}`)
                continue
            }
            throw new Error(`docs/help/${doc.fileName}: unrecognised link ("${href}"). Use another .md document, "app:/path", "#section" or an http(s) address.`)
        }
    })
}

/**
 * A PNG's dimensions, from its IHDR header. Put on the `<img>` as `width`/`height`, they
 * reserve the image's space before the file loads -- otherwise scrolling to a section would
 * land somewhere else once the images above it settle. Other formats are not measured;
 * screenshots are PNG.
 */
function pngDimensions(buffer) {
    const isPng = buffer.length >= 24
        && buffer.toString('latin1', 1, 4) === 'PNG'
        && buffer.toString('latin1', 12, 16) === 'IHDR'
    if (!isPng) {
        return undefined
    }
    return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) }
}

/**
 * Validates and registers a document's images. An image is written in Markdown as
 *
 *     ![Alternative text](../screenshots/users-list.png "Optional caption")
 *
 * alone in its paragraph. It becomes a `<figure>` with the image framed and the caption below.
 * Every rule is checked at generation time, so a wrong document stops the build:
 *   - the path is relative to the Markdown file and stays inside the `docs/` folder;
 *   - the file exists and has one of the extensions in `IMAGE_EXTENSIONS`;
 *   - the alternative text is present -- it is what a user without the image reads;
 *   - two files with the same name from different folders cannot both be used, because the
 *     images are copied into a single generated folder.
 *
 * `images` is the registry shared by all documents (absolute path -> file name in the
 * generated folder). Returns this document's images, in the order of the HTML placeholders.
 */
async function collectImages(md, tokens, doc, images) {
    const docImages = []
    for (let index = 0; index < tokens.length; index++) {
        const token = tokens[index]
        if (token.type !== 'inline') {
            continue
        }
        const imageTokens = (token.children ?? []).filter(child => child.type === 'image')
        if (imageTokens.length === 0) {
            continue
        }
        const standsAlone = imageTokens.length === 1
            && token.children.length === 1
            && tokens[index - 1]?.type === 'paragraph_open'
            && tokens[index + 1]?.type === 'paragraph_close'
        const image = imageTokens[0]
        const src = image.attrGet('src') ?? ''
        if (!standsAlone) {
            throw new Error(`docs/help/${doc.fileName}: image "${src}" must stand alone in its paragraph, with no text beside it`)
        }
        if (/^[a-z][a-z0-9+.-]*:/i.test(src) || src.startsWith('/')) {
            throw new Error(`docs/help/${doc.fileName}: image "${src}" must be a file from the repository, written as a relative path (usually "../screenshots/<id>.png")`)
        }
        const absolutePath = resolve(HELP_SOURCE_DIR, src)
        if (relative(IMAGES_ROOT_DIR, absolutePath).startsWith('..')) {
            throw new Error(`docs/help/${doc.fileName}: image "${src}" falls outside the "${IMAGES_ROOT_DIR}" folder`)
        }
        const extension = extname(absolutePath).toLowerCase()
        if (!IMAGE_EXTENSIONS.has(extension)) {
            throw new Error(`docs/help/${doc.fileName}: image "${src}" has an unsupported extension. Valid extensions: ${[...IMAGE_EXTENSIONS].join(', ')}`)
        }
        let buffer
        try {
            buffer = await readFile(absolutePath)
        } catch (error) {
            if (error.code === 'ENOENT') {
                throw new Error(`docs/help/${doc.fileName}: image "${src}" does not exist (${absolutePath})`, { cause: error })
            }
            throw error
        }
        const alt = md.renderer.renderInlineAsText(image.children ?? [], md.options, {}).trim()
        if (!alt) {
            throw new Error(`docs/help/${doc.fileName}: image "${src}" has no alternative text -- write what it shows, between the square brackets`)
        }

        const outputName = basename(absolutePath)
        if (!images.has(absolutePath)) {
            const clash = [...images.entries()].find(([, name]) => name === outputName)
            if (clash) {
                throw new Error(`docs/help/${doc.fileName}: image "${src}" has the same file name as "${clash[0]}"; images must have unique names`)
            }
            images.set(absolutePath, outputName)
        }

        const position = docImages.length
        docImages.push({ absolutePath, outputName })
        image.attrSet('src', IMAGE_PLACEHOLDER(position))
        image.attrSet('alt', alt)
        const dimensions = pngDimensions(buffer)
        if (dimensions) {
            image.attrSet('width', String(dimensions.width))
            image.attrSet('height', String(dimensions.height))
        }
        // The paragraph wrapping the image is not rendered: a `<figure>` cannot sit in a `<p>`.
        tokens[index - 1].hidden = true
        tokens[index + 1].hidden = true
    }
    return docImages
}

const { escapeHtml } = new MarkdownIt().utils

/**
 * Renders an image as a figure: the image framed and, if it has a title, the caption below it.
 * The alternative text and the address are already on the token, from `collectImages`.
 */
function renderImageAsFigure(tokens, index) {
    const token = tokens[index]
    const caption = token.attrGet('title')
    const attrs = token.attrs.filter(([name]) => name !== 'title')
    const img = `<img${attrs.map(([name, value]) => ` ${name}="${escapeHtml(value)}"`).join('')}>`
    const figcaption = caption ? `<figcaption>${escapeHtml(caption)}</figcaption>` : ''
    return `<figure class="help-figure">${img}${figcaption}</figure>\n`
}

/**
 * Compiles the documents. Writes nothing to disk -- if a document is invalid it throws before
 * the existing good version is touched.
 */
async function compileDocs(docs, declaredModules) {
    const docsBySlug = new Map(docs.map(doc => [doc.slug, doc]))

    // First pass: parse each document and work out its outline. Validating the anchors in the
    // second pass needs the headings of every document, including ones not yet processed.
    // `images` is the registry shared by all documents: a screenshot used by two documents is
    // copied once.
    const images = new Map()
    const parsed = []
    for (const doc of docs) {
        const md = new MarkdownIt({ html: false, linkify: true, breaks: false })
        md.renderer.rules.image = renderImageAsFigure
        helpModulePlugin(md, doc.fileName, declaredModules)

        const tokens = md.parse(doc.content, {})
        const modules = moduleContextByToken(tokens)
        const headings = applyHeadingIds(tokens, modules)
        const docImages = await collectImages(md, tokens, doc, images)
        parsed.push({ doc, md, tokens, headings, modules, images: docImages })
    }

    const headingsBySlug = new Map(parsed.map(item => [item.doc.slug, item.headings]))

    // Second pass: rewrite the links, now that anchor targets can be checked too.
    const searchEntries = []
    const compiled = parsed.map(({ doc, md, tokens, headings, modules, images: docImages }) => {
        rewriteLinks(tokens, doc, docsBySlug, headingsBySlug, modules)
        const tabs = resolveTabTargets({ sourceDoc: doc, docsBySlug, headingsBySlug })
        searchEntries.push(...collectSearchEntries(doc, tokens, modules))
        return {
            ...doc,
            html: md.renderer.render(tokens, md.options, {}),
            images: docImages,
            meta: { ...doc.meta, headings, ...(tabs ? { tabs } : {}) },
        }
    })
    return { compiled, images, searchEntries }
}

/**
 * The visible text of an inline token: text nodes and inline code. A link contributes only its
 * label, not its address, and an image only its caption -- exactly what the user reads.
 */
function inlineText(token) {
    const parts = []
    for (const child of token.children ?? []) {
        if (child.type === 'text' || child.type === 'code_inline') {
            parts.push(child.content)
        } else if (child.type === 'softbreak' || child.type === 'hardbreak') {
            // Documents are written with lines wrapped at ~100 columns. Without a space here,
            // the last word of a line would run into the first word of the next.
            parts.push(' ')
        } else if (child.type === 'image') {
            const caption = child.attrGet('title')
            if (caption) {
                parts.push(caption)
            }
        }
    }
    return parts.join('')
}

/**
 * Splits a document into search index entries, one per section.
 *
 * Headings are not folded into the section's text: they are kept separately so they can be
 * scored higher than the body and shown as the result's title.
 */
function collectSearchEntries(doc, tokens, modules) {
    const entries = []
    let heading
    let parts = []

    function flushSection() {
        if (!heading) {
            return
        }
        // A section with no body (just a heading, immediately followed by another) still has to
        // be findable by its heading, so the entry is emitted with empty text.
        const text = parts.join(' ').replace(/\s+/gu, ' ').trim()
        // Unlike the outline's headings, a search entry DOES inherit the document's module:
        // there either reason to hide the section should keep it out of the results.
        entries.push({
            slug: doc.meta.slug,
            section: heading.id,
            heading: heading.text,
            module: heading.module ?? doc.meta.module,
            text,
        })
        parts = []
    }

    tokens.forEach((token, index) => {
        if (token.type === 'heading_open') {
            flushSection()
            heading = {
                id: token.attrGet('id'),
                text: tokens[index + 1]?.content ?? '',
                module: modules[index],
            }
            return
        }
        // A heading's text is the inline token right after it; skip that one.
        if (token.type !== 'inline' || tokens[index - 1]?.type === 'heading_open') {
            return
        }
        const text = inlineText(token)
        if (text.trim()) {
            parts.push(text)
        }
    })
    flushSection()
    return entries
}

/**
 * A document's TypeScript module. Without images it is just the HTML. With images, each file is
 * imported as an asset -- Vite gives it its final address (with hash and `baseURL`) -- and put
 * into the HTML in place of the placeholder left by `collectImages`.
 */
function renderDocModule(doc) {
    if (doc.images.length === 0) {
        return [GENERATED_HEADER, '', `export default ${JSON.stringify(doc.html)}`, ''].join('\n')
    }
    const imports = doc.images.map((image, index) => `import image${index} from '../images/${image.outputName}'`)
    return [
        GENERATED_HEADER,
        '',
        ...imports,
        '',
        `const images = [${doc.images.map((_, index) => `image${index}`).join(', ')}]`,
        `const html = ${JSON.stringify(doc.html)}`,
        '',
        `export default html.replace(${IMAGE_PLACEHOLDER_RE.toString()}, (match, index) => images[Number(index)] ?? match)`,
        '',
    ].join('\n')
}

function renderManifestEntry(meta) {
    const lines = [
        '    {',
        `        slug: ${JSON.stringify(meta.slug)},`,
        `        title: ${JSON.stringify(meta.title)},`,
        `        order: ${meta.order},`,
    ]
    if (meta.group) {
        lines.push(`        group: ${JSON.stringify(meta.group)},`)
    }
    if (meta.summary) {
        lines.push(`        summary: ${JSON.stringify(meta.summary)},`)
    }
    lines.push(`        routes: ${JSON.stringify(meta.routes)},`)
    if (meta.tabs) {
        lines.push(`        tabs: ${JSON.stringify(meta.tabs)},`)
    }
    if (meta.module) {
        lines.push(`        module: ${JSON.stringify(meta.module)},`)
    }
    lines.push(`        headings: ${JSON.stringify(meta.headings)},`)
    lines.push('    },')
    return lines.join('\n')
}

function renderManifest(compiled, declaredModules) {
    const ordered = [...compiled].sort((a, b) => a.meta.order - b.meta.order || a.meta.title.localeCompare(b.meta.title))
    const entries = ordered.map(doc => renderManifestEntry(doc.meta))
    const loaders = ordered.map(doc => `    ${JSON.stringify(doc.slug)}: () => import('./docs/${doc.slug}'),`)

    // The declared modules as a union, so `~/utils/helpModules` is checked against the same
    // list the generator validates the documents against: a declared module with no predicate,
    // or a predicate for something undeclared, is then a type error rather than documentation
    // that quietly never appears. `never` when nothing is declared, which makes the predicate
    // map `{}` -- the shape an application with no optional parts already has.
    const moduleUnion = declaredModules.size
        ? [...declaredModules].sort().map(module => JSON.stringify(module)).join(' | ')
        : 'never'

    return [
        GENERATED_HEADER,
        '',
        "import type { HelpDocMeta } from '../types'",
        '',
        '// The optional modules declared in docs/help/modules.json.',
        `export type HelpModuleName = ${moduleUnion}`,
        '',
        '// Every document\'s metadata, ordered for the help menu.',
        'export const helpManifest: HelpDocMeta[] = [',
        ...entries,
        ']',
        '',
        '// Each document\'s content, loaded on demand (one chunk per document).',
        'export const helpDocLoaders: Record<string, () => Promise<{ default: string }>> = {',
        ...loaders,
        '}',
        '',
    ].join('\n')
}

/**
 * The search index, as a module separate from `manifest.ts` -- and that separation is the
 * point: the manifest reaches the Help button in the app bar, so it is loaded on every page.
 * Putting the documents' text in it would defeat the very reason each document is its own
 * chunk. Here it is imported dynamically, on the first search (see `utils/helpSearch.ts`).
 *
 * The text keeps its diacritics: normalising for comparison happens at runtime, in a single
 * pass, and the index stays half the size.
 */
function renderSearchIndex(entries) {
    return [
        GENERATED_HEADER,
        '',
        "import type { HelpSearchEntry } from '../types'",
        '',
        '// One entry per section of each document, in document order.',
        'export const helpSearchIndex: HelpSearchEntry[] = [',
        ...entries.map(entry => `    ${JSON.stringify(entry)},`),
        ']',
        '',
    ].join('\n')
}

/**
 * Regenerates the documentation. Returns the number of documents compiled.
 */
export async function generateHelpDocs() {
    const declaredModules = await readDeclaredModules()

    let docs
    try {
        docs = await readSourceDocs(declaredModules)
    } catch (error) {
        if (error.code === 'ENOENT') {
            // The generated files are not in git, so without the source the application cannot
            // be built at all. An explicit error beats a missing import.
            throw new Error(
                `the source folder is missing (${HELP_SOURCE_DIR}); set HELP_DOCS_DIR if the documents live elsewhere`,
                { cause: error },
            )
        }
        throw error
    }

    const { compiled, images, searchEntries } = await compileDocs(docs, declaredModules)

    await rm(OUTPUT_DIR, { recursive: true, force: true })
    await mkdir(DOCS_OUTPUT_DIR, { recursive: true })
    await mkdir(IMAGES_OUTPUT_DIR, { recursive: true })
    for (const [absolutePath, outputName] of images) {
        await copyFile(absolutePath, join(IMAGES_OUTPUT_DIR, outputName))
    }
    for (const doc of compiled) {
        await writeFile(join(DOCS_OUTPUT_DIR, `${doc.slug}.ts`), renderDocModule(doc), 'utf8')
    }
    await writeFile(join(OUTPUT_DIR, 'manifest.ts'), renderManifest(compiled, declaredModules), 'utf8')
    await writeFile(join(OUTPUT_DIR, 'search-index.ts'), renderSearchIndex(searchEntries), 'utf8')

    return compiled.length
}

// Run directly (`npm run help:generate`): exit with an error code, so it is usable as a local
// check or in CI. Called from the Nuxt module, the error is only reported, so a typo does not
// kill a running dev server.
if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
    try {
        const count = await generateHelpDocs()
        console.log(`[help] ${count} documents generated in ${SRC_SUBDIR}/help/generated`)
    } catch (error) {
        console.error(`[help] generation failed: ${error.message}`)
        process.exit(1)
    }
}
