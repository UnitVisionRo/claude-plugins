# claude-plugins

A [Claude Code](https://claude.com/claude-code) marketplace holding the skills shared across
our projects. It exists so a skill has **one** source of truth instead of a hand-copied
version per repo, drifting quietly apart.

The marketplace is named **`bogdan-plugins`** — that is the name you type after `@` when
installing, not the repository name.

## At a glance

**4 plugins, 8 skills.** Skills are invoked as `<plugin>:<skill>`. "Always-on" is what a
plugin's descriptions cost in *every* session; "on invoke" is paid only when a skill fires.

| plugin | skill | fires | always-on | on invoke |
|---|---|---|---|---|
| **`dev-workflow`** | `spec-driven-development` | automatically | ~120 | ~3.3k |
| | `git-commit-message` | automatically | ~20 | ~1.7k |
| | `clickup-task-updates` | automatically | ~110 | ~1.4k |
| **`project-tooling`** | `run-app` | automatically | ~90 | ~3.4k |
| | `check-updates-npm` | `/check-updates-npm` | ~80 | ~1.5k |
| | `check-updates-uv` | `/check-updates-uv` | ~60 | ~650 |
| **`database`** | `alembic` | automatically | ~80 | ~1.7k |
| **`scaffold`** | `fastapi-nuxt-scaffold` | `/fastapi-nuxt-scaffold` | ~140 | ~5.3k |

All four enabled costs roughly **710 tokens** in every session — `dev-workflow` ~259,
`project-tooling` ~230, `scaffold` ~139, `database` ~81. Disable what a project does not need;
`scaffold` is the usual candidate, since a project is scaffolded once and then never again.

## Install

Add the marketplace once, then install the plugins you want:

```bash
claude plugin marketplace add git@github.com:UnitVisionRo/claude-plugins.git

claude plugin install dev-workflow@bogdan-plugins
claude plugin install project-tooling@bogdan-plugins
claude plugin install database@bogdan-plugins
claude plugin install scaffold@bogdan-plugins
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
| `git-commit-message` | Commit messages written for business stakeholders, not developers. Asks for the tracker link. |
| `clickup-task-updates` | When to write to a tracker task, and what belongs in the description vs a comment. |

Fires automatically. Worth having on everywhere.

### `project-tooling` — running and maintaining a project

| skill | |
|---|---|
| `run-app` | Build, launch and screenshot the app (FastAPI + Nuxt). Discovers ports from the project's dev-server config; ships `driver.sh` for headless Edge under WSL2. |
| `check-updates-uv` | Outdated Python packages, with breaking-change notes and `uv sync` commands. |
| `check-updates-npm` | Outdated npm packages, grouped by what must move together. |

`run-app` fires automatically — ask it to run, start or screenshot the app and it activates.
It does start long-running dev servers, so the skill itself requires your go-ahead before
launching anything.

The two dependency checkers are **slash-commands only** (`/check-updates-uv`,
`/check-updates-npm`) and never fire on their own.

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
