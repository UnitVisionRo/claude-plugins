---
name: install-help-docs
description: Use when adding in-app user help documentation to an application - a Markdown-sourced, build-time-generated help system with contextual help per screen, a searchable topic browser, reproducible screenshots and optional per-module content. Rebuilds the system in the target app's own stack rather than copying files.
disable-model-invocation: true
user-invocable: true
---

# Install in-app help documentation

## What this skill is

**A handover document, not a file-copying installer.**

`references/` holds a complete, working implementation of this help system for one stack:
Nuxt 4 + Vuetify 3, TypeScript, Vite. Read it to learn what the system does, and — more
valuable — how the awkward parts were solved. Then **build the same behaviour in the target
application's own stack**.

The reference files are where the functionality is described in the most precise language
available, which happens to be code. They are not a payload. An app built on React and Tailwind,
Svelte, Angular, Django templates or Rails gets the same system, written its own way.

**One file travels verbatim**: `references/app-skill-help-docs.md`, the authoring skill installed
into the target repository. It describes how to *write* documentation, which is the same job in
every stack, and it is what stops the documentation rotting after you leave. Adapt its paths, its
placeholders and its examples; do not rewrite its rules.

Each reference file's first line is a `Destination:` comment naming where its equivalent went
in the stack it was written for — `<appRoot>` is the directory holding the app's manifest and
build config, `<appSrc>` its source root, `<docsDir>` the documents, `<shotsDir>` the screenshots
beside them. Treat it as a hint about the file's role, not an address to obey. If you do copy a
file verbatim because the stack matches, strip that first line: it is an instruction to you, not
part of the app.

So the install has three kinds of work:

| | What to do |
|---|---|
| The **functional contract** below | Reproduce all of it. This is what "installed" means. |
| `references/*` (code) | Read, understand, rebuild in the target stack. Copy verbatim only if the stack genuinely matches. |
| `references/app-skill-help-docs.md` | Copy, adjust paths and placeholders, keep the rules. |

## The functional contract

Everything below must be true when you are done. None of it names a framework. The rest of this
document refers back to these as **contract §1** … **contract §7**; a numbered **Step** is part
of the procedure further down. A `§` belonging to a spec is always written with that spec's file
name, because the numbering is unrelated.

### 1. The documents are the source of truth

One Markdown file per screen, in `docs/help/`, kept in git, edited by developers, reviewed in
pull requests, deployed with the feature it describes. Frontmatter carries the title, the menu
group and order, a summary, and the application routes the document is the contextual help for.

No CMS, no admin UI, no database table, nothing fetched at runtime.

### 2. Generation happens at build time, and validates everything

A generator compiles the Markdown into whatever the application can import directly, and **fails
the build** on:

- a link to a document that does not exist;
- a link to a section (anchor) that does not exist — the error lists the sections that do;
- an image that is missing, has an unsupported extension, lives outside the documentation folder,
  or has no alternative text;
- a tab mapping pointing at a document or section that does not exist;
- a document with no title;
- malformed frontmatter;
- an undeclared module name (contract §6);
- outside development, a missing or empty documentation folder.

This is the system's central promise: **a broken reference is a build error, not a dead link a
user finds.** If you rebuild nothing else faithfully, rebuild this. A help system that degrades
silently is worse than none, because nobody notices it has rotted.

The generated output is **not** committed. It is produced on every build and every dev-server
start, so it can never drift from the source.

### 3. Contextual help

A Help control in the application's top bar opens the document declared for the current route,
in a dialog, without leaving the page. On a tabbed screen it opens the document — and optionally
the section — declared for the active tab. With no document for the route, it falls back to the
topic list rather than erroring.

### 4. A help page with search

A route (`/help`) listing the topics grouped as the frontmatter says, plus full-text search over
the documents' bodies with highlighted snippets, landing on the right section. The search index
is built at generation time and loaded lazily — it must not be part of the initial bundle.

### 5. Screenshots

Documents embed screenshots as ordinary Markdown images, validated like any other reference
(contract §2). They live in a folder **beside** the documents, shared between them, so one screenshot is
taken once and reused.

They are captured **reproducibly, by a script, against a demo instance with invented data** —
never by hand, and never against a working or production database. `references/capture.mjs` is a
Playwright harness doing this for the reference stack; **Step 4** covers what porting it takes.

### 6. Optional modules

