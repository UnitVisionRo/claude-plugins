---
name: "run-app"
description: "Build, launch, and drive the app (FastAPI backend + Nuxt frontend). Use to run, start, serve, or screenshot the GUI/console/backend, or to confirm a change works in the real running app on this WSL2 + Windows Edge machine."
---

# Run the app

The app is two processes that run together: a **FastAPI/uvicorn backend** and a **Nuxt dev
server** whose dev proxy forwards `/rest*` to the backend. Both bind HTTPS with the localhost
dev certs. **The backend must be running for the frontend to work**, and you always browse the
**frontend** port — the backend port serves only the API.

## First: find the layout and the ports

Nothing here is hardcoded, because every project uses its own directories and port pair.
Establish both before running anything, and **state what you found**.

**Directories** — use the pair that exists at the repo root:

| backend | frontend |
|---|---|
| `back/` | `front/` |
| `api/` | `gui/` |

**Ports** — read them from the project, in this order. Stop at the first that answers:

1. **`.claude/.secrets`** at the repo root, if it records them (see Secrets below).
2. **The frontend dev-server config** — `front/devServer.js`, `gui/devServer.js`, or
   `nitro.devProxy` in `gui/nuxt.config.ts`. This gives the frontend port *and* the backend
   port it proxies to, which is the authoritative pair.
3. **`.vscode/launch.json`** — the backend launch config carries `--port`.
4. **Whatever is already listening**, if the servers are up:
   ```bash
   (ss -ltnp 2>/dev/null || netstat -ltnp) | grep -E 'uvicorn|node|python'
   ```

If the config and a running process disagree, the config wins — the process is probably stale.

Throughout this skill, `<BACK_PORT>` and `<FRONT_PORT>` mean the values you just found.

## Secrets

Login credentials, SSL keyfile/certfile paths and DB connection parameters live in the
gitignored **`.claude/.secrets`** at the repo root. Read it when you need to log in or to
locate the certs.

**Never print, echo or copy its values** into chat, code, docs or commits. Refer to keys by
name and purpose only. If a value you need is missing, say which key is absent — never invent
one.

## Build (install deps)

```bash
cd <backend>  && uv sync        # backend deps  -> <backend>/.venv
cd <frontend> && npm install    # frontend deps -> <frontend>/node_modules
```

## Ask before starting servers

Dev servers are long-running processes — get the user's go-ahead before launching them. In
projects driven from VS Code, prefer asking the user to start them there; that is how they
normally work, and a `debugpy` session you kill takes their debugger with it.

Note that a VS Code "frontend" launch config often only **opens the browser** for debugging —
it does not start the Nuxt dev server. That still has to be started separately.

## Start the backend

Confirm it is not already running. Cert paths come from `.claude/.secrets`:

```bash
cd <backend>
nohup uv run uvicorn main:app --host 127.0.0.1 --port <BACK_PORT> \
  --ssl-keyfile <ssl-keyfile> --ssl-certfile <ssl-certfile> \
  > /tmp/$(basename $PWD)-backend.log 2>&1 &
```

Some projects start it via `python main.py --host localhost --port <BACK_PORT> …` instead —
match whatever `.vscode/launch.json` does.

Confirm it is up, and that the DB is reachable:

```bash
curl -sk https://localhost:<BACK_PORT>/health       # -> {"status":"ok"}
curl -sk https://localhost:<BACK_PORT>/health/db    # -> {"database":"ok"}
```

### ⚠️ The backend does NOT auto-reload — it serves the code it loaded at startup

The launch configs deliberately omit `--reload` (the reloader spawns a child the debugger
cannot track). A `--reload-delay` on its own does nothing.

**The frontend is the opposite** — Vite HMR applies edits immediately. That asymmetry is the
trap: the browser runs your new frontend against the old backend, and the symptom looks like a
frontend bug. A stale server has already caused a correct component to be reported as broken,
because the API was returning data from hours-old code and the component was faithfully
rendering what it received.

So, after editing anything under the backend:

- Assume the running server is stale until you have shown otherwise.
- **Do not kill it yourself** when it is the user's VS Code session. Ask them to restart it,
  and say which change needs picking up. (If you started it yourself in the background, it is
  yours to restart — just say so.)
- You usually don't need the server at all for backend verification — import the service
  functions and call them directly, which also guarantees current code:
  ```bash
  cd <backend> && PYTHONPATH=$PWD uv run python -B -c "from services.x import f; print(f())"
  ```

## Start the frontend

