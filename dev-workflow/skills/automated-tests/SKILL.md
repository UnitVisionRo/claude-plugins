---
name: automated-tests
description: Use when running, writing, splitting or reviewing automated tests in a FastAPI + async SQLAlchemy + Nuxt/Vuetify project -- backend pytest on a real test database, frontend Vitest, or Playwright end-to-end -- when a test command is blocked by the scoped-tests hook, or when a suite is slow, skips unexpectedly, or collides with another run.
---

# Automated tests

Three suites, each with its own runner: backend pytest against a real MySQL/PostgreSQL test database, frontend
Vitest, Playwright end-to-end. A test is part of the product: one that seeds too much, waits on the clock or makes
its file the longest one slows every later run, for every developer and agent. Check the cost of every test you add
(**Performance budget** below).

## The project's local skill (hand-off contract)

This skill holds the rules shared by every project on the stack. The project's facts -- folders, commands, database
names, ports, helpers, timings -- live in its **local** skill, `.claude/skills/automated-tests/SKILL.md`. Read it
before running or writing anything: where it states a project fact, it wins.

**No local skill yet:** write one with the user, from `references/local-skill-template.md`. Establish what you can
from the repository (`conftest.py`, `pyproject.toml`, `vitest.config.ts`, `playwright.config.ts`, the npm scripts,
a timed full run) and ask only for what the repository cannot answer. The user confirms the file before you write
it. Its existence also switches on the scoped-tests hook below for that project.

## Targeted while iterating, full once before a commit

While working on a change, run **only the tests that cover it**: the affected pytest module(s), Vitest file(s),
Playwright spec(s). Shared code (a store, an API wrapper, an endpoint several screens use) justifies a **wider
targeted** run -- more files named -- never an unscoped one.

The **full suites run once, right before a commit the user ordered**, or when the user asks for a full run. In
`dev-workflow:spec-driven-development` they run once, after the human approves the final review of the
implementation. Every phase or review-fix commit before that runs only the tests covering its changes. A full run prefixes the command with `FULL_SUITE=1`:

```bash
FULL_SUITE=1 python -B -m pytest        # + the project's -n, if it has outgrown a serial run
FULL_SUITE=1 npm test
FULL_SUITE=1 npm run test:e2e           # when a screen changed
```

Why: briefs that demanded every suite after every change request turned one small change into ~40 minutes, and
parallel agents running full suites on one MySQL server slowed each other down (a 70 s backend run became 170 s).

