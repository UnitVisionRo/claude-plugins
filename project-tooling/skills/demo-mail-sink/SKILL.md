---
name: demo-mail-sink
description: Use when building or running a throwaway demo, screenshot or end-to-end test instance of an app that sends e-mail (verification codes, invitations, notifications) - routes its outbound mail to a local SMTP server, copied into the app, that accepts and discards everything.
---

# Local mail sink for demo and test instances

A demo or test instance — a second installation with its own database, built to seed invented data,
take screenshots or run the end-to-end suite — must never send real e-mail, and must still be able
to *send* e-mail successfully. `smtp_sink.py`, next to this file, is a local SMTP server that does
both: it accepts every message and delivers none.

## Why an instance needs one

- **Apps send mail on their own, even with notifications switched off.** Adding a client or a
  contact with an e-mail address can send a verification code by itself; creating users sends
  invitations; password and security flows send codes. A seed script or a test suite that drives
  the app's real endpoints triggers all of it — easily dozens of messages, to invented addresses,
  through the real mail account a copied configuration still points at.
- **Blocking is not enough; the mail has to be accepted.** Apps commonly store state only after
  the mail server accepted the message — a verification code is saved, an address becomes
  "code sent", an invitation becomes "pending". Point the instance at a closed port and every send
  fails: those records never appear, the screens that show them have nothing to show, and the
  flows behind them cannot be tested end to end. The sink answers `250` to everything, so the app
  proceeds exactly as in production.

Backend unit and integration tests are a different case: they replace the send function with a
stand-in and reach no SMTP server at all. The sink is for instances that run the whole app.

## Put a copy in the app

The sink lives **in the application's repository**, not in this plugin: the end-to-end suite has to
run on a machine (or in CI) where no plugin is installed, and a project procedure that points into
the plugin cache breaks on every plugin update. Copy it once, next to the backend's other scripts:

```bash
cp "<this skill's directory>/smtp_sink.py" <back>/scripts/smtp_sink.py
```

Install the plugin per project (`claude plugin install project-tooling@bogdan-plugins --scope
project`, from the repository root) wherever an app has the sink: the end-to-end skill and the
app's help-docs skill check for both this skill and the copy, and remind the user when either is
missing.

`<this skill's directory>` is the base directory stated when this skill loaded; `<back>` is the
backend folder (`back/`, `api/`). If the app already has a copy, `diff` it against this one and
take the newer behaviour rather than keeping two. It is standard library only (Python 3.12+ no
longer ships `smtpd`; nothing to install), advertises no `AUTH` and no `STARTTLS`, and discards
each message after reading it.

## Point the instance at it

Set the instance's mail configuration — and **only** those keys — to:

| setting | value |
|---|---|
| server / host | `127.0.0.1` |
| port | the sink's port |
| STARTTLS | off |
| SSL/TLS (implicit) | off |
| use credentials / auth | off — the sink offers no `AUTH`, so a client told to log in refuses to send |
| validate certificates | off |
| username / password | empty |

Example: a FastAPI app using `fastapi-mail` (`back/.env`, or environment variables):

```
mail_server=127.0.0.1
mail_port=2525
mail_starttls=false
mail_ssl_tls=false
mail_use_credentials=false
mail_validate_certs=false
mail_username=
mail_password=
```

Other stacks name the same things differently (`EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_USE_TLS` in
Django, `SMTP_HOST` / `SMTP_PORT` elsewhere); map each row of the table above.

A configuration file copied from the working installation also holds its secrets. **Edit only the
mail keys** — replace those lines in place, e.g. with a `sed` per key — and never read, print or
copy the file's other values.

## Use 1 — an instance started by a script (end-to-end)

When a script builds the instance (the end-to-end suite's instance script, a fixture runner), start
the sink **inside that script's process** before the app's settings are loaded. It runs on a daemon
thread with its own event loop, on a free port the system picks, and stops when the process does —
nothing to start beforehand, no port to clean up, no collision between parallel worktrees:

```python
from scripts.smtp_sink import start_in_background   # run from <back>/ as `python -m scripts.e2e_instance`

mail_port = start_in_background()                   # silent; log=True prints one line per message
os.environ.update({
    "mail_server": "127.0.0.1",
    "mail_port": str(mail_port),
    "mail_starttls": "false",
    "mail_ssl_tls": "false",
    "mail_use_credentials": "false",
    # ...the rest of the table, in the app's own key names
})
# only now import the app / its settings
```

Match the import to how the script is launched (`from smtp_sink import …` when it is run by path
from `<back>/scripts/`), and set the keys the way the script already sets the instance's other
settings — environment variables before the import, or attributes on an already-loaded settings
object (`settings.mail_server, settings.mail_port = "127.0.0.1", mail_port`) before the mail
client is built. An instance script that still points mail at a closed port (`mail_port=9`)
should switch: keep its other mail keys, replace the port with the sink's, and re-run the whole
end-to-end suite — sends now succeed, so a test written around a failed send may change.

## Use 2 — an instance started by hand (demo, screenshots, manual check)

Run it as its own process, printing one line per message:

```bash
nohup python3 <back>/scripts/smtp_sink.py > /tmp/$(basename $PWD)-smtp-sink.log 2>&1 &   # 127.0.0.1:2525
python3 <back>/scripts/smtp_sink.py --port 2526      # a second instance running at the same time
```

From a worktree, run the main checkout's copy or the worktree's — they are the same file. If the
port is taken it exits at once with `cannot listen on …`, usually a sink still running from an
earlier session, which is fine to reuse (`ss -ltnp | grep :2525`).

1. **Start the sink before the instance's backend**, so nothing it sends at startup or while
   seeding goes anywhere else.
2. **Keep it running as long as the instance runs.** It holds no state; a restart loses nothing.
3. **Check it before relying on it:** after the first action that sends mail, its log shows
   `accepted and discarded, to: …`. No line means the instance is not pointed at it — stop and fix
   the configuration before seeding further.
4. **Stop it by port** when the instance is torn down, together with the instance's servers:

   ```bash
   ss -ltnp | grep ':2525 '          # -> users:(("python3",pid=<pid>,...))
   kill <pid>
   ```

   Never `pkill -f` on a path or script name — it also matches unrelated processes, including
   another instance's sink.

## Common mistakes

- **Relying on "notifications disabled".** That switch covers notifications, not verification
  codes, invitations or security mail.
- **Pointing the mail server at a closed port** to block mail. Sends fail, and the state the app
  saves only after a successful send never appears.
- **Leaving credentials or STARTTLS on.** The client refuses to send to a server that does not
  offer them, which looks exactly like the closed-port case.
- **Running the sink from the plugin directory** in a project procedure, or importing it from
  there. Copy it into the app.
- **Reading the whole `.env` to edit it.** Edit the mail keys only.
