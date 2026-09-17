// Destination: <shotsDir>/capture.mjs
// Screenshot capture for the user-facing help documentation.
//
// The documents in `<docsDir>` embed screenshots as `![alt](../screenshots/<id>.png)` -- which
// resolves to this folder, a sibling of the documents'. This script produces those PNGs by
// driving the real application in a browser, so a screenshot is a reproducible artefact of a
// known dataset rather than something taken by hand once and never retakeable. Every screenshot
// is one entry in the STEPS list at the bottom of this file and one row in `README.md` beside it.
//
// What this needs:
//   - Playwright, installed in THIS folder (see `package.json`), not in the app's -- the
//     browser driver has no business in the application's dependency tree or Docker image;
//   - a running instance of the application, with the demo dataset loaded;
//   - Vuetify, assumed throughout. The SELECTORS block below covers the waiting helpers; the
//     interaction helpers (`pickFromField`, `openTab`, `tooltipButton`) carry Vuetify's classes
//     inline, so another component library means editing those bodies, not just the config.
// Nuxt is NOT required. This script only ever talks to the application over HTTP.
//
// NEVER run this against the working development database, and never against production:
// whatever is on screen is published with the documentation. Screenshots are taken on the demo
// instance -- see the "Screenshots" section of the app's help-docs authoring skill.
//
// Install (once, in this folder):
//     npm install && npx playwright install chromium
//
// Run:
//     node capture.mjs                         # every screenshot
//     node capture.mjs --only dashboard,login  # a few
//     node capture.mjs --list                  # just the ids
//
// Environment (all optional):
//     SCREENSHOTS_BASE_URL   the demo interface's address    (default https://localhost:3000)
//     SCREENSHOTS_CREDS      the demo users file             (default `.claude/.secrets-demo`
//                            at the repository root, git-ignored)
//     SCREENSHOTS_ADMIN_USER / SCREENSHOTS_ADMIN_PASS    the administrator
//
// The credentials file holds `key: value` lines (`login`, `password`, `base`, then
// `user: password` for any other role a screenshot needs). Passwords never reach the log.

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Playwright is this folder's dependency, declared in its own `package.json`.
import { chromium } from 'playwright'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const OUT_DIR = HERE

// `<shotsDir>` -> the repository root, two levels up. Adjust if the documentation folder does
// not sit directly under the repository root.
const REPO_ROOT = path.resolve(HERE, '..', '..')
const DEFAULT_CREDS = path.join(REPO_ROOT, '.claude', '.secrets-demo')

// ── What to edit for your application ──────────────────────────────────────────────────

// Every screenshot is taken at this size, unscaled, so the images look like one set.
const VIEWPORT = { width: 1440, height: 900 }
const COLOR_SCHEME = 'light'
const LOCALE = 'en-US'
const TIMEZONE = 'UTC'

// `true` when the router is in hash mode (`/#/clients`), `false` for history mode
// (`/clients`), which is the default for a Nuxt application.
//
// This is not cosmetic. A hash change fires no navigation event, so in hash mode `goto()` has
// to prove the page changed by watching the content region's text; in history mode a real
// navigation happens and Playwright can wait for it. UNVERIFIED: the history-mode branch is
// written for this plugin but has not been exercised against a real app -- the hash-mode path
// is the one that has produced screenshots in anger. Report anything that misbehaves.
const HASH_MODE = false

// The application's structure, as the waiting helpers see it. These are Vuetify's own classes.
const SELECTORS = {
    // Present once the framework has mounted -- the signal that the app loaded at all.
    app: '.v-application',
    // The content region. Its text is the reference for "the page has actually changed".
    main: '.v-main',
    // An open dialog, menu or tooltip.
    overlay: '.v-overlay--active',
    // The card inside an open dialog.
    dialog: '.v-overlay--active .v-card',
    // Anything that says the page is still loading. While one of these is on screen the
    // screenshot would capture a skeleton instead of the data.
    busy: '.v-skeleton-loader, .v-progress-circular--indeterminate, .v-progress-linear--active',
    // The close button in a dialog's title bar. If the app's dialogs close through a button
    // identified some other way (a localized `title` attribute, an icon name), add it here as
    // an extra comma-separated selector; `closeOverlays` falls back to Escape and then to a
    // reload, so this is an optimisation rather than a requirement.
    dialogClose: '.v-overlay--active .v-card-title button',
}

