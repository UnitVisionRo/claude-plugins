---
name: install-help-docs
description: Use when adding in-app user help documentation to a Nuxt + Vuetify application - a Markdown-sourced, build-time-generated help system with contextual help per page, a searchable topic browser, and an authoring skill installed into the app itself.
disable-model-invocation: true
user-invocable: true
---

# Install in-app help documentation

## Overview

Installs a complete user-facing help system into an existing Nuxt + Vuetify application:

- **Markdown in `docs/help/`** is the source of truth — one file per screen, kept in git,
  edited by developers, reviewed in PRs.
- **A build-time generator** compiles it into the app's bundle. Every link, anchor and image is
  verified while generating, so a broken reference is a build error, not a dead link in
  production.
- **Contextual help**: a Help button in the app bar opens the document declared for the current
  page (and, on tabbed pages, for the active tab), in a dialog, without leaving the page.
- **A `/help` page** with a topic list and full-text search over the documents' bodies, with
  highlighted snippets.
- **An authoring skill** written into the target app at `.claude/skills/help-docs/SKILL.md`, so
  whoever works in that repo next — human or agent — has the rules for writing the documents.

Nothing is fetched at runtime: the Markdown parser never reaches the browser, each document is
its own lazy-loaded chunk, and the search index is imported only on the first search.

## Requirements

- **Nuxt 3 or 4** with Vue 3, and **npm**.
- **Vuetify 3 or 4**, already wired in. The UI components are plain Vuetify
  (`v-card`/`v-list`/`v-dialog`/`v-text-field`/`v-menu`) using only default theme tokens
  (`primary`, `on-surface`), so they work against a bare `createVuetify()`.
- An icon set — either `@mdi/font` (string names, which is what the reference files use) or
  `@mdi/js` (imported paths, see "Adapt to the app" below).

If the app is not Nuxt, or has no Vuetify, **stop and say so** rather than porting the
components by hand — the layout and scroll behaviour are Vuetify-specific and rewriting them is
not what this skill does.

## Discover the app, then confirm

Before copying anything, establish these and **state them back to the user**:

| | How to find it | Typical |
|---|---|---|
| `<nuxtDir>` | the directory holding `nuxt.config.*` and `package.json` | `gui/`, `front/`, or the repo root |
| `<srcDir>` | `<nuxtDir>/app` if it exists (Nuxt 4), otherwise `<nuxtDir>` (Nuxt 3) | `gui/app` |
| `<docsDir>` | where the Markdown will live — the repository root's `docs/help` | `<repoRoot>/docs/help` |
| the app bar | the layout or component holding the top bar, where the Help button goes | `<srcDir>/layouts/default.vue` |
| route guard | whether a global auth middleware denies unlisted paths | see below |
| icon set | `@mdi/font` or `@mdi/js` in `package.json` | `@mdi/font` |

If `docs/help/` would land somewhere surprising (a Nuxt app at the repo root, a monorepo with
several apps), **ask** rather than picking.

## Files this skill installs

Each reference file's first line is a `Destination:` comment naming where it goes — strip that
line from the copy, it is an instruction to you, not part of the app.

| Reference | Destination |
|---|---|
| `references/generate-help.mjs` | `<nuxtDir>/scripts/generate-help.mjs` |
| `references/help-docs-module.js` | `<nuxtDir>/modules/help-docs.js` |
| `references/help-types.ts` | `<srcDir>/help/types.ts` |
| `references/helpDocs.ts` | `<srcDir>/utils/helpDocs.ts` |
| `references/helpSearch.ts` | `<srcDir>/utils/helpSearch.ts` |
| `references/HelpButton.vue` | `<srcDir>/components/help/HelpButton.vue` |
| `references/HelpContent.vue` | `<srcDir>/components/help/HelpContent.vue` |
| `references/HelpSearch.vue` | `<srcDir>/components/help/HelpSearch.vue` |
| `references/HelpTopicList.vue` | `<srcDir>/components/help/HelpTopicList.vue` |
| `references/help.vue` | `<srcDir>/pages/help.vue` |
| `references/help-slug.vue` | `<srcDir>/pages/help/[[slug]].vue` |
| `references/sample-getting-started.md` | `<docsDir>/getting-started.md` |
| `references/app-skill-help-docs.md` | `<repoRoot>/.claude/skills/help-docs/SKILL.md` |

