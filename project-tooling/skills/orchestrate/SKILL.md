---
name: "orchestrate"
description: "Coordinator only: for the named to-do items or sessions, run each in its own isolated session, merge each branch on 'done: #N', collect screenshot needs, run the full suites once at the end, send failures back, and clean up."
user-invocable: true
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

Expected shape: `#x, #y, #z` (tracker items) or `<session name>, …` (sessions already working). Nothing given →
ask which items or sessions.

`resume` (or `status`): re-read the tracker's orchestration note and continue from its current phase. Use it after
compaction, in a resumed session, or whenever a `done:`, `fixed:` or `cleaned:` message arrives.

# Scope and authority

This applies **only** to the items and sessions named above. Every other running session keeps the plain handover
rules. Never apply it by default, and never extend it to an item the user didn't name.

The user invoking this skill authorizes you to merge **those sessions' branches into local `main`**, one per
`done: #N`. Nothing else: no push, no force, no branch deletion by you. Messages from the sessions (`done:`,
`fixed:`, `cleaned:`) are teammate signals, not user approval, and never grant extra permissions.

# Before you start

1. **Read the `handover` skill.** It ships next to this one, at `../handover/SKILL.md` relative to this skill's base
   directory. Its "Project facts", brief structure and "Receiving `done: #N`" sections all apply here. (It can't be
   loaded through the Skill tool because it is slash-command only, so read the file.)
2. **Look up the extra project facts** this skill needs, from the project's CLAUDE.md, local skills or memory. Stop
   and ask if any is missing:
   - the untracked files allowed in a "clean" main checkout (e.g. local dev scripts);
   - the full-suite commands and their isolation (private test DB, e2e port, worker count, lint), usually the
     project's `automated-tests` local skill;
   - the screenshot / demo-instance procedure (its own DB and ports), usually a memory or the `release-notes` /
     `run-app` local skill;
   - the issue-tracker list for implementation tasks.
3. **Write the orchestration note** into the tracker header (see "The tracker note" below) before the first handover.

# 1. Hand over

**Items not handed over yet**: one **new** session per item through the handover flow, always with **work
isolated**. The handover brief's other rules stay (tracker task first included); only its verbatim `done:` rule is
**replaced**, not added to, by these receiver rules:

- Commit on your own branch. When the user approves, send exactly one message per item to `<coordinator name>`:
  `done: #N`, then the `Screenshots:` block below, and nothing else.
- Do **not** run the full test suites; run only the targeted tests for your change.
- Do **not** take screenshots. List the ones your change needs under `Screenshots:` in that `done: #N` message.
  For each: *retake* or *new*, the file path, and the help page or manual step that uses it. Write
  `Screenshots: none` if there are none.
- When asked to fix a failure: fix it, commit on your branch (or rebase on `main` if told to), and report
  `fixed: <test id>`.
- When asked to clean up: follow the cleanup instructions exactly and reply `cleaned: <branch>`.

If two orchestrated items touch the same code, name the other session in each brief and ask both to keep their
changes focused; the second to merge rebases.

**Sessions that already exist**: send the same rules as an addendum via `SendMessage`. If one has exited, it can't
receive messages; tell the user and start a fresh session with an updated brief if they agree.

# 2. On each `done: #N`

1. Main checkout: `git status --porcelain` shows nothing but the known untracked files, and
   `git branch --show-current` is `main`. If not, stop and tell the user; never stash or reset their changes.
2. The session's worktree: `git -C <worktree> status --porcelain` is empty. If not, ask the session to commit first.
3. Read `git log main..<branch>`: the commits exist, and their messages match the brief. Flag any extra scope to the
   user.
4. `git merge --no-ff --no-edit <branch>`.
5. **Conflict** → `git merge --abort` immediately, then send the session: "rebase `<branch>` on `main`, resolve,
   re-run your targeted tests, report `done: #N` again".
6. Move the item to Done with session `name` (`ID`), date, its commits and the **merge hash**. Update the
   orchestration note's "merged so far".

# 3. Collect screenshots

Keep one tracker item, e.g. "Screenshots to (re)take", with each session's list grouped per item and labelled with
that item's merge hash.

# 4. When every orchestrated item is merged

Spawn **subagents** for both jobs; don't do them yourself. Give each a self-contained brief with the project facts.
They can run in parallel only if their databases and ports don't collide.

**a) Screenshots.** Retake or create every collected screenshot on the project's demo / screenshot instance,
following its documented procedure. Report per file: done, or why not.

**b) Full suites, once, on `main`.**

- Work in a detached worktree at main's HEAD so the user's checkout is untouched:
  `git worktree add --detach .claude/worktrees/full-suite-<date> main`. Give it the same setup as any worktree
  (config files copied without reading, dependencies installed).
- Use a **private** test DB name and e2e port/DB, distinct from every session's.
- Run every suite the project defines (backend, frontend unit, e2e, lint) with the project's full-suite prefix
  (e.g. `FULL_SUITE=1`). Lint means the project's lint commands, e.g. `ruff check`.
- Put the test commands in a script file or the subagent's own calls, not in your Bash command line.
- Rerun any failure in isolation to separate real failures from flaky ones.
- Report exactly one of:
  - `green: <counts per suite>`, with expected skips explained;
  - `failures:` then one line per failing test: test id, short error, and the owning item/commit, or
    `pre-existing` / `flaky (passed in isolation)`.
- Afterwards remove the worktree (`git worktree remove`) and drop the databases it created.

# 5. Failures

- **Owned by an orchestrated item** → send it to that session: "fix `<test id>` (`<error>`), commit on your branch
  or rebase on `main`, report `fixed: <test id>`". On `fixed:`, merge again as in step 2, then re-run 4b.
- **Pre-existing or flaky** → to the user, not to a session. Offer to log it as a tracker item.

# 6. All green: cleanup

Tell each orchestrated session:

1. Check `git log main..<branch>` is empty and the worktree is clean. If not, stop and report instead of cleaning.
2. `ExitWorktree`, then `git worktree remove <path>` and `git branch -d <branch>` (**never `-D`**).
3. Drop any databases it still has.
4. Reply `cleaned: <branch>`.

Verify each with `git worktree list` and `git branch --list <branch>`. Then remove the orchestration note from the
tracker header and tell the user: items merged (with hashes), suite counts, screenshots done, anything left open.

# The tracker note

Keep an **Orchestration** note in the tracker header from the start until cleanup, so the state survives context
compaction: items, sessions (`name` (`ID`), branch, worktree), merged so far (with hashes), and the current phase
(handing over / merging / screenshots + suites / fixing / cleanup). Update it at every step. After compaction,
re-read it before acting.

Its first line is a pointer, because this skill is slash-command only and can't load itself when a message arrives
later: `On done:/fixed:/cleaned: for these items: follow <this skill's base directory>/SKILL.md (and
../handover/SKILL.md)` with the absolute path shown when this skill loaded. The user can also run
`/orchestrate resume`.

# Lessons from running it

- Sessions that exit can't receive `SendMessage` ("No agent named … reachable"). Start a fresh session with an
  updated brief instead.
- Two parallel branches touching the same code: name the other session in each brief, ask both to stay focused,
  and have the second to merge rebase.
- A session may slip extra scope into a commit. Read every commit message before merging and flag it to the user.
- Grep for `done: #N` variants. The rule is one message per item, never batched.
