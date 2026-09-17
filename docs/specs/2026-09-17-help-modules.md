# Conditional help content ("help modules")

**Date:** 2026-09-17
**Status:** implemented in the reference implementation (Nuxt + Vuetify), 2026-09-17
**Affects:** `help-docs` plugin — `skills/install-help-docs/`

**Note on §10 and §11.** After this design was approved, the plugin was reframed: it is a handover
document whose `references/` are a reference *implementation* to rebuild from, not files to copy
into every app. The design itself is unaffected — it never named a framework — but §10 now reads as
"what changed in the reference implementation", and §11's installer steps are folded into the
functional contract in `SKILL.md` rather than a file-mapping table.

## 1. Problem

The help system installs the same documentation into every deployment of an application. An
application with optional parts — a GDPR module, a billing integration, a feature sold
separately — therefore documents features some of its users do not have. The reader is told
about a screen that does not exist for them.

`SKILL.md` currently lists this as deliberately not installed, on the grounds that hiding a
topic "needs a settings surface that varies by app". That objection is real but narrower than it
looks: only the *predicate* varies by app. Everything else — the authoring syntax, the
validation, the filtering — is the same everywhere.

The feature exists and is in production in `pool_flow` (`docs/help/`, five documents use it).
This spec ports it, generalised.

## 2. Decisions

| Decision | Choice | Why |
|---|---|---|
| Install scope | Always installed, inert by default | An app that declares no modules behaves exactly as today. One code path to maintain, and an author can reach for it without reinstalling. |
| What drives a flag | Any predicate the app can compute | Covers a backend setting, a user role, a licence tier or a build flag. The plugin never learns what is behind it. |
| Where predicates live | A new app-owned file, `helpModules.ts` | Keeps every other installed file copy-verbatim, so a plugin update can re-copy them without destroying the app's wiring. |
| When filtering happens | Runtime only | See §3. |
| Where names are declared | `docs/help/modules.json`, once | `pool_flow` lists them twice — in the generator and at runtime — and nothing notices when they diverge. |
| How drift is prevented | The generator emits a union type; predicates are typed against it | Drift becomes a compile error rather than something to detect at runtime. |

## 3. The invariant

**The generator compiles everything, unconditionally. Module state only ever affects display.**

Every document and every `:::module` block is parsed, validated, compiled and emitted into the
bundle regardless of any module's state. Nothing is omitted at build time. The runtime decides
what to show.

This is deliberate, and it follows from §2: the flag is computed in the browser — from a backend
setting, from the signed-in user's role — so it is not knowable when the bundle is built. The
same build serves a deployment with the module on and one with it off, and flipping a backend
setting takes effect without regenerating the documentation.

**Consequence, stated plainly: this is not access control.** Hidden content is present in the
shipped bundle and can be read by anyone willing to open devtools. It is a relevance filter, not
a security boundary. Documentation that must not be read by a class of user cannot be protected
this way — do not put anything confidential behind a module. §11 requires this to be said in the
authoring skill too, where the person choosing to use a module will actually read it.

## 4. Authoring

Two levels, both optional.

**A whole document** belongs to a module through its frontmatter:

```markdown
---
title: GDPR requests
module: gdpr
---
```

**A passage within a document** belongs to a module through a fenced block:

```markdown
:::module gdpr
This paragraph, and the heading above it, only appear when the GDPR module is on.
:::
```

Blocks do not nest — a module inside a module has no meaning and would make filtering
ambiguous. Generation fails on a nested block, on an unclosed block, and on a module name the
generator does not know (§7).

## 5. Data model

Three optional fields, all defaulting to "always visible" when absent:

- `HelpDocMeta.module?: string` — the document's module.
- `HelpHeading.module?: string` — set when the heading sits inside a `:::module` block, so a
  disabled section leaves the outline as well as the body. **A heading inherits the block's
  module only, never the containing document's**: a heading in a document marked `module: gdpr`
  keeps `module: undefined`. The two are separate facts, and §7 rule 3 consults both — collapsing
  them would make that rule reject a legal link between two sections of the same module-marked
  document.
- `HelpSearchEntry.module?: string` — so search cannot surface hidden content (§8).

The manifest gains one more export:

- `type HelpModuleName` — the declared names from `docs/help/modules.json` (§7) as a union
  (`'gdpr' | 'billing'`), or `never` when none are declared. This is what makes the predicates in
  §6.1 checkable; see §9.

A type and not a value: nothing at runtime needs the list of names. `isHelpModuleEnabled` looks a
name up in `helpModuleFlags` and treats a miss as disabled (§6.2), so the names reach the bundle
only as the keys the application itself wrote.

A `:::module` block compiles to `<div data-help-module="<name>">`, which is what the runtime
looks for.

## 6. Runtime

### 6.1 `helpModules.ts` — the app's file

New reference file, installed at `<srcDir>/utils/helpModules.ts`, shipped empty:

