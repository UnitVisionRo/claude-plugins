---
name: "orchestrate"
description: "Coordinator only: hand work items to other Claude sessions and see them through to merged, tested work."
user-invocable: true
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

Expected shapes:

- `#x[, #y, …] [options]` (tracker items) or `<session name>, …` (sessions already working): create a **new
  orchestration group** with exactly those members. One item is a group of one. Nothing given → ask which items or
  sessions. Options, any combination, in the user's own words:
  - **to `<session>`**: hand the item(s) to that existing session instead of starting a new one;
  - **batch**: several items go to one session instead of one session per item;
  - **work isolated**: the receiver works in its own worktree and branch off local `main`;
  - **main checkout**: the receiver edits the main checkout directly, no worktree;
  - a model/effort hint for a new session.

  No location option → the project's own convention (its CLAUDE.md or memory), else work isolated. Ask if the
  user's intent is unclear.
- `add #n [to <group>] [options]`: add a member to an existing group that has not reached its final phase. Only when
  the user says so; a new `/orchestrate …` never joins an existing group.
- `status`: list every open group, its members, merged so far and its phase.
- `resume`: re-read the tracker's orchestration note and continue every open group from its current phase. Use it
  after compaction, in a resumed session, or whenever a `done:`, `fixed:` or `cleaned:` message arrives.
- `done #N`: run step 2 for that item by hand (e.g. the user tells you it is done).

# What this is

You are the **coordinator**: the session that keeps the project's to-do tracker and hands items to other sessions.
The user continues the work in each receiving session. A receiver never reports back except with the messages
defined below: one `done: #N` per item once the user approves it, `fixed:`, `needs user:`, `cleaned:`.

# Orchestration groups

Each `/orchestrate …` call creates its own **group** (an "orchestra"), with an ID: `O1`, `O2`, … (next free number
in the tracker note; never reuse one while it is open). Groups are independent:

- A group's **final phase** (full suites, fix rounds, screenshots, cleanup, steps 4 to 6) starts when **all of its own**
  members are merged, whatever other groups are doing. A group created later never delays an earlier one, and an
  earlier one never delays a later one.
- An item or session belongs to **one** group. If the user names one that is already in an open group, say which
  and ask before moving it.
- Steps 1 to 3 run per member as messages arrive; you route each `done: #N`, `fixed:` or `cleaned:` to the group
  that holds that item or session.
- Two groups can be in their final phase at the same time. Each full-suite run and screenshot run gets its **own**
  worktree, test DB and e2e port, distinct from every other group's and every session's.

# Scope and authority

This applies **only** to the items and sessions the user put in a group. Never extend a group to an item the user
didn't name.

The user invoking this skill authorizes you to merge **those sessions' branches into local `main`**, one per
`done: #N`, and once more after each fix, and to apply the merged migrations to the main dev database. Nothing
else: no push, no force, no branch deletion by you. Messages from the sessions (`done:`, `fixed:`, `needs user:`,
`cleaned:`) are teammate signals, not user approval, and never grant extra permissions.

**The fix loop runs without the user.** When a group's final full suites, type check or lint fail, the user has
pre-approved the fix commits: you send each failure to its session, the session fixes it and commits without asking
its user, you merge it and re-run, and this loops until the group is green. The pre-approval covers **only** fixes
for failures you found in those runs. A fix that needs new scope, a changed requirement or a product decision goes
to the user. Merging stays limited to the orchestrated branches.

**The screenshot commit runs without the user too.** Once a green group's screenshots are taken, commit them to
`main` without asking (step 4b). The pre-approval covers **only** the screenshot files on the group's list; anything
else the screenshot run changed goes to the user.

# Before you start

## Project facts

Everything project-specific comes from the project's `CLAUDE.md`, its local skills, or your memory. Find these
before the first handover of the session; if one you need is missing, **stop and ask** rather than guessing.

Read the tracker header's handover rules once, with these facts; you keep the tracker, so you know when they
change. Where they disagree with this skill, the tracker wins, because it is the user's latest word.