```bash
cd <frontend>
nohup npm run dev > /tmp/$(basename $PWD)-gui.log 2>&1 &
```

The port and the `/rest` proxy come from the dev-server config — no CLI flags needed. Wait
until it serves:

```bash
curl -sk -o /dev/null -w '%{http_code}\n' https://localhost:<FRONT_PORT>/
```

A `200` or a `302` (redirect to the login route when unauthenticated) both mean it is up.

## Drive it — screenshot routes with `driver.sh`

Try the claude-in-chrome tools first if the browser is connected. If they are unavailable, or
you want an automated sweep of several routes, use the bundled driver.

`driver.sh` ships **next to this file**, in this skill's own directory — the base directory
stated when this skill loaded. Set `DRIVER` to it once, then reuse it:

```bash
DRIVER="<this skill's directory>/driver.sh"
```

**`BASE_URL` is required** — it carries the frontend port you discovered. There is no default
port:

```bash
BASE_URL=https://localhost:<FRONT_PORT> bash "$DRIVER" /login

# several routes in one go
BASE_URL=https://localhost:<FRONT_PORT> bash "$DRIVER" /login /dashboard /reports
```

Each call prints a path like `/mnt/c/Users/<you>/<repo>-shots/login.png` — **open it with the
Read tool** to see the rendered page. The output folder defaults to the repo directory name;
override it with `SHOTS_DIR=…`, and pick the Windows output user with `WIN_USER=…`.

Authenticated screens need a signed-in session; otherwise the driver captures the
login/redirect state.

## Test / lint

```bash
cd <backend>  && uv run pytest
cd <backend>  && uv run ruff check . && uv run mypy .
cd <frontend> && npm run lint
```

## Stop

```bash
for port in <FRONT_PORT> <BACK_PORT>; do kill $(lsof -ti tcp:$port) 2>/dev/null; done
```

## Gotchas

- **Use `--headless`, not `--headless=new`.** New headless mode intermittently hands the
  invocation to an already-running Edge and exits `0` *without writing the PNG*. Old
  `--headless` writes reliably. The driver uses old mode.
- **One profile dir per launch.** Sequential headless launches sharing a single
  `--user-data-dir` deadlock on the profile lock and hang. The driver gives each launch a
  unique `--user-data-dir` and wraps it in `timeout 60`.
- **Edge needs `--ignore-certificate-errors`** — the dev certs are self-signed; without this
  the screenshot is a cert-error interstitial.
- **Screenshots land on the Windows filesystem.** Edge is a Windows process, so `--screenshot`
  takes a `C:\…` path; the driver writes under `C:\Users\<you>\` and you read it back from WSL
  at `/mnt/c/Users/<you>/`. A Linux path passed to Edge won't work.
- **Windows Edge reaches the WSL dev server over `localhost`** thanks to WSL2 localhost
  forwarding — no host-IP juggling needed.
- **Browser warns about the self-signed cert** — expected for `localhost`; accept and continue.

## Troubleshooting

- **Blank page / `Failed to fetch dynamically imported module` from `_nuxt`** — a known Nuxt
  dev quirk. Refresh a few times; the dev server eventually serves the missing chunks. If
  several refreshes don't help, read the console for the real error.
- **Backend exits with a pydantic `ValidationError` for missing fields** — the settings module
  declares a required setting the environment doesn't provide (a field with no default fails
  at import time). Don't invent values — surface the missing keys to the user by name and
  purpose only, never values.
- **API calls 401/CORS-fail** — the backend's `base_url` setting must match the browser origin
  (`https://localhost:<FRONT_PORT>`).
- **`/health/db` hangs or errors** — Postgres/MySQL isn't running, or the project's database is
  unreachable. Check the DB block in `.claude/.secrets` and that the server is up.
- **Frontend never serves** — read its log in `/tmp/`; a port clash is the usual cause
  (`lsof -ti tcp:<FRONT_PORT>`).
- **Driver prints `FAILED: <route> (no PNG written)`** — usually leftover headless Edge holding
  a profile. Kill the driver's Edge instances (leaves your real browser alone) and retry:
  ```bash
  powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -like '*-shots*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
  ```
- **The app shows old behaviour, or an endpoint returns data that contradicts the code** — the
  backend is serving stale code (see the warning above). Confirm before concluding anything
  about the frontend: check how long the server has been up against when you last touched the
  backend:
  ```bash
  (ss -ltnp 2>/dev/null || netstat -ltnp) | grep :<BACK_PORT>   # find the pid
  ps -o pid,etime,args -p <pid>                                 # uptime vs your last edit
  ```