```ts
import type { HelpModuleName } from '~/help/generated/manifest'

export const helpModuleFlags: Record<HelpModuleName, () => boolean> = {}
```

The type is what ties this file to the declaration in `docs/help/modules.json` (§9). With nothing
declared, `HelpModuleName` is `never`, `Record<never, …>` is `{}`, and the empty object above is
correct — the inert default of §2 costs nothing and still type-checks.

This is the **one** installed file an application is expected to edit. It is where an app writes,
for example:

```ts
import type { HelpModuleName } from '~/help/generated/manifest'
import { useRootStore } from '~/store'

export const helpModuleFlags: Record<HelpModuleName, () => boolean> = {
    gdpr: () => useRootStore().appSettings?.use_gdpr === true,
}
```

Each predicate is called during rendering, not cached, so whatever reactive source it reads is
tracked by the surrounding computed — a Pinia getter, a composable, a `useState`. Predicates
must therefore be cheap and side-effect free.

### 6.2 `helpDocs.ts` — filtering

- `isHelpModuleEnabled(module?: string): boolean` — `true` when `module` is absent. Otherwise
  looks the name up in `helpModuleFlags` and calls it. **An unknown name counts as disabled**:
  hiding a topic is recoverable, pointing a reader at a screen that does not exist is not.
- `visibleHelpDocs(): HelpDocMeta[]` — `helpDocs` minus disabled modules. Every existing
  consumer inside this file switches to it: `findHelpDoc`, `resolveHelpSlug`,
  `groupedHelpDocs`, `findHelpDocForPath`. `helpDocs` itself stays exported and unfiltered.
- `filterHelpModuleBlocks(html: string): string` — removes `[data-help-module]` elements whose
  module is disabled, by parsing into a `<template>` and walking the DOM. Safe because the HTML
  is our own, compiled at build time with raw HTML disabled in the parser.

**SSR guard.** `filterHelpModuleBlocks` needs `document`, which does not exist when Nuxt renders
on the server, so it returns its input unchanged when `document` is undefined.

In practice that branch is unreachable, and the reason is worth recording so nobody later
"simplifies" it away or panics about hydration. `HelpContent.vue` renders the body only when
`loading` is false; `load()` sets `loading.value = true` synchronously, before its first `await`,
and is invoked from a `watch(..., { immediate: true })` during setup. The server therefore always
renders the progress branch, never the `v-html` body, and the client hydrates from the same
initial state. The body — and so the filter — only ever runs in the browser, after mount. The
guard is defensive, not load-bearing, and stays because an unguarded `document` reference in a
utility is a trap for whoever calls it next.

### 6.3 Components

`HelpContent.vue` renders `filterHelpModuleBlocks(html)` through a computed rather than `html`
directly. No other component changes: the topic list and the Help button already read through
`helpDocs.ts`, so they inherit the filtering.

## 7. Build-time validation

The valid module names are declared in **`docs/help/modules.json`**, a JSON array of strings
that ships containing `[]`:

```json
["gdpr"]
```

This file is the single source of truth for module names (§9). It sits with the documents it
governs, because it is edited by whoever writes documentation, not only at install time. The
generator reads it with `fs`, so none of the import restrictions that separate a build script
from application code apply. A missing file is treated as `[]`, so an installation that predates
this feature keeps working; a file that is not an array of strings fails generation, naming the
file. When collecting documents the generator filters on the `.md` extension, so a `.json`
sitting beside them is not mistaken for one.

It fails generation on:

1. **An undeclared module name**, in frontmatter or in a `:::module` opener — the message names
   the offending document and lists the declared names. A typo silently hides a document
   otherwise, because unknown means disabled (§6.2). Generation runs on every dev server start
   and every build, so this always fires.
2. **A nested or unclosed `:::module` block.**
3. **A link into module content from outside it** — a link to a section that lives inside
   `:::module X` is an error unless the link itself is inside `:::module X`, or the linking
   document is marked `module: X`. Without this, switching a module off produces a live link to
   a section that is no longer rendered.
4. **A tab whose help document belongs to a module** — a tab is always visible, so its help must
   be too.

Rules 3 and 4 are the reason this feature is worth porting properly rather than approximating.
The help system's central promise is that a broken reference is a build error rather than a dead
link in production; these two rules extend that promise to conditional content. They are ported
from `pool_flow`'s generator, where they already exist.

## 8. Search

`helpSearch.ts` skips entries whose module is disabled, at query time rather than index build
time — the index is shared by every user and every deployment of the same build.

A section inside a `:::module` block inherits that module in the index, so a disabled passage is
unreachable through search even though the document containing it is visible.

## 9. One list, enforced by types

`docs/help/modules.json` declares the names. Everything else derives from it:

- the **generator** validates every `module:` and every `:::module` against it (§7 rule 1);
- the **manifest** re-exports them as the union `HelpModuleName` (§5);
- the **predicates** are typed `Record<HelpModuleName, () => boolean>` (§6.1).

