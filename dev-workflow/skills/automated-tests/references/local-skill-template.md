---
name: automated-tests
description: Use when running, writing, splitting or reviewing <App>'s automated tests -- backend pytest (<back>/tests), frontend Vitest (<front>/<test root>/unit, nuxt) or Playwright end-to-end (<front>/<test root>/e2e) -- or when a suite is slow, skips unexpectedly, or collides with another run.
---

<!--
Template for a project's local automated-tests skill. Copy it to <repo>/.claude/skills/automated-tests/SKILL.md,
replace every <placeholder>, and delete what does not apply and this comment.
It supplies facts only; the rules live in dev-workflow:automated-tests. Keep it that way, so a fix to the rules
reaches every project. Its existence also switches on dev-workflow's scoped-tests hook in this repository.
-->

# <App> automated tests

**REQUIRED:** invoke the `dev-workflow:automated-tests` skill and follow it. It owns the rules. This file supplies
only <App>'s facts, and where it states one, it wins.

## Suites

Targeted while iterating; the full runs once, right before a commit the user ordered.

| Suite | Where | One file | Full run (before a commit) | Typical time |
|---|---|---|---|---|
| Backend | `<back>/`, venv active | `python -B -m pytest tests/test_x.py` | `FULL_SUITE=1 python -B -m pytest <-n 4, or nothing>` | <~70 s (N tests)> |
| Vitest | `<front>/` | `npx vitest run <test root>/nuxt/x.test.ts` | `FULL_SUITE=1 npm test` | <~25 s> |
| End-to-end | `<front>/` | `npm run test:e2e -- <test root>/e2e/x.spec.ts` | `FULL_SUITE=1 npm run test:e2e` | <~2.5 min with the build> |

- Expected skips in a full backend run: <0>. <Any known, expected skip and why, e.g. the schema-drift tests with
  a custom TEST_DB_NAME.>
- Install: <`uv sync --extra dev`>; Chromium with `npx playwright install chromium`.
- Shared code worth a wider targeted run: <the store, the API wrapper, the toasts, ...>.
- Gates beside the tests: <`ruff check`; ESLint `npx eslint .` / `npm run lint`; `npm run type-check` or "no type
  gate"; which ones hooks already run, so they are not run by hand>.

## Backend

- Test database: `TEST_DB_NAME`, default `<app>_test`; built by <`tests/conftest.py` / `scripts/test_database.py`>.
- Isolation: <rolled-back transaction per test, factory replaced in `<file>`; opt-out marker `<real_commits>`> OR
  <seed and delete by tracked ids, row prefix per file>.
- Async: <`asyncio_mode = "auto"`> OR <`pytestmark = [pytest.mark.anyio, ...]`>.
- Fixtures and helpers: <`db`, `client` (`https://test`), `make_user(db, email, role=...)`, `sign_in(client, db,
  user)`; or the conftest helpers imported as `from conftest import ...`>.
- HTTP: <through `client`> OR <endpoints called directly as functions with a `SimpleNamespace` user>.
- Mail and external services: <`outbox` fixture; stand-ins for ...>.
- Parallel: <serial by default / `-n 4` by default>.

## Frontend (Vitest)

- Test root: `<front>/<test or tests>/`; layers: `unit/`, `nuxt/`<, plus any project layer, e.g. `editor/` with its
  own `check()` harness>.
- Mounting: <`mountSuspended`> OR <`mountComponent` from `<test root>/nuxt/mount.ts` -- plain `mountSuspended`
  stalls on the auth middleware>.
- Split examples to copy: <`nuxt/BookingForm/`>.
- <Vitest module cache, time zone, type-checked or not.>

## End-to-end

- Instance: `<back>/scripts/e2e_instance.py` on port <8031>, database `E2E_DB_NAME` default <`<app>_e2e_test`>,
  app under <`/gui/`>.
- Mail: the instance starts `<back>/scripts/smtp_sink.py` in-process (`start_in_background()`, a free port) and
  points <its mail keys: `mail_server`, `mail_port`, ...> at it; every send is accepted and discarded.
- Data helpers: <`<test root>/e2e/data.ts` with `unique()`, `ui.ts` for forms>.
- A worktree also needs: <`<back>/.env`, `<back>/.venv`, generated files, `<front>/devServer.js`> linked.
- Icon-only buttons: <how the button wrapper gives them an accessible name: `title`, or an explicit
  `aria-label`>.
- <Project-only e2e machinery: stand-ins, a solo project, blocking helpers.>