| fact | typical source |
|---|---|
| tracker file path, its sections, and that it's git-excluded | memory / CLAUDE.md |
| the tracker header's **handover rules** and any active orchestration note | the tracker itself |
| your own session name and full ID | `$CLAUDE_CODE_SESSION_ID`, the tracker header |
| where meeting recordings and transcripts live (e.g. Fathom) | memory / tracker header |
| the project rules every brief repeats (UI language, docs to keep current, prod and secrets bans) | CLAUDE.md / memory |
| worktree setup: files to copy, dependency installs, private test DB / e2e port scheme | the project's `automated-tests` local skill, memory |
| the untracked files allowed in a "clean" main checkout (e.g. local dev scripts) | memory / CLAUDE.md |
| the full-suite commands and their isolation (private test DB, e2e port, worker count, lint) | the project's `automated-tests` local skill |
| the screenshot / demo-instance procedure (its own DB and ports) | memory, the `release-notes` / `run-app` local skill |
| the issue-tracker list for implementation tasks | memory / CLAUDE.md |
| the migrations directory and the commands that list the migration heads and apply them to the main dev database from the main checkout (e.g. `uv run alembic heads`, `uv run alembic upgrade head`); not needed without migrations | CLAUDE.md / the `alembic` skill / memory |

**Session identity.** Every session is written in the tracker as `name` (`full session ID`), because names change
and IDs don't. A full ID is a UUID. It is the transcript `~/.claude/projects/<project-slug>/<ID>.jsonl` (look for
the `customTitle` records to match a name) or `~/.claude/jobs/<8hex>/state.json` → `sessionId`. ListAgents refs
such as `[6c8ba8]` are **not** session IDs.

## The group

Add the group to the orchestration note in the tracker header (see "The tracker note" below) before the first
handover.

# 1. Hand over

## a) Build the brief

The brief is the receiver's **only** context. It must stand alone: no "as discussed", no references to your
conversation. Structure:

1. **Item(s)**: number and full text from the tracker, for each item.
2. **What you already know**: code pointers you found (`file:line`), related items and out-of-scope items (by
   number and one line each), and the project's terminology for the domain.
3. **Source evidence**: the relevant quotes from the meeting transcripts, each with a timestamped link to the
   recording. Fetch the transcript (e.g. Fathom `get_recording_by_url` → `get_meeting_transcript`). A large
   transcript is saved to a file; read **all** of it in chunks, don't stop at the first hit.