There is therefore no second list to drift from the first, and no runtime check is needed to
detect drift, because the two ways of getting it wrong are both compile errors:

- a declared module with **no predicate** — `Record` is exhaustive, so the missing key fails
  `npm run typecheck`, naming the module;
- a predicate for an **undeclared** module — an excess key against `Record<HelpModuleName, …>`,
  which fails the same way.

This is what the earlier draft of this spec tried to approximate with a development-time console
warning comparing two independently maintained lists. Deriving one from the other is both simpler
and stricter: the warning could be missed, a type error cannot, and there is now no state in
which the lists *can* disagree.

Note the division of labour, since it decides which failure an author sees. Only the generator
can catch a **typo in a document**, because only it reads the documents; it does so on every dev
start and build, whether or not the project has a typecheck gate. Only the type system can catch
a **mismatch between the declaration and the predicates**, and that check requires
`npm run typecheck` to actually run. An app with no typecheck gate keeps full protection against
the first and loses the second, whose failure mode is visible and recoverable — a declared module
with no predicate is simply never shown.

## 10. Files

| File | Change |
|---|---|
| `references/generate-help.mjs` | read `modules.json`; frontmatter validation; the `:::module` block rule; module context per token; heading and search-entry tagging; validation rules 3 and 4; `module` on the emitted metadata and the `HelpModuleName` union in the manifest |
| `references/help-types.ts` | `module?` on `HelpDocMeta`, `HelpHeading`, `HelpSearchEntry` |
| `references/help-modules.json` | **new**, the declaration; ships as `[]`, installed to `<docsDir>/modules.json` |
| `references/helpModules.ts` | **new**, app-owned, ships empty, typed against `HelpModuleName` |
| `references/helpDocs.ts` | `isHelpModuleEnabled`, `visibleHelpDocs`, `filterHelpModuleBlocks`; existing consumers switched to the filtered list |
| `references/helpSearch.ts` | skip disabled entries at query time |
| `references/HelpContent.vue` | render the filtered HTML |
| `SKILL.md` | modules as contract §6, with the three invariants of §3 and §7 stated stack-neutrally; verification |
| `references/app-skill-help-docs.md` | authoring section: both syntaxes, the four rules, and §3's "not access control" |

`helpModules.ts` is the only one of these an application is expected to edit after it is in
place. That was originally motivated by keeping the other files copy-verbatim; under the handover
model it matters for a better reason — it is the single, findable place where an app's own wiring
lives, whatever stack the rest was rebuilt in.

## 11. Installer

Whoever installs the system must:

- create `docs/help/modules.json` containing `[]`, and the predicate map empty;
- when the app has a module, add its name to `modules.json` and its predicate to the map, and say
  which setting or role drives it.

There is no generator constant to set: the module list is content, not layout, so it lives with
the documents rather than in the build script.

The authoring skill gains the syntax from §4, the failure modes from §7 stated as rules an
author can follow, and §3's consequence in plain words — hidden is not private.

## 12. Verification

- An app declaring no modules: generation, topic list, search and contextual help are byte-for-byte
  unchanged from before. This is the inert-by-default claim and is the one that matters most.
- A document marked `module: x` with `x` off: absent from the topic list, absent from search,
  and the Help button on its route falls back to the topic list rather than erroring.
- The same document with `x` on: present in all three.
- A `:::module x` block with `x` off: absent from the body **and** from the outline, while the
  rest of its document renders.
- Validation rules 1–4 each fail generation with a message naming the file, and each passes once
  corrected. Rule 3 is the easiest to get wrong: verify it both ways — a link from outside the
  module fails, the same link from inside it succeeds.
- A name used by a document but absent from `modules.json` fails generation, naming the document
  and listing the declared names.
- A module declared in `modules.json` with no predicate in `helpModules.ts` fails
  `npm run typecheck`; so does a predicate for a name that is not declared. Both must be checked —
  they are the two halves of §9's claim, and they are the reason there is no runtime drift check.
- A missing `modules.json` behaves as `[]` rather than failing, so an installation predating this
  feature still generates.
- **On an SSR-enabled Nuxt app**: the help body renders and the browser console shows no
  hydration mismatch. §6.2 argues this cannot happen, from the order in which `loading` is set;
  the check confirms the argument rather than exploring an open question. If a mismatch does
  appear, the reasoning in §6.2 is wrong and the body needs explicit client-only rendering —
  resolve it in implementation, not by relaxing this check.

## 13. Not in scope

- **Access control.** §3.
- **Per-role documentation as a first-class idea.** A role-driven predicate works, but the design
  is not extended to cope with two users sharing a deep link to a section only one can see.
- **A UI for toggling modules.** The app owns the setting.
- **Migrating `pool_flow`** onto the ported version. Its implementation stays as it is; this
  spec generalises it rather than replacing it.