Content can be marked as belonging to an optional part of the application — a module the
deployment may not have, a feature behind a licence, anything the app can compute a boolean for.
Marked content is hidden when its module is off: absent from the topic list, from search, and
from the body and outline of the document containing it.

Three rules make this safe, and all three must survive a rebuild:

- **Everything is compiled, unconditionally. Filtering happens at display time.** The flag is
  computed in the running application, so it is not knowable at build time; one build serves a
  deployment with the module on and one with it off.
- **Hidden is not private.** Hidden content is in the shipped bundle and anyone can read it with
  devtools. This is a relevance filter, not access control. Nothing confidential goes behind a
  module.
- **A reference into hidden content is a build error.** A link to a section inside a module block
  fails generation unless the link is itself inside that module, or its document belongs to that
  module. Otherwise turning a module off silently creates a dead link, which is exactly what contract §2
  exists to prevent.

Module names are declared once, in `docs/help/modules.json`. The generator validates every use
against it; the application supplies one predicate per declared name. An unknown name counts as
disabled — hiding a topic is recoverable, sending a reader to a screen that does not exist is
not.

The full design — including why there is no runtime check for a module name drifting between the
declaration and the predicates — is `docs/specs/2026-09-17-help-modules.md` §9, in this plugin's
own repository.

### 7. The authoring skill

`.claude/skills/help-docs/SKILL.md` in the target repository, from
`references/app-skill-help-docs.md`. Without it, the next person to change a screen has no reason
to think a document describes it. **It is part of the install, not an optional extra** — and it
is the part that survives you.

## Step 1 — Discover the target stack

Establish these before writing anything, and **state them back to the user**. Ask when the answer
is not in the repository; guessing here produces a system nobody can maintain.

| | What you need to know | Why it changes the build |
|---|---|---|
| Framework | React, Vue, Svelte, Angular, server-rendered templates… | Decides the components and how a route knows its document. |
| Build tool | Vite, webpack, esbuild, a bundler-less server framework… | Decides how generated output is imported and how generation hooks into dev and build. |
| Component library | Vuetify, MUI, Tailwind + headless, the app's own | Decides the dialog, list, search field and progress indicator. |
| Language | TypeScript or JavaScript | Decides whether the module contract of contract §6 is type-enforced. |
| Router | Path shapes, hash vs history, how the active route is read | Feeds the `routes:` matching and the screenshot harness. |
| Rendering | SPA, SSR, SSG | SSR needs care: the body must not be rendered on the server if filtering needs the DOM. |
| Where things live | App root, source root, documentation folder, the top bar | The paths everything else is relative to. |
| Auth | Whether a global guard would block `/help` | A protected help page bounces anonymous readers to sign-in. |
| Icons | Which set, and how icons are referenced | The reference uses Material Design Icons by name. |

If `docs/help/` would land somewhere surprising — a monorepo, an app at the repository root — ask
rather than picking. Its sibling `docs/screenshots/` follows it, because images must resolve from
the documents' parent folder (contract §2).

## Step 2 — Rebuild the contract

Work through the contract in order. For each part, read the reference file, understand the
decision, then implement it in the target stack.

| Contract | Read | Then build |
|---|---|---|
| contract §1 source, contract §2 generation | `references/generate-help.mjs` (the largest and most important file) | A generator in the project's own build language, producing whatever the app imports directly. |
| contract §2 hooking into the build | `references/help-docs-module.js` | Generation before dev-server start and before build. It must be impossible to build without it. |
| contract §3 contextual help | `references/HelpButton.vue`, `references/helpDocs.ts` | The top-bar control and route→document matching. |
| contract §4 page and search | `references/help.vue`, `references/help-slug.vue`, `references/HelpTopicList.vue`, `references/HelpSearch.vue`, `references/helpSearch.ts` | The help route, topic list, search box and ranking. |
| contract §4 rendering a document | `references/HelpContent.vue` | Rendering compiled HTML, section scrolling, intercepting internal links. |
| contract §5 screenshots | `references/capture.mjs`, `references/screenshots-readme.md` | The capture harness — see Step 4 below. |
| contract §6 modules | `references/help-modules.json`, `references/helpModules.ts`, and the module parts of the generator | Declaration, validation, and display-time filtering. |
| contract §7 authoring skill | `references/app-skill-help-docs.md` | Copy it. |
| a first document | `references/sample-getting-started.md` | One real document, so the system is exercised end to end. Fix its `routes:` to a path this app actually has — a document matching nothing makes the Help button fall back to the topic list, and the feature looks broken the first time anyone tries it. |
| types | `references/help-types.ts` | The shape of the generated data, whatever the language. |