4. **Receiver rules**, verbatim (with the coordinator's name and the URLs filled in):
   - Before any work, create an implementation task for the item(s) in `<issue-tracker list URL>`, following
     `dev-workflow:clickup-task-updates` if it is installed.
   - The user continues the work in this session. Never send progress reports or questions to the coordinator;
     the only messages you send it are the ones below.
   - Commit only when the user approves an item: on your own branch (work isolated) or on `main` (main checkout).
     With several items, commit each separately. Then send exactly one message per item to `<coordinator name>`:
     ```
     done: #N
     Migrations: <each migration file the item adds> | none
     Screenshots: <one line per screenshot: retake|new, file path, the help page or manual step that uses it> | none
     ```
     and nothing else.
   - Do **not** run the full test suites; run only the targeted tests for your change.
   - Do **not** take screenshots; list the ones your change needs under `Screenshots:`.
   - Migrations: the coordinator applies them to the main dev database when it merges. Once your work is on
     `main`, never edit or delete a migration it contains: the dev database already ran it. A later schema change,
     including one a fix needs, adds a **new** migration.
   - When the coordinator sends you failures from the final full suites, type check or lint: fix them and commit
     (or rebase on `main` if told to) **without waiting for the user's approval**. The user pre-approves these fix
     commits, and only these: fix just the reported failures. Then send **one** reply covering every failure in
     that message: `fixed: <test id>, …`, plus a `Migrations:` line and a `Screenshots:` block as above (`none`
     when the fix changes neither). If a fix needs new scope, a changed requirement or a product decision, don't
     commit it: ask the user here, and send the coordinator `needs user: <test id>` so it knows the loop is waiting.
   - When asked to clean up: follow the cleanup instructions exactly and reply `cleaned: <branch or "main checkout">`.
5. **Project rules reminder**: the UI language; flag stale docs instead of leaving them; never run anything against
   production; never read `.env` or other secret files. Add whatever else the project's CLAUDE.md treats as
   standing rules.
6. **Where to work**, spelled out in full (below).
7. **Parallel work**: if another open session touches the same code (in this group or another), name it (`name`
   (`ID`), item, branch) and ask both to keep their changes focused. Whoever merges second rebases.

### Work isolated

Spell out in the brief:

- `git worktree add .claude/worktrees/<name> -b <name> main` (local `main`, not `origin/main`), then enter it with
  `EnterWorktree` and that path.
- The setup the project needs in a fresh worktree: copy the untracked config/env files **as files, without reading
  them** (`cp`, never `cat`), and install dependencies. Take the exact list from the project's facts.
- A private test database name and a private e2e port and database, **unique across every parallel session**.
  Check the tracker and other open briefs so no two sessions share one.
- Never run migrations against the main dev database from the worktree.
- Don't touch the main checkout's dev servers.
- Drop every database it created before cleanup.

### Main checkout

The receiver edits the main checkout directly. Say so, and name any other session working in the same checkout. It
still uses a private test database for its tests, and the migrations rule above holds: the coordinator applies them
at `done:`. Only if the user asks to try the change in the dev servers before approving may the receiver upgrade the
main dev database itself; from then on that migration is frozen like a merged one (a change adds a new migration).
Its commits, fix commits included, land directly on `main`.

While such a receiver has uncommitted work, the main checkout is not clean, so merges of other members wait (step
2.1). Tell the user when that happens.

## b) Deliver the brief

**New session** (the default):

1. Write the brief to a file in your scratchpad.
2. From the repo root: `claude --bg --name <name> [--model <m>] [--effort <e>] "$(cat <brief-file>)"`.
   Never put the brief text, and above all **never a test command**, literally on the Bash command line: a
   test-scoping hook matches the command line and will deny it. `$(cat …)` keeps it off.
3. The output `backgrounded · <8hex> · <name>` gives the job ID. Read the full session ID from
   `~/.claude/jobs/<8hex>/state.json` → `sessionId`.
4. Model and effort: judge the task (a small UI tweak → lower effort; tricky domain logic or a multi-phase spec →
   higher). When unsure, pass neither and keep the defaults. Tell the user what you chose and why.

Name sessions after the item, e.g. `todo-<N>-<short-slug>`.

**Existing session** (`to <session>`, or a group of sessions already working). Load `SendMessage` (and
`ListAgents` to find it) via ToolSearch, then send an **addendum** with the same structure as a full brief. If the
session has exited ("No agent named … reachable"), it can't receive messages: tell the user and, if they agree,
start a new session with an updated brief instead.

The fix-commit pre-approval only holds where the receiver can trust it came from the user. A new session gets it in
its brief (its starting prompt). An existing session receiving it by `SendMessage` will rightly treat it as a
teammate's message, not as its user's approval. So for existing sessions, also ask the user to paste the fix-commit
rule into that session themselves, or the loop will stop at each fix waiting for approval.

## c) Record it

On the item: `Handed off to session \`<name>\` (\`<full ID>\`) (<YYYY-MM-DD>)[, worktree <path>, branch <branch>]`.
Add it to the group's members in the orchestration note and update the header's "Last updated" line.

## d) Tell the user

What went to which session, the model/effort chosen (MANDATORY), and how to pick it up: `claude attach <8hex>` for a new
background session.

# 2. On each `done: #N`

Grep incoming messages for `done:` variants (`done #N`, `Done: #N`, …). The rule is one message per item; if one
message names several items, handle each separately and mention the deviation to the user.

**An item in no group** (handed over before handover was folded into this skill, or outside it): verify as in
1 to 3, apply its migrations only if it is already on `main` (5 and 7), and move it to Done (8). Never merge it;
tell the user it is ready to merge, and apply its migrations once they say it is merged.

1. **Main checkout clean**: `git status --porcelain` shows nothing but the known untracked files, and
   `git branch --show-current` is `main`. If not, stop and tell the user; never stash or reset their changes.
2. **The work is committed.** Work isolated: `git -C <worktree> status --porcelain` is empty (if not, ask the session
   to commit first), and `git log main..<branch>` lists the commits. If it is empty, check
   `git branch --merged main`: the user may have merged it already; then skip the merge (step 4) and go on. Main checkout: find the item's commits on `main`
   by message or by the session's files. Nothing committed → tell the user instead of going on.
3. **Read the commit messages**: they match the brief. Flag to the user anything beyond it: extra scope, a changed
   approach, a skipped requirement.
4. **Merge** (work isolated only; main-checkout commits are already on `main`):
   `git merge --no-ff --no-commit <branch>`. **Conflict** → `git merge --abort` immediately, then send the session:
   "rebase `<branch>` on `main`, resolve, re-run your targeted tests, report `done: #N` again".
5. **Migration heads.** The `Migrations:` line says whether the item brings any; confirm it against the change
   (`git diff --cached --name-only -- <dir>` during the merge, or the item's commits on `main`), and trust the diff
   if they disagree (tell the session). A `done:` without the line gets the same check. If there are migrations,
   list the heads. More than one head (two branches each added a migration on the same parent):
   - during a merge → `git merge --abort`, then send the session: "rebase `<branch>` on `main` and re-point your
     migration's parent at main's current head (don't edit any migration already on `main`), re-run your targeted
     tests, report `done: #N` again";
   - already on `main` (main checkout) → tell the user; don't upgrade.
6. `git commit --no-edit` (if you merged).
7. **Apply the migrations to the main dev database.** If the item brought migrations, run the project's upgrade
   command from the main checkout right away, then confirm the database is at head. Isolated sessions never
   migrate the main dev DB, so without this it drifts behind `main` and the user's dev servers break on the new
   code. (After a main-checkout receiver it is often a no-op.) If the upgrade fails, stop and tell the user with
   its output; never downgrade, stamp or edit the database to get past it. Fix merges in step 5 get the same
   treatment.
8. **Move the item to Done** with session `name` (`ID`), date, its commits and the **merge hash** (if merged).
   Update its group's "merged so far" in the orchestration note and the header's "Last updated". If you mark the
   Done entry with the group or round while the group is open, that label goes at cleanup (step 6).
9. Add its `Screenshots:` lines to the group's list (step 3).
10. If that was the group's last member, start the group's final phase (step 4).

Merges from different groups land on the same local `main`, one at a time; never run two merges at once. Each
merge's migrations are applied before the next merge starts.

# 3. Collect screenshots

Collect each group's screenshot list in the tracker while the group is open: in the project's screenshots item if
it has one, under a heading for the group, or else in a temporary item, e.g. "Screenshots to (re)take (O2)". Group
the lines per item, labelled with that item's merge hash. The list is **temporary**: it is removed at cleanup
(step 6), and a shared screenshots item goes back to its plain "nothing open" state once no group has a list in it.

# 4. When every member of a group is merged

This step and the next two are per group. Work only on the group whose members are all merged.

**Minimize runs.** Full suites and screenshots are slow; that is why orchestration exists. Each run must cover as
many changes as possible:

- The full suites run once when the group's last member is merged, then **once per fix round**, and only after
  **every** fix of that round is merged (step 5). Never re-run for a single fix while others are outstanding.
- Screenshots are taken **once**, after the group is green, so they show the final code and never need retaking
  because of a fix.

Spawn **subagents** for both jobs; don't do them yourself. Give each a self-contained brief with the project facts.

**a) Full suites on `main`.**

- Work in a detached worktree at main's HEAD so the user's checkout is untouched:
  `git worktree add --detach .claude/worktrees/full-suite-<group>-<date> main`. Give it the same setup as any worktree
  (config files copied without reading, dependencies installed).
- Use a **private** test DB name and e2e port/DB, distinct from every session's and every other group's run.
- Record the tested commit (`git rev-parse HEAD` in that worktree). It may contain merges from other groups that are
  still in progress; that is expected.
- Run every suite the project defines (backend, frontend unit, e2e, type check, lint) with the project's full-suite prefix
  (e.g. `FULL_SUITE=1`). Lint means the project's lint commands, e.g. `ruff check`.
- Put the test commands in a script file or the subagent's own calls, not in your Bash command line.
- Rerun any failure in isolation to separate real failures from flaky ones.
- Report exactly one of:
  - `green: <counts per suite>`, with expected skips explained;
  - `failures:` then one line per failing test: test id, short error, and the owning item/commit (with its group,
    or none), or `pre-existing` / `flaky (passed in isolation)`.
- Afterwards remove the worktree (`git worktree remove`) and drop the databases it created.

**b) Screenshots, once the group is green** (step 5 found nothing left that it owns). Retake or create every
screenshot collected for **this group**, including those added by fix replies, on the project's demo / screenshot
instance, following its documented procedure, at main's current HEAD. Report per file: done, or why not. If
another group is using the demo instance at that moment, wait for it; it has one DB and one set of ports.

Then **review and commit them yourself, without asking the user** (see "Scope and authority"):

1. **Review** every screenshot file: open it and check it shows the page or step its help page / manual step
   describes, in the final state of the change, with demo data, no error, spinner, empty or half-loaded state, and
   the project's usual size and framing.
2. **Not OK** → send the subagent back to retake only those files, once, saying what is wrong. Still wrong, or
   reported as not done → leave them uncommitted and tell the user which files and why.
3. **OK** → in the main checkout (clean apart from the known untracked files and these screenshots, as in step 2.1;
   copy the files there first if the run wrote them elsewhere), stage **only** the reviewed screenshot files on the
   group's list, by path, and commit them on `main` following the project's commit-message rules. Never stage
   anything else the run changed; report it to the user instead. Record the commit hash for the final report.

# 5. Failures: one fix round at a time

Loop on your own until the group is green; don't stop to ask the user between rounds (see "The fix loop runs
without the user" above). A **round** is: sort the run's failures, send all the fixes out at once, wait for all of
them, merge, re-run once.

- **Owned by an item of this group** → group the failures by session and send **one message per session** listing
  all of its failures: "final-suite failures `<test id>` (`<error>`), …: fix them and commit (or rebase on `main`)
  without waiting for approval (the user pre-approved fix commits for this orchestration), then reply once with
  `fixed: <test ids>`". On each `fixed:`, check the new commits only fix those failures (flag anything else to the
  user) and modify or delete no migration already on `main` (send it back if one does), merge as in step 2
  (migrations applied included), and add any `Screenshots:` lines to the group's list.
