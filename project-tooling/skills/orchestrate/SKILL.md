---
name: "orchestrate"
description: "Coordinator only: group the named to-do items or sessions into an orchestration group, run each in its own isolated session, merge each branch on 'done: #N', and once the whole group is merged retake its screenshots, run the full suites, send failures back and clean up. Groups run independently."
user-invocable: true
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

Expected shapes:

- `#x, #y, #z` (tracker items) or `<session name>, …` (sessions already working): create a **new orchestration
  group** with exactly those members. Nothing given → ask which items or sessions.
- `add #n [to <group>]`: add a member to an existing group that has not reached its final phase. Only when the
  user says so; a new `/orchestrate …` never joins an existing group.
- `status`: list every open group, its members, merged so far and its phase.
- `resume`: re-read the tracker's orchestration note and continue every open group from its current phase. Use it
  after compaction, in a resumed session, or whenever a `done:`, `fixed:` or `cleaned:` message arrives.

# Orchestration groups

Each `/orchestrate …` call creates its own **group** (an "orchestra"), with an ID: `O1`, `O2`, … (next free number
in the tracker note; never reuse one while it is open). Groups are independent:

- A group's **final phase** (screenshots, full suites, fixes, cleanup, steps 4 to 6) starts when **all of its own**
  members are merged, whatever other groups are doing. A group created later never delays an earlier one, and an
  earlier one never delays a later one.
- An item or session belongs to **one** group. If the user names one that is already in an open group, say which
  and ask before moving it.
- Steps 1 to 3 run per member as messages arrive; you route each `done: #N`, `fixed:` or `cleaned:` to the group
  that holds that item or session.
- Two groups can be in their final phase at the same time. Each full-suite run and screenshot run gets its **own**
  worktree, test DB and e2e port, distinct from every other group's and every session's.

# Scope and authority

This applies **only** to the items and sessions the user put in a group. Every other running session keeps the
plain handover rules. Never apply it by default, and never extend a group to an item the user didn't name.

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
3. **Add the group to the orchestration note** in the tracker header (see "The tracker note" below) before the
   first handover.

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

If two orchestrated items touch the same code (in the same group or in different ones), name the other session in each brief and ask both to keep their
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
6. Move the item to Done with session `name` (`ID`), date, its commits and the **merge hash**. Update its group's
   "merged so far" in the orchestration note.
7. If that was the group's last member, start the group's final phase (step 4).

Merges from different groups land on the same local `main`, one at a time; never run two merges at once.

# 3. Collect screenshots

Keep one tracker item per group, e.g. "Screenshots to (re)take (O2)", with each session's list grouped per item and
labelled with that item's merge hash.

# 4. When every member of a group is merged

This step and the next two are per group. Work only on the group whose members are all merged.

Spawn **subagents** for both jobs; don't do them yourself. Give each a self-contained brief with the project facts.
They can run in parallel only if their databases and ports don't collide.

**a) Screenshots.** Retake or create every screenshot collected for **this group** on the project's demo /
screenshot instance, following its documented procedure, at main's current HEAD. Report per file: done, or why
not. If another group is using the demo instance at that moment, wait for it; it has one DB and one set of ports.

**b) Full suites, once, on `main`.**

- Work in a detached worktree at main's HEAD so the user's checkout is untouched:
  `git worktree add --detach .claude/worktrees/full-suite-<group>-<date> main`. Give it the same setup as any worktree
  (config files copied without reading, dependencies installed).
- Use a **private** test DB name and e2e port/DB, distinct from every session's and every other group's run.
- Record the tested commit (`git rev-parse HEAD` in that worktree). It may contain merges from other groups that are
  still in progress; that is expected.
- Run every suite the project defines (backend, frontend unit, e2e, lint) with the project's full-suite prefix
  (e.g. `FULL_SUITE=1`). Lint means the project's lint commands, e.g. `ruff check`.
- Put the test commands in a script file or the subagent's own calls, not in your Bash command line.
- Rerun any failure in isolation to separate real failures from flaky ones.
- Report exactly one of:
  - `green: <counts per suite>`, with expected skips explained;
  - `failures:` then one line per failing test: test id, short error, and the owning item/commit (with its group,
    or none), or `pre-existing` / `flaky (passed in isolation)`.
- Afterwards remove the worktree (`git worktree remove`) and drop the databases it created.

# 5. Failures

- **Owned by an item of this group** → send it to that session: "fix `<test id>` (`<error>`), commit on your branch
  or rebase on `main`, report `fixed: <test id>`". On `fixed:`, merge again as in step 2, then re-run 4b for this
  group.
- **Owned by an item of another open group** → doesn't block this group. Send it to that item's session the same
  way, and record it against **that** group in the note; that group's own final run must come back green. On its
  `fixed:`, merge as in step 2. This group proceeds to cleanup once every failure it owns is fixed.
- **Owned by a merged commit outside any group** (e.g. the user's own work) → to the user, not to a session.
- **Pre-existing or flaky** → to the user, not to a session. Offer to log it as a tracker item.

# 6. Group green: cleanup

A group is green when its last full-suite run has no failure owned by one of its members. Tell each session **of
that group**:

1. Check `git log main..<branch>` is empty and the worktree is clean. If not, stop and report instead of cleaning.
2. `ExitWorktree`, then `git worktree remove <path>` and `git branch -d <branch>` (**never `-D`**).
3. Drop any databases it still has.
4. Reply `cleaned: <branch>`.

Verify each with `git worktree list` and `git branch --list <branch>`. Then remove **that group** from the
orchestration note (the whole note once no group is open) and tell the user: the group, items merged (with hashes),
the tested commit and suite counts, screenshots done, anything left open, and any failure handed to another group.

# The tracker note

Keep one **Orchestration** note in the tracker header while any group is open, so the state survives context
compaction. One entry per group:

- group ID and creation date;
- members: item, session `name` (`ID`), branch, worktree;
- merged so far (with hashes);
- current phase (handing over / merging / screenshots + suites / fixing / cleanup);
- open failures it owns, including ones found by another group's run;
- the full-suite worktree, test DB and port in use, if any.

Update it at every step. After compaction, re-read it before acting.

Its first line is a pointer, because this skill is slash-command only and can't load itself when a message arrives
later: `On done:/fixed:/cleaned: for an orchestrated item: follow <this skill's base directory>/SKILL.md (and
../handover/SKILL.md)` with the absolute path shown when this skill loaded. The user can also run
`/orchestrate resume`.

# Lessons from running it

- Sessions that exit can't receive `SendMessage` ("No agent named … reachable"). Start a fresh session with an
  updated brief instead.
- Two parallel branches touching the same code: name the other session in each brief, ask both to stay focused,
  and have the second to merge rebase.
- A session may slip extra scope into a commit. Read every commit message before merging and flag it to the user.
- Grep for `done: #N` variants. The rule is one message per item, never batched.
- Know which group a message belongs to before acting on it. A `done:` for a group-O1 item must never start
  group O2's final phase.
