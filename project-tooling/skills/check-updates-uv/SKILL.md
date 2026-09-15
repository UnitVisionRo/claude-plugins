---
name: "check-updates-uv"
description: "Check for outdated Python packages with uv in the backend directory (back/ or api/), with breaking-change notes and ready-to-run uv sync commands."
user-invocable: true
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

Consider the user input above before proceeding (if not empty). It may name a tree level (e.g. `1`) or specific packages to focus on.

# Objective

Check for outdated packages in the backend directory and list them, along with any relevant notes about breaking changes. Also prepare a list of update commands for the outdated packages.

# Locating the backend

The backend directory is named differently per project. Use the first of these that exists at the repo root, and say which one you picked:

- `back/`
- `api/`

If none exists, check whether the repo root itself is the Python project (a `pyproject.toml` at the top level) and use that. If the layout still does not match, stop and ask rather than guessing.

# User input

Tree level: e.g. `1`. If not provided, assume `1`.

# Steps

1. Run `uv pip list --outdated` from the backend directory. Then run `uv tree` and see which level `<level>` packages (those directly under the project's own package) need an update.
2. For those that need an update, check on the internet whether there are any breaking changes between the current and new versions. Make sure you check the release notes for **all intermediate versions**, not just the latest one. Use the browser or web fetch to investigate the release notes and changelogs.

# Output

3. List the `--outdated` output for the outdated `<level>` packages only, plus any relevant notes about breaking changes.
4. Prepare a list of update commands for the outdated `<level>` packages, in the format `uv sync --upgrade-package package_name`.

# Rules

- Do not check for transitive dependencies, only the `<level>` packages.
- Prepare the commands, do not run them. Applying the updates is a separate, explicit request.
