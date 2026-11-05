# claude-plugins

A [Claude Code](https://claude.com/claude-code) marketplace holding the skills shared across
our projects. It exists so a skill has **one** source of truth instead of a hand-copied
version per repo, drifting quietly apart.

The marketplace is named **`bogdan-plugins`** — that is the name you type after `@` when
installing, not the repository name.

## At a glance

**6 plugins, 13 skills.** Skills are invoked as `<plugin>:<skill>`. "Always-on" is what a
plugin's descriptions cost in *every* session; "on invoke" is paid only when a skill fires.

| plugin | skill | fires | always-on | on invoke |
|---|---|---|---|---|
| **`dev-workflow`** | `spec-driven-development` | automatically | ~120 | ~3.3k |
| | `automated-tests` | automatically | ~85 | ~3.8k |
| | `git-commit-message` | automatically | ~20 | ~1.7k |
| | `clickup-task-updates` | automatically | ~110 | ~1.4k |
| **`project-tooling`** | `run-app` | automatically | ~90 | ~3.4k |
| | `check-updates-npm` | `/check-updates-npm` | ~80 | ~1.5k |
| | `check-updates-uv` | `/check-updates-uv` | ~60 | ~650 |
| | `handover` | `/handover` | ~50 | ~1.9k |
| | `orchestrate` | `/orchestrate` | ~50 | ~1.7k (+ reads `handover`) |
| **`database`** | `alembic` | automatically | ~80 | ~1.7k |
| **`scaffold`** | `fastapi-nuxt-scaffold` | `/fastapi-nuxt-scaffold` | ~140 | ~5.3k |
| **`help-docs`** | `install-help-docs` | `/install-help-docs` | ~90 | ~2.3k |
| **`client-comms`** | `release-notes` | via the app's local skill | ~60 | ~2.8k |

All six enabled costs roughly **1,045 tokens** in every session — `dev-workflow` ~344,
`project-tooling` ~330, `scaffold` ~139, `help-docs` ~90, `database` ~81, `client-comms` ~60.
Disable what a project does not need; `scaffold` and `help-docs` are the usual candidates, since both do their work
once and then never again.

## Install

Add the marketplace once, then install the plugins you want:

```bash
claude plugin marketplace add git@github.com:UnitVisionRo/claude-plugins.git

claude plugin install dev-workflow@bogdan-plugins
claude plugin install project-tooling@bogdan-plugins
claude plugin install database@bogdan-plugins
claude plugin install scaffold@bogdan-plugins
claude plugin install help-docs@bogdan-plugins
claude plugin install client-comms@bogdan-plugins
```

Use the **SSH** URL while the repository is private — it reuses the SSH key you already push
with. A plain `UnitVisionRo/claude-plugins` shorthand works once the repo is public.

**Skills load on the next session.** Nothing appears in the session where you install them.
Confirm what landed with:

```bash
claude plugin details dev-workflow      # component inventory + token cost
claude plugin list                      # everything installed, and its scope
```

### Scope

`--scope user` (the default) installs for you everywhere. Use `project` to tie a plugin to the
repo you are in, and `local` for a machine-local install that stays out of shared settings:

```bash
claude plugin install database@bogdan-plugins --scope project
```

Enable and disable per scope without uninstalling:

```bash
claude plugin disable scaffold          # e.g. in an already-scaffolded project
claude plugin enable  scaffold
```

## What's in it

Skills are invoked as `<plugin>:<skill>`. Each plugin is installed and enabled independently,
so pick the ones a given project actually needs.

### `dev-workflow` — how we work

| skill | |
|---|---|
| `spec-driven-development` | The phase → chunk → review workflow: where specs and plans live, how code cites them, when to commit. **Overrides the `superpowers` plugin** on review granularity, committing, and spec locations. |
| `automated-tests` | Writing and running the backend pytest, Vitest and Playwright suites of a FastAPI + Nuxt project: test databases and isolation, speed budgets, and **targeted runs while iterating, the full suites once before a commit**. |
| `git-commit-message` | Commit messages written for business stakeholders, not developers. Asks for the tracker link. |
| `clickup-task-updates` | When to write to a tracker task, and what belongs in the description vs a comment. |

Fires automatically. Worth having on everywhere.

`automated-tests` is generic, like `release-notes`: each project keeps a small **local** skill at
`.claude/skills/automated-tests/SKILL.md` that invokes `dev-workflow:automated-tests` and supplies its facts —
folders, commands, database names, ports, helpers, timings. Start it from
`dev-workflow/skills/automated-tests/references/local-skill-template.md`.

The plugin also ships a **`PreToolUse` hook** (`hooks/scoped-tests.py`) that denies an unscoped pytest, Vitest
or Playwright run unless the command is prefixed `FULL_SUITE=1`. It is **opt-in**: it acts only in a project that
has that local skill, and does nothing anywhere else. A project that registered its own copy of the hook should
drop it, or every unscoped run is denied twice. Its checks: `python3 -B dev-workflow/hooks/test_scoped_tests.py`.

### `project-tooling` — running and maintaining a project

| skill | |
|---|---|
| `run-app` | Build, launch and screenshot the app (FastAPI + Nuxt). Discovers ports from the project's dev-server config; ships `driver.sh` for headless Edge under WSL2. |
| `check-updates-uv` | Outdated Python packages, with breaking-change notes and `uv sync` commands. |
| `check-updates-npm` | Outdated npm packages, grouped by what must move together. |
| `handover` | `/handover #N [#M…] [to <session>\|new] [work isolated\|main checkout]`: builds a self-contained brief (item text, code pointers, meeting-transcript quotes with timestamped links, the handover rules verbatim — including creating a tracker implementation task before any work — and the project's standing rules), starts a `claude --bg` session or messages an existing one, and records the handoff in the to-do tracker as `name` (`session ID`). Also covers receiving `done: #N`: verify the commits, move the item to Done, flag extra scope. |
| `orchestrate` | `/orchestrate #x, #y` or `/orchestrate <session names>`: for those items only, one isolated session per item, merge each branch into local `main` on `done: #N`, collect the screenshots each change needs, then subagents retake the screenshots and run the full suites once on `main`; failures go back to the owning session, and when everything is green each session removes its worktree and branch. |

`run-app` fires automatically — ask it to run, start or screenshot the app and it activates.
It does start long-running dev servers, so the skill itself requires your go-ahead before
launching anything.

The two dependency checkers, `handover` and `orchestrate` are **slash-commands only** (`/check-updates-uv`,
`/check-updates-npm`, `/handover`, `/orchestrate`) and never fire on their own.

`handover` and `orchestrate` are meant for the one session that keeps a project's to-do tracker and hands work to
other sessions. Nothing project-specific is in them: the tracker path, its header's handover rules, the recording
source, worktree setup, test-DB and port scheme, full-suite commands and the screenshot instance all come from the
project's CLAUDE.md, local skills or memory, and the skills stop and ask when one is missing.

### `database` — schema and migrations

| skill | |
|---|---|
| `alembic` | Migration practice for both the MySQL and PostgreSQL projects, including what `--autogenerate` and `alembic check` do **not** see. |

### `scaffold` — starting something new

| skill | |
|---|---|
| `fastapi-nuxt-scaffold` | Bootstrap a FastAPI backend with multiple API surfaces plus a Nuxt 4 + Vuetify 4 frontend generated from the backend's OpenAPI schema. Ships 24 reference files. |

Enable it when starting a project; disable it afterwards — it is the heaviest plugin here and
a project only gets scaffolded once.

### `help-docs` — user-facing documentation inside the app

| skill | |
|---|---|
| `install-help-docs` | Install a Markdown-sourced help system into a Nuxt + Vuetify app: `docs/help/*.md` compiled at build time, a Help button giving contextual help per page, a searchable `/help` browser, and an authoring skill written into the app's own `.claude/skills/`. |

Slash-command only (`/install-help-docs`). Like `scaffold`, enable it for the install and
disable it afterwards — the documentation is then maintained through the skill it leaves behind
in the app.

### `client-comms` — telling the client what shipped

| skill | |
|---|---|
| `release-notes` | The client's release email, in Romanian, for non-technical staff: from a commit range, with every claim checked against the code and migrations, screenshots from the app's own capture tooling, and an Outlook-ready `.eml` (CID-embedded images, opens as a draft) plus `.html` and `.txt`. Ships the builder that produces and verifies the `.eml`. |

Generic on purpose. Each app keeps a small **local** skill at `.claude/skills/release-notes/SKILL.md` that
invokes `client-comms:release-notes` and supplies the app's facts: name, theme colours, help-docs and manual
paths, vocabulary, migrations, screenshot store and demo-instance capture procedure. Start it from
`client-comms/skills/release-notes/references/local-skill-template.md`.

The skill stays model-invocable on purpose: a local skill reaches it through the Skill tool, and
`disable-model-invocation` risks blocking that call. Its description is narrow enough that it does not fire on
commit messages or developer changelogs.

## Updating

An installed plugin is a **frozen copy**, not a live link to this repo. Pulling or editing
locally changes nothing until you refresh:

```bash
claude plugin marketplace update bogdan-plugins    # re-read the catalog
claude plugin update dev-workflow                  # then take the new version
```

Restart Claude Code for the change to take effect.

## Contributing a skill

```
<plugin>/
├── .claude-plugin/plugin.json
└── skills/
    └── <skill-name>/
        └── SKILL.md            # frontmatter: name, description
```

A skill's **`description` is what decides whether it fires**, and it stays resident in every
session — so make it specific about *when* to use the skill, and keep it tight.

Add `disable-model-invocation: true` + `user-invocable: true` for a slash-command-only skill.

Validate before opening a PR:

```bash
claude plugin validate .                    # the marketplace manifest
claude plugin validate ./<plugin>           # one plugin manifest
claude plugin validate ./<plugin>/skills    # the skills themselves
```

Register a new plugin in `.claude-plugin/marketplace.json` as well as its own `plugin.json`,
and keep the two descriptions identical — `claude plugin tag` checks that they agree.

### ⚠️ Subfolders under `skills/` do not work

Only `skills/<name>/SKILL.md` is discovered. A skill one level deeper —
`skills/group/<name>/SKILL.md` — **passes validation, installs, and is then silently ignored**.
There is no warning; the skill simply never exists.

Group skills by splitting them into separate plugins instead. The plugin name becomes the
namespace, which is what `dev-workflow:` and `project-tooling:` already are.

## Testing a change without publishing

Point the marketplace at your working copy, and installs come from disk:

```bash
claude plugin marketplace add /path/to/claude-plugins
```

Note that a local `directory` marketplace is recorded in `settings.json` under
`extraKnownMarketplaces` and can be dropped when Claude Code rewrites that file. If a plugin
disappears after a restart, check there first.