### Decisions worth keeping in any stack

These are the non-obvious ones. They were each arrived at the hard way, and a rewrite that
discards them will rediscover the same problems.

- **Sections are addressed with a query parameter (`?s=<id>`), not a URL fragment.** The same
  link has to work inside the help *dialog*, where the browser has no anchor to scroll to. The
  content component scrolls by itself, identically on the page and in the dialog.
- **Internal links are intercepted and handed to the router**, never allowed to do a full page
  reload. Modified clicks (ctrl/cmd/shift, middle button) and `target="_blank"` are deliberately
  left alone.
- **The Markdown parser never reaches the browser.** Compilation is a build-time concern; shipping
  a parser to render content that was already known at build time is pure waste.
- **Each document is its own lazily-loaded chunk**, and the search index is another. Opening the
  help must not cost anything on first paint.
- **Generated files are not in git**, so they cannot drift from the Markdown. The corollary is
  that a missing source folder must be *fatal* outside development, or a build with no source
  silently produces an app importing something that does not exist.
- **Raw HTML is disabled in the Markdown parser.** The content is trusted, reviewed-in-PR
  material; keeping it to Markdown means rendering it is not a question of sanitising.
- **Alternative text on images is required, not encouraged.** It is what a reader who cannot see
  the screenshot gets, and a generator is the only thing that will ever enforce it.
- **An unknown module is disabled, not visible** (contract §6).

### Where the reference implementation is stack-specific

Replace these; do not try to preserve them.

- Vuetify components and classes throughout the `.vue` files, and the two theme tokens
  (`primary`, `on-surface`) their styles use.
- Nuxt's `modules/` auto-registration (`help-docs-module.js`) — any build has an equivalent hook.
- Vite's `import.meta.glob`-style dynamic imports and asset-URL handling in the generated output.
- Nuxt 4's `app/` source layout, and the `SRC_SUBDIR` / `DOCS_SUBPATH` constants that exist only
  to absorb it.
- Auto-import assumptions: the reference imports its components explicitly anyway, precisely so
  this does not matter.

## Step 3 — Install the authoring skill

Copy `references/app-skill-help-docs.md` to `.claude/skills/help-docs/SKILL.md` in the target
repository. It is a `SKILL.md`, so its frontmatter must be the file's first bytes and it carries
no `Destination:` line.

Adjust: the paths to match where things actually landed, the command names to match the project's
scripts, and the screenshot procedure's `<placeholders>` (**Step 4**). **Keep its rules** — what belongs
in a document, how screens map to documents, when to update one, the screenshot discipline, and
the module warnings. Those are what you are handing over.

## Step 4 — The screenshot harness

`references/capture.mjs` drives a real browser against a demo instance and writes one PNG per
screen, so screenshots can be *re*taken when the interface changes. A hand-taken screenshot
cannot be, which is how documentation starts lying.

It is Playwright plus roughly 200 lines of waiting logic, and it splits cleanly:

- **Portable:** the runner, the session-per-role model, per-step failure isolation with a
  diagnostic capture outside the screenshots folder, the credentials file, the fixed viewport and
  locale, and the "wait for the content to change, then to stop changing" approach to knowing a
  page is ready. That last one is the hard-won part and applies to any stack.
- **Stack-specific:** every selector. The reference keys off Vuetify's classes, hoisted into a
  `SELECTORS` block for the waiting helpers; the interaction helpers carry them inline. Routing
  mode is a constant (`HASH_MODE`), and the sign-in flow is a small config block that an app with
  SSO or a second factor must replace outright.

Install it in `<docsDir>/../screenshots/` with its **own** `package.json`
(`references/screenshots-package.json`) — Playwright is a documentation tool and has no business
in the application's dependency tree, lockfile or image. Copy
`references/screenshots-readme.md` as that folder's `README.md`: its table of "id | screen | what
must be visible" is the contract that makes a screenshot reproducible by someone who did not take
it.