The last one is the exception: it is a `SKILL.md`, so its frontmatter must be the file's first
bytes and it carries **no** `Destination:` line. Copy it verbatim, then replace the
`<nuxtDir>` / `<srcDir>` placeholders in it with the app's real paths.

## Steps

1. **Discover and confirm** the table above. Do not create files before the user has agreed to
   `<nuxtDir>` and `<docsDir>`.

2. **Install the generator's dependencies** — from `<nuxtDir>`, through npm, never by
   hand-editing `package.json`:
   ```bash
   npm install -D markdown-it gray-matter @types/markdown-it
   ```
   They are dev dependencies on purpose: they run at build time and never ship to the browser.

3. **Copy the reference files** to the destinations above, stripping each `Destination:` first
   line.

4. **Adjust the generator's two layout constants**, at the top of
   `<nuxtDir>/scripts/generate-help.mjs`:
   - `SRC_SUBDIR` — `'app'` on Nuxt 4 (the default in the file), `'.'` on Nuxt 3.
   - `DOCS_SUBPATH` — `'../docs/help'` when the Nuxt app is a subdirectory of the repository
     (the default), `'docs/help'` when Nuxt *is* the repository root.

   Verify by running the generator (step 9) — a wrong value fails loudly with the path it tried.

   **The Nuxt 4 / subdirectory combination is the one these files were built and verified
   against.** The Nuxt 3 and root-level variants follow from the same two constants but have not
   been run; on those layouts, check where the output actually lands before trusting the
   `.gitignore` and ESLint paths below, which assume the Nuxt 4 `app/` prefix.

5. **Add the npm script** to `<nuxtDir>/package.json`:
   ```json
   "help:generate": "node scripts/generate-help.mjs"
   ```
   Nothing needs adding to `nuxt.config.ts`: Nuxt auto-registers everything in `modules/`, which
   is what runs generation before `dev` and `build`.

6. **Ignore the generated output** — append to `<nuxtDir>/.gitignore`:
   ```
   # Generated help documentation (built from docs/help by scripts/generate-help.mjs)
   app/help/generated
   ```
   (`help/generated` without the `app/` prefix on Nuxt 3.)

   If the project uses ESLint, also exclude it there — generated TypeScript is not code anyone
   authored, and a lint gate will fail on it. With `@nuxt/eslint`'s flat config that is an
   `ignores` entry alongside any existing one:
   ```js
   export default withNuxt().append({
       ignores: ['app/help/generated/**'],
   })
   ```

7. **Put the Help button in the app bar.** In the layout holding the top bar, import and place
   it — usually just before the user menu or sign-out button:
   ```vue
   <HelpButton />
   ```
   ```ts
   import HelpButton from '~/components/help/HelpButton.vue'
   ```
   The import is explicit so this works whether or not the app has component auto-import
   configured, and regardless of any `pathPrefix` setting (which would otherwise name the
   component `HelpHelpButton`).