// The login screen, as `login()` drives it. Regexes, so they survive wording changes and
// translations. An application with SSO, a redirect to an identity provider or a second factor
// cannot be configured through these: replace the body of `login()` instead.
const LOGIN = {
    route: '/login',
    userLabel: /user|e-?mail/i,
    passLabel: /password/i,
    submitName: /sign in|log ?in|continue/i,
}

// Written into localStorage before the first paint of every session, so that state the
// application remembers per user does not differ from one screenshot to the next. The usual
// case is the navigation drawer: it remembers whether the user collapsed it, and it must look
// the same in all the images. For an app that stores it under `sideBar`, that is:
//     sideBar: JSON.stringify({ expandOnHover: true, mini: false }),
const INIT_LOCAL_STORAGE = {}

// Development overlays that must not appear in the documentation. Harmless when absent.
const HIDE_DEVTOOLS_CSS = `
    #nuxt-devtools-container, #nuxt-devtools-anchor, nuxt-devtools-inspect-panel,
    #vue-tracer-overlay, [class^="nuxt-devtools"], [class*=" nuxt-devtools"] {
        display: none !important;
    }
`

// ── Configuration ──────────────────────────────────────────────────────────────────────

/** Reads the credentials file: `key: value` per line, comments start with `#`. */
function readCreds(file) {
    const values = {}
    if (!fs.existsSync(file)) return values
    for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
        const match = /^\s*([^#\s:][^:]*)\s*:\s*(.+?)\s*$/.exec(line)
        if (match) values[match[1].trim()] = match[2]
    }
    return values
}

const creds = readCreds(process.env.SCREENSHOTS_CREDS ?? DEFAULT_CREDS)
const BASE = (process.env.SCREENSHOTS_BASE_URL ?? creds.base ?? 'https://localhost:3000').replace(/\/$/, '')
const ADMIN = {
    user: process.env.SCREENSHOTS_ADMIN_USER ?? creds.login ?? 'admin',
    pass: process.env.SCREENSHOTS_ADMIN_PASS ?? creds.password ?? creds.pass,
}

// ── Navigation and waiting ─────────────────────────────────────────────────────────────

/** The address of an in-app route, in whichever routing mode the app uses. */
function routeUrl(route) {
    return HASH_MODE ? `${BASE}/#${route}` : `${BASE}${route}`
}

/** The route currently displayed, read back from the browser's address. */
function currentRoute(url) {
    const parsed = new URL(url)
    return (HASH_MODE ? parsed.hash.replace(/^#/, '') : parsed.pathname) || '/'
}

async function newContext(browser) {
    const context = await browser.newContext({
        viewport: VIEWPORT,
        deviceScaleFactor: 1,
        ignoreHTTPSErrors: true,
        colorScheme: COLOR_SCHEME,
        locale: LOCALE,
        timezoneId: TIMEZONE,
    })
    await context.addInitScript(({ css, storage }) => {
        try {
            for (const [key, value] of Object.entries(storage)) localStorage.setItem(key, value)
        } catch { /* private mode, no localStorage */ }
        const inject = () => {
            const style = document.createElement('style')
            style.textContent = css
            document.head?.appendChild(style)
        }
        if (document.head) inject()
        else document.addEventListener('DOMContentLoaded', inject)
    }, { css: HIDE_DEVTOOLS_CSS, storage: INIT_LOCAL_STORAGE })
    context.setDefaultTimeout(30000)
    return context
}

/**
 * Loads the interface at a route, retrying past the dev server's "Failed to fetch dynamically
 * imported module" -- a cold Vite server can lose the first request for a lazy chunk.
 */
async function loadApp(page, route) {
    for (let attempt = 1; attempt <= 4; attempt++) {
        try {
            await page.goto(routeUrl(route), { waitUntil: 'domcontentloaded', timeout: 45000 })
            await page.waitForSelector(SELECTORS.app, { timeout: 20000 })
            return
        } catch (error) {
            if (attempt === 4) throw error
            await page.waitForTimeout(1500)
        }
    }
}

/**
 * Navigates to a route and waits for the target page's content.
 *
 * In hash mode the route is changed in place: no navigation event fires, and the title in the
 * top bar changes before the content does, so neither `networkidle` nor the title is a valid
 * signal -- the content region's text has to change and then stay unchanged. In history mode a
 * real navigation happens and a plain load is both simpler and more reliable.
 */
async function goto(page, route, anchor, { force = false } = {}) {
    await closeOverlays(page)
    const onApp = page.url().startsWith(BASE)
    const sameRoute = onApp && currentRoute(page.url()) === route
    let previous = null

    if (!onApp || force || (!sameRoute && !HASH_MODE)) {
        await loadApp(page, route)
    } else if (!sameRoute) {
        previous = await mainText(page)
        await page.evaluate((r) => { window.location.hash = r }, route)
    }

    await waitForPageContent(page, previous)
    if (anchor) await page.locator(anchor).first().waitFor({ state: 'visible', timeout: 30000 })
    await settle(page)
}

/** The content region's text, used as the reference for a page change. */
async function mainText(page) {
    return page.evaluate((selector) => (document.querySelector(selector)?.innerText ?? '').trim(), SELECTORS.main)
}

/** Waits for the content: first to differ from the previous page, then to stop changing. */
async function waitForPageContent(page, previous) {
    await page.waitForFunction(({ prev, selector }) => {
        const main = document.querySelector(selector)
        if (!main) return false
        const text = (main.innerText ?? '').trim()
        if (text.length < 20) return false
        return prev === null || text !== prev
    }, { prev: previous, selector: SELECTORS.main }, { timeout: 30000 }).catch(() => {})

    let last = null
    for (let i = 0; i < 25; i++) {
        const text = await mainText(page)
        if (text === last) return
        last = text
        await page.waitForTimeout(400)
    }
}

/** Waits for loading to finish: no skeletons, no progress indicators. */
async function settle(page) {
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {})
    await page.waitForFunction(
        (selector) => document.querySelectorAll(selector).length === 0,
        SELECTORS.busy,
        { timeout: 20000 },
    ).catch(() => {})
    await page.waitForTimeout(400)
}

/** Closes anything left open, so each screenshot starts from a clean page. */
async function closeOverlays(page) {
    if (!page.url().startsWith(BASE)) return
    for (let i = 0; i < 4; i++) {
        if (await page.locator(SELECTORS.overlay).count() === 0) return
        const closeButton = page.locator(SELECTORS.dialogClose).last()
        if (await closeButton.count() > 0 && await closeButton.isVisible().catch(() => false)) {
            await closeButton.click({ timeout: 3000 }).catch(() => {})
        } else {
            await page.keyboard.press('Escape')
        }
        await page.waitForTimeout(350)
    }
    // A "persistent" dialog ignores both Escape and a click outside it; a reload always closes it.
    if (await page.locator(SELECTORS.overlay).count() > 0) {
        await loadApp(page, currentRoute(page.url()))
        await waitForPageContent(page, null)
    }
}

/** Waits for an open dialog to finish its opening animation. */
async function dialogOpen(page, inside) {
    await page.locator(SELECTORS.dialog).first().waitFor({ state: 'visible' })
    if (inside) await page.locator(inside).first().waitFor({ state: 'visible' })
    await settle(page)
    await page.waitForTimeout(400)
}

/** Writes the screenshot -- the visible window only, as the user sees it. */
async function shot(page, id) {
    await page.waitForTimeout(200)
    await page.screenshot({ path: path.join(OUT_DIR, `${id}.png`), animations: 'disabled' })
}

/** Signs in on the login screen. See LOGIN above; SSO or a second factor belongs here instead. */
async function login(page, account) {
    await loadApp(page, LOGIN.route)
    await page.getByLabel(LOGIN.userLabel).first().fill(account.user)
    await page.getByLabel(LOGIN.passLabel).first().fill(account.pass)
    await page.getByRole('button', { name: LOGIN.submitName }).first().click()
    await page.waitForFunction(
        (route) => !location.href.includes(route),
        LOGIN.route,
        { timeout: 30000 },
    )
    await settle(page)
}

// ── Interacting with the page ──────────────────────────────────────────────────────────

/**
 * Finds a button by the text of its tooltip.
 *
 * Some component libraries turn a `title` property into a tooltip component, so the buttons
 * carry no `title` attribute in the DOM and there is nothing to match on. The only way left is
 * to hover them in turn and read the tooltip that appears. Slow -- use it only where a button
 * cannot be reached by role, name or position.
 */
async function tooltipButton(page, scope, wanted) {
    const matches = (text) => (wanted instanceof RegExp ? wanted.test(text) : text === wanted)
    const buttons = scope.locator('button')
    const total = await buttons.count()
    for (let i = 0; i < total; i++) {
        const button = buttons.nth(i)
        if (!await button.isVisible().catch(() => false)) continue
        await button.hover({ timeout: 5000 }).catch(() => {})
        await page.waitForTimeout(220)
        const text = (await page.locator('.v-tooltip.v-overlay--active .v-overlay__content').first()
            .innerText().catch(() => '')).trim()
        if (matches(text)) return button
    }
    throw new Error(`No button found whose tooltip is "${wanted}".`)
}

/** Picks a value in a Vuetify select / autocomplete identified by its label. */
async function pickFromField(page, root, label, optionText, { search } = {}) {
    // A required field's label ends with "*". Playwright's selector syntax consumes one level
    // of escaping, hence the doubled backslashes.
    const field = root.locator(`.v-input:has(label:text-matches("^${label}\\\\s*\\\\*?$"))`).first()
    await field.click()
    if (search) {
        // Fields that search on the server show no options until something is typed.
        await field.locator('input').first().fill(search)
        await page.waitForTimeout(1200)
    }
    const options = page.locator(`${SELECTORS.overlay} .v-list-item`)
    const option = (optionText ? options.filter({ hasText: optionText }) : options).first()
    await option.waitFor({ state: 'visible' })
    await option.click()
    await page.waitForTimeout(400)
}

/** Opens the named tab of a detail page. */
async function openTab(page, name) {
    await page.locator('.v-tab').filter({ hasText: name }).first().click()
    await settle(page)
}

// ── Preparing data through the API ─────────────────────────────────────────────────────
//
// Some screenshots need a state the demo dataset does not contain -- a record in a particular
// condition, an empty list, a button that only appears once something else exists. Prepare it
// through the same endpoints the interface uses, never by clicking it in by hand: a step
// prepared this way can be re-run (`--only <id>`) any number of times without duplicating
// anything, and the dataset stays rebuildable from scratch. The session's cookies are already
// on `context.request`, so the calls are authenticated.
//
// A helper of this shape, called from the step that needs it:
//
//     async function ensureDemoRecord(context) {
//         const call = async (method, url, data) => {
//             const response = await context.request.fetch(`${BASE}/api${url}`, { method, data })
//             if (!response.ok()) throw new Error(`${method} ${url} -> ${response.status()}`)
//             const body = await response.text()
//             return body ? JSON.parse(body) : null
//         }
//         const found = await call('GET', '/widgets?search=Example')
//         if (found?.items?.length) return found.items[0].id
//         await call('POST', '/widgets', { name: 'Example', ... })
//         return (await call('GET', '/widgets?search=Example')).items[0].id
//     }
//
// If a screenshot needs data the demo set does not have, prefer extending the seed script over
// preparing it here: the set is what every other screenshot is taken against.

// ── The screenshots ────────────────────────────────────────────────────────────────────
//
// One entry per screenshot, each independent: if one fails the rest are still taken. `id` is
// the file name (`<id>.png`) and the key into the table in `README.md`. `ctx` picks the
// session -- `admin` by default, `anon` for screens seen while signed out, or any other name
// for a second role, which `session()` below must be taught to sign in.
//
// Replace the two examples with the application's own list.

const STEPS = [
    {
        id: 'login', ctx: 'anon',
        async run(page) {
            await loadApp(page, LOGIN.route)
            await page.getByLabel(LOGIN.userLabel).first().waitFor({ state: 'visible' })
            await settle(page)
            await shot(page, 'login')
        },
    },
    {
        id: 'dashboard',
        async run(page) {
            await goto(page, '/', `${SELECTORS.main} .v-card`)
            await shot(page, 'dashboard')
        },
    },
]

// ── Running ────────────────────────────────────────────────────────────────────────────

function parseArgs(argv) {
    const options = { only: null, list: false }
    for (let i = 0; i < argv.length; i++) {
        if (argv[i] === '--only') options.only = (argv[++i] ?? '').split(',').map((s) => s.trim()).filter(Boolean)
        else if (argv[i].startsWith('--only=')) options.only = argv[i].slice(7).split(',').map((s) => s.trim())
        else if (argv[i] === '--list') options.list = true
    }
    return options
}

async function main() {
    const options = parseArgs(process.argv.slice(2))
    if (options.list) {
        for (const step of STEPS) console.log(step.id)
        return 0
    }
    if (!ADMIN.pass) {
        throw new Error('No administrator password (credentials file or SCREENSHOTS_ADMIN_PASS).')
    }

    fs.mkdirSync(OUT_DIR, { recursive: true })
    const steps = options.only ? STEPS.filter((s) => options.only.includes(s.id)) : STEPS
    const unknown = (options.only ?? []).filter((id) => !STEPS.some((s) => s.id === id))
    if (unknown.length) console.warn(`unknown screenshots: ${unknown.join(', ')}`)

    const browser = await chromium.launch()
    const sessions = {}
    const results = []

    /** Opens the session a step asks for, once. Add a branch here for each extra role. */
    const session = async (name) => {
        if (sessions[name]) return sessions[name]
        const context = await newContext(browser)
        const page = await context.newPage()
        if (name === 'admin') await login(page, ADMIN)
        sessions[name] = { context, page }
        return sessions[name]
    }

    for (const step of steps) {
        const name = step.ctx ?? 'admin'
        process.stdout.write(`... ${step.id} `)
        try {
            const { page, context } = await session(name)
            await step.run(page, context)
            console.log('ok')
            results.push([step.id, 'ok'])
        } catch (error) {
            console.log(`FAILED ${error.message.split('\n')[0]}`)
            // A diagnostic capture, written outside the screenshots folder so it can never be
            // mistaken for one and committed.
            await sessions[name]?.page.screenshot({ path: path.join(os.tmpdir(), `failed-${step.id}.png`) })
                .catch(() => {})
            results.push([step.id, `error: ${error.message.split('\n')[0]}`])
            const failed = sessions[name]
            if (failed) await closeOverlays(failed.page).catch(() => {})
        }
    }

    await browser.close()

    const failures = results.filter(([, status]) => status !== 'ok')
    console.log(`\n${results.length - failures.length}/${results.length} screenshots taken`)
    for (const [id, status] of failures) console.log(`  ${id}: ${status}`)
    return failures.length ? 1 : 0
}

main().then((code) => process.exit(code), (error) => {
    console.error(error)
    process.exit(1)
})