- **Owned by an item of another open group** → doesn't block this group. Send it to that item's session the same
  way, and record it against **that** group in the note; that group's own final run must come back green. On its
  `fixed:`, merge as in step 2. This group proceeds once every failure it owns is fixed.
- **Wait for the whole round.** Re-run 4a only when **every** session sent fixes in this round has replied `fixed:`
  and been merged. Keep the round's outstanding sessions in the tracker note.
- **`needs user: <test id>`** → that session's fix is still part of the round, so the re-run keeps waiting for it.
  Tell the user which session needs them and why. Re-run without it only if the user says so.
- **Owned by a merged commit outside any group** (e.g. the user's own work) → to the user, not to a session.
- **Pre-existing or flaky** → to the user, not to a session. Offer to log it as a tracker item.

# 6. Group green: cleanup

A group is green when its last full-suite run has no failure owned by one of its members. Start its screenshots
(4b) and, in parallel, tell each session **of that group**:

1. Work isolated: check `git log main..<branch>` is empty and the worktree is clean. If not, stop and report instead
   of cleaning. Then `ExitWorktree`, `git worktree remove <path>` and `git branch -d <branch>` (**never `-D`**).
2. Drop any databases it still has.
3. Reply `cleaned: <branch>` (or `cleaned: main checkout`).

Verify each isolated one with `git worktree list` and `git branch --list <branch>`.

**Remove every record of the group** once its screenshots are done and every session has replied `cleaned:`. The
tracker keeps an orchestration only while it is in progress; no history afterwards:

- its entry in the header's orchestration note (the whole note, pointer line included, once no group is open);
- its screenshot list and any per-round history (a shared screenshots item goes back to "nothing open");
- every group or round label it left elsewhere, e.g. "Orchestration O2" or "round 2" in Done entries, and the
  "Handed off to session …" lines of its items.

The Done entries themselves stay: item, session `name` (`ID`), date, commits, merge hash.

Then tell the user: the group, items merged (with hashes), the migrations applied to the main dev database,
the tested commit and suite counts, the number of full-suite runs, screenshots done and their commit hash, anything
left open, and any failure handed to another group.

# The tracker note

Keep one **Orchestration** note in the tracker header while any group is open, so the state survives context
compaction. It is working state, not history: each group's entry goes at that group's cleanup (step 6). One entry
per group:

- group ID and creation date;
- members: item, session `name` (`ID`), where it works (worktree + branch, or main checkout);
- merged so far (with hashes);
- current phase (handing over / merging / full suites / fix round N, waiting on <sessions> / screenshots /
  cleanup);
- open failures it owns, including ones found by another group's run;
- the full-suite worktree, test DB and port in use, if any.

Update it at every step. After compaction, re-read it before acting.

Its first line is a pointer, because this skill is slash-command only and can't load itself when a message arrives
later: `On done:/fixed:/needs user:/cleaned: from a receiver: follow <this skill's base directory>/SKILL.md` with the
absolute path shown when this skill loaded. The user can also run `/orchestrate resume`.

# Lessons from running it

- Sessions that exit can't receive `SendMessage` ("No agent named … reachable"). Start a fresh session with an
  updated brief instead.
- Two parallel branches touching the same code: name the other session in each brief, ask both to stay focused,
  and have the second to merge rebase.
- A session may slip extra scope into a commit. Read every commit message before merging and flag it to the user.
- Grep for `done: #N` variants. The rule is one message per item, never batched.
- Know which group a message belongs to before acting on it. A `done:` for a group-O1 item must never start
  group O2's final phase.