- **Subagent briefs name the targeted test files** ("run `tests/test_booking.py` and
  `<test root>/nuxt/BookingForm/`"), never "run all the tests". The full run is the orchestrator's, before the commit.
- **Done without a commit** means the targeted tests pass. Say in the report that the full suites were not run,
  and why.
- **The hook.** `dev-workflow` ships a `PreToolUse` hook that denies an unscoped pytest, Vitest or Playwright
  run without `FULL_SUITE=1`, in projects that have the local skill. A scope is a file, folder below the test
  root, node id, `-k`/`-t`/`-g` filter or `--lf`; `tests/` itself is not one. Denied? Name the files. Don't
  reach for `FULL_SUITE=1` to get past it, except for the full run above.

## Backend (pytest)

### Running
- Always `python -B -m pytest`, from the backend folder with its venv activated. Never bare `pytest` (it misses the
  backend root on `sys.path`) and never `uv run` for tests. `-B` keeps stale bytecode from making a broken file look
  green.
- One file: `python -B -m pytest tests/test_x.py`; one test: `tests/test_x.py::test_name`; the slowest setups and
  calls: `--durations=20`.
- **Serial until a full serial run passes ~60 s**, then `-n 4` (pytest-xdist; `-n 6` at most -- more workers only
  add database rebuilds on the one server). Each worker gets its own database, `<base>_gw<N>_test`, rebuilt at its
  start, so a single file is always faster serial. `--dist=loadfile` keeps each file on one worker, in file order.
  pdb and `-s` need a serial run.

### The test databases
- The suite runs on its own database, `TEST_DB_NAME` (default `<app db>_test`), which it **drops and rebuilds**
  at the first database test of a run: the schema from the ORM models plus the enum rows, as a fresh install.
  `conftest.py` points the settings at it **before anything imports the app**.
- **A name that does not end in `_test`, or equals the app's database, is refused** before any connection opens.
- **Never two runs at once on one test database** -- another session, a worktree, an end-to-end backend: each
  wipes the other's tables mid-run, and the failures look like bugs in the code under test. Each concurrent run
  takes its own name, `TEST_DB_NAME=<app>_<label>_test`, created if missing; with `-n` the workers' databases
  derive from it (`<app>_<label>_gw0_test`, ...). The default name is for a run you know to be alone; an
  orchestrator gives each subagent its label. Drop a labelled run's databases when it is done (`DROP DATABASE IF
  EXISTS ...`, or `dropdb` on PostgreSQL), its `_gw*_test` ones included; the default-name databases stay.
- **An unreachable database fails the run; it is never skipped.** A green run has the project's expected skip count
  (normally 0). Hundreds of skips mean the database was lost and nothing was tested -- the run is not green. A
  suite that still skips on a missing database: compare the skip count with the local skill's before reporting.
- Per-agent databases for parallel subagent work: `dev-workflow:spec-driven-development`, Per-agent test databases.

### Isolating a test
**Preferred: one rolled-back transaction per test.** All the app's sessions come from one factory (e.g.
`database/session.py::session_maker`); the fixtures replace it so every session -- the test's `db`, each request's,
each service's own -- joins one connection's outer transaction through its own savepoint. `commit()` releases the
savepoint, `rollback()` returns to it, the transaction is rolled back after the test. `dependency_overrides` cannot
do this when every `Depends(get_session())` is a function of its own. What follows from it:
- **Ids are not reset** (a rolled-back insert keeps its AUTO_INCREMENT value): never depend on an id's value.
- **No DDL in a test**: MySQL commits it implicitly, ending the transaction.
- **Savepoints nest**: once a request committed while `db` held a savepoint, `db.rollback()` erases that commit too.
- **A request opens several sessions at once** (the auth check's, the endpoint's): a session closed without
  uncommitted writes must leave its savepoint in place, or it erases the other's commit.
- **Another connection sees none of it.** A test whose point is what another connection sees opts out with a marker
  (e.g. `@pytest.mark.real_commits`, one-line reason beside it): its sessions commit for real and its teardown
  truncates the non-enum tables.
- Commit what a test sets up before calling the endpoint, as production would need it.

**Fallback, where the sessions do not come from one replaceable factory:** seed through the app's session, commit,
and delete everything in the fixture's teardown by tracked ids, in reverse foreign-key order. Give rows a
file-specific prefix and query by your own ids, never by global counts.

### Writing a test
- Async: the project's choice of `asyncio_mode = "auto"` (pytest-asyncio) or the `anyio` marker -- the local skill
  says which. A session-scoped async fixture does not mix with a module-scoped event loop: do session-wide setup
  synchronously with `asyncio.run(...)`, and dispose the engine after a wide-scope fixture's setup -- pooled asyncmy
  connections cannot cross event loops.
- HTTP through the test client (`https://test` when the auth cookies are `Secure`), or endpoints called directly
  as functions -- the local skill says which. Sign users in through a helper that sets the token cookie without
  bcrypt (~0.25 s a login); test the login itself through the login endpoint.
- No test sends mail or reaches an external service: stand-ins only.
- Pure logic needs no database: ask for none of its fixtures, and the test runs in milliseconds.

### Keeping it fast
- **Many rows -> one Core statement.** On MySQL the ORM sends one `INSERT` per row to read back each id: 800 rows
  took 0.54 s with `db.add_all([...])` and 0.065 s with `await db.execute(sa.insert(Model), [dict(...), ...])`.
  ORM for the few rows whose ids you need, Core for anything generated in a loop. Setup much longer than call in
  `--durations` is the sign.
- **Seed once what no test changes.** Read-only background data a whole file needs goes in a `scope="module"`
  fixture. No test modifies it; a test that adds to it removes what it added; anything a test changes stays per
  test. Module-scoped rows sit outside the per-test transaction, so the fixture deletes them in its teardown -- and
  keep them out of files with real-commit tests, whose truncation would remove them.

## Frontend (Vitest)

Three layers, one folder each under the test root (`test/` or `tests/`):
- **`unit/`**: plain Node, pure code (utils, formatting, parsing). Import by relative path, not `~/`. Milliseconds.
- **`nuxt/`**: the app's Nuxt environment (`@nuxt/test-utils`, happy-dom): auto-imports, `~/`, plugins, Vuetify,
  Pinia. Mount with `mountSuspended` or the project's wrapper around it (a global auth middleware can stall every
  mount for seconds). The backend is reached through axios (`apiHttp`), which `registerEndpoint` does not
  intercept: replace it with `mockNuxtImport('apiHttp', ...)`. Dialogs and menus teleport: look their content up
  in `document.body`. `nuxt/setup.ts` fills what happy-dom lacks.
- **`e2e/`** belongs to Playwright: the Vitest config's `include`s keep Vitest out of it.

One file or folder: `npx vitest run <path>`; one test: add `-t "<title>"`.

### Keeping it fast
- **Files run in parallel, the tests inside a file one after another**: the run takes as long as the slowest file.
  Each `nuxt/` file pays ~5 s to start its environment, so tiny files cost too -- don't split small ones.
- Keep a `nuxt/` file to roughly 30 mounting tests and 10-12 s on its own. When a component's tests outgrow that,
  split them by topic into a folder, `nuxt/<Component>/`:
  - `api.ts`: the fake backend (state, call log, the `apiHttp` stand-in). **No app imports**: it loads before the
    app's modules.
  - `harness.ts`: fixtures, mounting, element lookups and a `resetBetweenTests()`.
  - `<topic>.test.ts`, each starting with the two lines below -- `mockNuxtImport` must sit in the test file itself.
    Share backend answers through an exported object (`backend.detail = ...`): an imported `let` is read-only.
    ```ts
    mockNuxtImport('apiHttp', async () => (await import('./api')).apiHttp)
    resetBetweenTests()
    ```
