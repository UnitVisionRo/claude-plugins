---
name: "check-updates-npm"
description: "Check for outdated npm packages in the frontend directory (front/ or gui/), grouped by packages that must move together, with breaking-change notes and npm update/install commands."
user-invocable: true
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

Consider the user input above before proceeding (if not empty). It may be a list of package names to focus on; if empty, report on everything that is outdated.

# Objective

Check for outdated packages in the frontend directory and list them, along with any relevant notes about breaking changes. Also prepare a list of update commands for the outdated packages.

# Locating the frontend

The frontend directory is named differently per project. Use the first of these that exists at the repo root, and say which one you picked:

- `front/`
- `gui/`

If neither exists, check for a `package.json` at the repo root and use that. If the layout still does not match, stop and ask rather than guessing.

# Steps

1. Run `npm outdated` from the frontend directory. It exits with code `1` whenever anything is outdated — that is its normal behaviour, not a failure. Without `--all` it lists only the direct dependencies declared in `package.json`, which is the scope of this check; never pass `--all`.
2. Read the three version columns before deciding anything:
   - **Current** — what is installed.
   - **Wanted** — the newest version allowed by the range in `package.json`.
   - **Latest** — whatever the `latest` dist-tag points at.

   From these:
   - `Wanted > Current` — an in-range update; `npm update <package>` is enough.
   - `Latest > Wanted` — the range in `package.json` blocks it; it needs `npm install <package>@<version>`, which rewrites that range.
   - `Latest < Current` — leave it alone. The maintainer's `latest` tag points at an older line and the line in use is published under a different tag; `vuedraggable` is the standing example, where `latest` is the Vue 2 release and the Vue 3 line sits under `next`. Confirm with `npm view <package> dist-tags` before drawing any conclusion from this column.
3. Group the packages that have to move together and report each group as a single decision, never as independent rows:
   - all `@tiptap/*` packages, `@tiptap/pm` included, share one version
   - `nuxt` and the `@nuxt/*` modules
   - `vue`, `vue-router` and `vue-tsc`
   - `pinia` and `@pinia/nuxt`
   - `eslint` and everything built on it (`@nuxt/eslint`, plugins, configs)
4. For each group that needs an update, check the release notes of **every intermediate version**, not just the newest one, and note the breaking changes:
   - Vuetify — the `vuetify-mcp` tools (`get_release_notes_by_version`, `get_upgrade_guide`, `get_v4_breaking_changes`)
   - Nuxt — `mcp__nuxt__get-changelog`
   - everything else — the browser or web search, on the project's own changelog and release notes

# Output

5. List the outdated direct dependencies, grouped as above, with the breaking-change notes per group.
6. Prepare the update commands, split in two blocks:
   - in-range updates: `npm update <package> ...`
   - major bumps, one line per group: `npm install <package>@<version> ...` with every package of the group on the same command
7. State which packages were deliberately left alone and why.

# Rules

- Only direct dependencies. Transitive ones move with their parents.
- Prepare the commands, do not run them. Applying the updates is a separate, explicit request.
- Never edit `package.json` or `package-lock.json` by hand.
- **Respect the project's pinned major versions.** Read the frontend's conventions doc first — `front/AGENTS.MD`, `gui/CLAUDE.md`, or the equivalent — and treat any framework version it pins as fixed. Both current projects pin **Vuetify 4**, and their component overrides are written against it, so a v5 bump is a project decision of its own, never part of a dependency refresh.
- A major version of one member of a group is never bumped on its own.
- After the updates are applied, verify them with `npm install`, then the project's type-check and build scripts (commonly `npm run type-check` and `npm run generate` — check `package.json`). `type-check` prints a `vue-router` / Volar `ERR_PACKAGE` line even when it succeeds — judge it by its exit code.