8. **Make `/help` reachable.** If the app has a global auth middleware that **denies unlisted
   paths**, `/help` is protected by default and will bounce an anonymous visitor to the sign-in
   page. Decide deliberately:
   - documentation for signed-in operators → leave it protected (the usual answer);
   - documentation that should be readable before signing in → add `/help` to the public list
     (in the scaffold's layout, `<srcDir>/utils/routeAccess.ts`).

   Say which you chose. Either way the verification below must be done **signed in** — a bare
   `curl /help` on a protected route returns a redirect and tells you nothing.

9. **Create the first document and generate.** Copy the sample to `<docsDir>/getting-started.md`
   and **fix its `routes:` to a real path of this application** (`/` is a safe default, but if
   the app's root redirects, point it at a real page instead). A document whose `routes:` match
   nothing makes the Help button fall back to the topic list, and the feature looks broken the
   first time anyone tries it.

   `docs/help/` must not be empty: outside dev, a missing source folder is a **fatal** build
   error, by design — the generated files are not in git, so a build with no source would
   otherwise produce an app that imports something that does not exist.

   ```bash
   cd <nuxtDir> && npm run help:generate
   ```

10. **Restart the dev server** if one is running. `modules/help-docs.js` is read at Nuxt
    **startup**; HMR will not pick up a newly added module, and you will conclude generation is
    broken when it is not.

## Verification

Don't report the install as done until all of these pass:

- `npm run help:generate` exits 0 and reports the document count.
- `<srcDir>/help/generated/manifest.ts` and `search-index.ts` exist and are **not** tracked by
  git (`git status --porcelain <srcDir>/help/generated` is empty).
- `npm run typecheck` and `npm run lint` (whichever the project has) are clean.
- **Signed in**, `/help` renders the topic list on the left and the sample document on the
  right.
- The **Help button** on the page named in the sample's `routes:` opens the dialog showing that
  document — not the "no dedicated guide" topic-list fallback. Getting the fallback means
  `routes:` does not match the real path.
- `npm run build` succeeds, and generation runs inside it (the module's line appears in the build
  log). This is the path where an invalid document is **fatal** rather than a warning.
- A word from the **body** of the sample document (not its title) typed into the search returns
  a result with a highlighted snippet, and choosing it lands on the right section.
- An **in-document link** (the sample's `[Searching](#searching)`) navigates without a full page
  reload.
- **The check actually checks.** Temporarily change that link to `#no-such-section`, run
  `npm run help:generate`, and confirm it exits non-zero naming the file and listing the
  available sections — then revert. This is the whole point of generating at build time; if it
  passes, the wiring is wrong.

## Common mistakes

- **Not restarting the dev server** after adding `modules/help-docs.js`. Nuxt registers modules
  at startup only.
- **Leaving `SRC_SUBDIR`/`DOCS_SUBPATH` at their defaults on a Nuxt 3 app or a root-level Nuxt
  app.** The generator then writes into a folder nothing imports, or cannot find the source.
- **Committing `help/generated/`.** It is derived output, rebuilt on every `dev` and `build`; in
  git it only produces merge conflicts nobody can resolve meaningfully.
- **Using `@mdi/js` icon names as strings.** If the app imports icon *paths* (`import {
  mdiHelpCircleOutline } from '@mdi/js'`), then `icon="mdi-help-circle-outline"` renders
  nothing. Swap the three icons in `HelpButton.vue` and the one in `HelpSearch.vue` to
  `:icon="mdiHelpCircleOutline"` style with the matching imports.
- **Assuming a custom theme token exists.** The stylesheets deliberately use only
  `--v-theme-primary` and `--v-theme-on-surface` (with alpha for borders and shading). If you
  swap in the app's own palette, check the token is actually defined — an undefined one
  resolves to nothing and fails silently.
- **Writing an anchor as a real `#fragment` in the generated HTML.** Sections are addressed with
  `?s=<id>` so the same link works inside the help dialog, where the browser has no anchor to
  scroll to. `HelpContent.vue` does the scrolling itself, identically on the page and in the
  dialog.
- **Letting internal links do a full page reload.** The generator rewrites them to plain paths,
  so `HelpContent.vue` intercepts the click and hands it to the router. Modified clicks
  (ctrl/cmd/shift, middle button) and `target="_blank"` links are deliberately left alone.
- **Forgetting the app-level skill.** `.claude/skills/help-docs/SKILL.md` is what stops the
  documentation rotting: without it, the next person to change a screen has no reason to think
  a document describes it. It is part of the install, not an optional extra.

## Deliberately not installed

- **No CMS, no admin UI, no database table.** The documents are code: reviewed in PRs, versioned
  with the app, and deployed together with the feature they describe.
- **No per-document visibility or feature flags.** Hiding a topic behind a runtime setting needs
  a settings surface that varies by app. The generator has one hook for it if it is ever needed
  — labelling content and filtering it at display time — but shipping it unused would be dead
  code in every app that installs this.
- **No screenshot capture tooling.** Capturing depends entirely on how the app is run and
  seeded. The generator validates images strictly (path, existence, extension, alt text,
  unique names) and the authoring skill states the rule; producing them is the app's own job.