- **Don't wait on the clock.** A real `await new Promise(r => setTimeout(r, 350))` costs 350 ms in every test using
  it. Fake the timeouts **before** the mount or keystroke that starts the debounce, then advance:
  ```ts
  afterEach(() => { vi.useRealTimers() })
  // ...
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  const wrapper = await mountSuspended(Component)   // or the keystroke that starts the debounce
  await vi.advanceTimersByTimeAsync(350)
  vi.useRealTimers()
  ```
  Convert existing real waits when you touch those tests.
- Logic that needs no mount goes into a function, tested in `unit/`.

## End-to-end (Playwright)

- A real Chromium against the whole application in the production topology. `npm run test:e2e`:
  - builds the app for production into `.e2e/` (git-ignored), away from the `.nuxt/` a running `npm run dev`
    works in and the build the development backend serves;
  - starts the backend's e2e instance script on its own port (plain http on 127.0.0.1, no dev proxy), which
    rebuilds **its own database** (`E2E_DB_NAME`, ending in `_test`, never the backend suite's) with the
    administrator the tests sign in as, and sends mail to a closed port.

  It never reuses a server already answering on its port.
- One spec: `npm run test:e2e -- <spec>`. `E2E_REUSE_BUILD=1` skips the build while writing tests that don't change
  the interface's code. `npx playwright show-report` shows the report and the traces of failures. Chromium, once
  and after a Playwright upgrade: `npx playwright install chromium`.
- **One run per checkout at a time** (shared `.e2e/` and saved session). A second checkout or worktree needs its
  own `E2E_DB_NAME=<x>_test E2E_PORT=<port>`, plus the backend's `.env` and `.venv` linked from the main checkout.
- A `setup` project signs in once and saves the session (`e2e/.auth/`, git-ignored: live cookies). Tests start
  signed in from it, or opt out with `test.use({ storageState: { cookies: [], origins: [] } })`.
- Hash routes: `page.goto('#/clients')`, relative to the app's base path -- never `'/#/clients'`, which drops it.
- Tests run in parallel on one database: create data **through the REST API** with `unique()` names, not through
  the UI when the UI is not what is tested -- each UI step costs seconds.
- Wait on what the user would see (`await expect(locator).toBeVisible()`), never `page.waitForTimeout`. Find
  controls by role and name (`getByRole('button', { name })`); an icon-only button needs an accessible name --
  check how the project's button wrapper derives it before relying on `title`.
- The most expensive layer (10-18 s a test). Cover a rule there only when it needs the real browser and backend
  together; edge cases belong in pytest or Vitest.

## Performance budget (check before finishing)

| Check | How | Smell |
|---|---|---|
| Backend test setup | `python -B -m pytest <file> --durations=20` | setup > 0.3 s per test, or setup >> call |
| Backend file | the file on its own, serial | > 30 s: look for per-test seeding of shared data |
| Backend suite | a full serial run | > ~60 s: switch to `-n 4` |
| Vitest file | `npx vitest run <file>` | > 10-12 s, or > 30 mounting tests |
| Vitest waits | `grep -n "setTimeout(" <file>` | any new real-time wait |
| End-to-end | the HTML report's per-test times | UI used to create data, `waitForTimeout` |

Before declaring work done:
1. The targeted tests of the change pass (the full suites only if a commit was ordered).
2. The skip count matches the local skill's expected count.
3. Report the times of the test files you added or grew.

## Common mistakes

| Mistake | Fix |
|---|---|
| Running every suite after each change request | The covering files only; full suites once, before an ordered commit |
| A subagent brief saying "run all tests" | Name the test files the chunk touches |
| `pytest tests/` to get past the hook | `tests/` is the full suite; name files, or `FULL_SUITE=1` before a commit |
| Bare `pytest` or `uv run pytest` | `python -B -m pytest` from the activated venv |
| Two runs on the same `TEST_DB_NAME` at once | A distinct `TEST_DB_NAME=..._test` per concurrent run |
| "All green" with hundreds of skips | The test database was unreachable; fix it and rerun |
| A test depending on an id's value | Query by what the test created; ids are not reset |
| `db.add_all` of hundreds of generated rows per test | `sa.insert(Model)` with dicts, in a module-scoped fixture if no test changes them |
| A test edits a shared module-scoped row | Make that row per test, or undo the change in the test's teardown |
| `-n 4` on a small suite or a single file | Serial is faster until a run passes ~60 s |
| The 40th test in a 12 s Vitest file | Split by topic into `nuxt/<Component>/` |
| `mockNuxtImport` placed in the harness | Keep it in each test file, importing the fake from `api.ts` |
| `page.goto('/#/x')` | `page.goto('#/x')` |