**Check the mail sink**, which the demo instance procedure relies on (authoring skill, step 2).
If the skill `project-tooling:demo-mail-sink` is not in this session's skill list, or the app has no
`<back>/scripts/smtp_sink.py`, **remind the user** which is missing and how to add it — the plugin
with `claude plugin install project-tooling@bogdan-plugins --scope project` from the repository root
(then a new session), the script by copying it from that skill's directory — and offer to do the
copy. Do not report the install as done while either is missing.

Then: `.gitignore` the folder's `node_modules` and the demo credentials file;
`.dockerignore` the `node_modules` if the image ships the documentation; and fill in the demo
instance procedure in the authoring skill, by asking how a throwaway instance of this application
is built, seeded and torn down. **The harness without that procedure is inert** — it has nothing
safe to point at.

## Verification

Do not report the install as done until all of these pass. Phrase them in the project's own
commands; the substance is what matters.

**Generation**
- The generator runs clean and reports the document count.
- Generated output exists and is **not** tracked by git.
- The project's typecheck and lint gates are clean.
- The production build succeeds **and generation runs inside it** — this is the path where an
  invalid document is fatal rather than a warning.

**The check actually checks.** Point a link at a section that does not exist, regenerate, and
confirm it fails naming the file and listing the real sections — then revert. If it passes, the
wiring is wrong and contract §2's promise is not being kept. Do the same for a missing image and for an
image with no alt text.

**Behaviour**
- The help route renders the topic list and a document.
- The Help control on a documented screen opens *that* document, not the topic-list fallback.
  Getting the fallback means `routes:` does not match the real path.
- A word from a document's **body** (not its title) returns a search result with a highlighted
  snippet, and choosing it lands on the right section.
- An internal link between documents navigates without a full page reload.
- If the app has a global auth guard, decide deliberately whether `/help` is public, and **say
  which you chose**. Verify signed in either way — a bare request to a protected route returns a
  redirect and tells you nothing.

**Modules**, if the app declares any
- With the module off: its documents are absent from the topic list and search, and its blocks
  are absent from both body and outline while the rest of the document renders.
- With it on: all of the above appear.
- A name used but not declared in `modules.json` fails generation.
- A declared name with no predicate, and a predicate for an undeclared name, both fail typecheck
  in a typed language.
- An app declaring no modules behaves exactly as if the feature did not exist.

**Screenshots**, if the harness was installed
- Listing the screenshot ids works without launching a browser.
- Capturing one against the demo instance writes the PNG, and **you open it** and confirm it shows
  what the table claims. A harness that silently captures a blank page passes every automated
  check there is.
- A document embedding it still generates — this proves the image path resolves under contract §2's rules.

## Common mistakes

- **Copying the reference files because they parse.** They are a reference implementation for one
  stack. If the target is not Nuxt + Vuetify, code that runs is not the same as code that
  belongs.
- **Rebuilding the components but not the validation.** The components are the visible part and
  the easy part; contract §2 is what makes the system trustworthy, and it is invisible until it saves you.
- **Rewriting the authoring skill in your own words.** It is the handover. Adjust paths, keep
  rules.
- **Treating generation as a script someone remembers to run.** It must be impossible to build
  without it.
- **Forgetting that a dev server reads its build hooks at startup.** Adding the generation hook
  and then wondering why nothing regenerates is the single most common way to conclude, wrongly,
  that generation is broken.
- **Letting the generated output into git.** It will drift, and the drift will be invisible.
- **Documenting a screen without a screenshot** because capturing one is inconvenient. contract §5.
- **Putting anything confidential behind a module.** contract §6.

## Deliberately not included

- **No CMS, no admin UI, no database table.** The documents are code: reviewed in PRs, versioned
  with the app, deployed with the feature they describe.
- **No runtime fetching.** Everything the help system shows was known at build time, so it is
  compiled at build time.
- **No demo instance.** The harness installs and runs; what it runs *against* is the app's own
  job, because building and seeding a throwaway instance depends entirely on how the application
  is deployed and what its data looks like. The authoring skill carries the *shape* of that
  procedure — separate database, seeded through the app's real endpoints, torn down afterwards —
  with placeholders for this app's specifics, and sends the instance's outbound mail to a local
  discard sink (the one part that *is* generic: copy `smtp_sink.py` from
  `project-tooling:demo-mail-sink` into the app if it has none). Capturing
  against the working database is how real customer data ends up in published documentation, so
  the procedure is not optional, only un-generalizable.
- **No access control.** contract §6.
