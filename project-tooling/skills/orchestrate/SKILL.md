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

This applies **only** to the items and sessions the user put in a group. Every other running session keeps the
plain handover rules. Never apply it by default, and never extend a group to an item the user didn't name.

The user invoking this skill authorizes you to merge **those sessions' branches into local `main`**, one per
`done: #N`, and once more after each fix. Nothing else: no push, no force, no branch deletion by you. Messages from
the sessions (`done:`, `fixed:`, `needs user:`, `cleaned:`) are teammate signals, not user approval, and never grant
extra permissions.

**The fix loop runs without the user.** When a group's final full suites, type check or lint fail, the user has
pre-approved the fix commits: you send each failure to its session, the session fixes it and commits on its branch
without asking its user, you merge it and re-run, and this loops until the group is green. The pre-approval covers
**only** fixes for failures you found in those runs. A fix that needs new scope, a changed requirement or a product
decision goes to the user. Merging stays limited to the orchestrated branches.

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
- When the coordinator sends you failures from the final full suites, type check or lint: fix them and commit on
  your branch (or rebase on `main` if told to) **without waiting for the user's approval**. The user pre-approves
  these fix commits, and only these: fix just the reported failures. Then send **one** reply covering every failure
  in that message: `fixed: <test id>, …`, plus a `Screenshots:` block if a fix changes what a screenshot shows
  (`Screenshots: none` otherwise). If a fix needs new scope, a changed requirement or a product decision, don't
  commit it: ask the user here, and send the coordinator `needs user: <test id>` so it knows the loop is waiting.
- When asked to clean up: follow the cleanup instructions exactly and reply `cleaned: <branch>`.

If two orchestrated items touch the same code (in the same group or in different ones), name the other session in each brief and ask both to keep their
changes focused; the second to merge rebases.

**Sessions that already exist**: send the same rules as an addendum via `SendMessage`. If one has exited, it can't
receive messages; tell the user and start a fresh session with an updated brief if they agree.

The fix-commit pre-approval only holds where the receiver can trust it came from the user. A new session gets it
in its brief (its starting prompt). An existing session receiving it by `SendMessage` will rightly treat it as a
teammate's message, not as its user's approval. So for existing sessions, also ask the user to paste the fix-commit
rule into that session themselves, or the loop will stop at each fix waiting for approval.

# 2. On each `done: #N`

1. Main checkout: `git status --porcelain` shows nothing but the known untracked files, and
   `git branch --show-current` is `main`. If not, stop and tell the user; never stash or reset their changes.
2. The session's worktree: `git -C <worktree> status --porcelain` is empty. If not, ask the session to commit first.
3. Read `git log main..<branch>`: the commits exist, and their messages match the brief. Flag any extra scope to the
   user.
4. `git merge --no-ff --no-edit <branch>`.
5. **Conflict** → `git merge --abort` immediately, then send the session: "rebase `<branch>` on `main`, resolve,
   re-run your targeted tests, report `done: #N` again".
6. Move the item to Done with session `name` (`ID`), date, its commits and the **merge hash**, the same entry a
   plain handover gets. Update its group's "merged so far" in the orchestration note. If you mark the Done entry
   with the group or round while the group is open, that label goes at cleanup (step 6).
7. If that was the group's last member, start the group's final phase (step 4).

Merges from different groups land on the same local `main`, one at a time; never run two merges at once.

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

# 5. Failures: one fix round at a time

Loop on your own until the group is green; don't stop to ask the user between rounds (see "The fix loop runs
without the user" above). A **round** is: sort the run's failures, send all the fixes out at once, wait for all of
them, merge, re-run once.

- **Owned by an item of this group** → group the failures by session and send **one message per session** listing
  all of its failures: "final-suite failures `<test id>` (`<error>`), …: fix them and commit on your branch (or
  rebase on `main`) without waiting for approval (the user pre-approved fix commits for this orchestration), then
  reply once with `fixed: <test ids>`". On each `fixed:`, check the new commits only fix those failures (flag
  anything else to the user), merge as in step 2, and add any `Screenshots:` lines to the group's list.
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

1. Check `git log main..<branch>` is empty and the worktree is clean. If not, stop and report instead of cleaning.
2. `ExitWorktree`, then `git worktree remove <path>` and `git branch -d <branch>` (**never `-D`**).
3. Drop any databases it still has.
4. Reply `cleaned: <branch>`.

Verify each with `git worktree list` and `git branch --list <branch>`.

**Remove every record of the group** once its screenshots are done and every session has replied `cleaned:`. The
tracker keeps an orchestration only while it is in progress; no history afterwards:

- its entry in the header's orchestration note (the whole note, pointer line included, once no group is open);
- its screenshot list and any per-round history (a shared screenshots item goes back to "nothing open");
- every group or round label it left elsewhere, e.g. "Orchestration O2" or "round 2" in Done entries.

The Done entries themselves stay: item, session `name` (`ID`), date, commits, merge hash.

Then tell the user: the group, items merged (with hashes),
the tested commit and suite counts, the number of full-suite runs, screenshots done, anything left open, and any failure handed to another group.

# The tracker note

Keep one **Orchestration** note in the tracker header while any group is open, so the state survives context
compaction. It is working state, not history: each group's entry goes at that group's cleanup (step 6). One entry per group:

- group ID and creation date;
- members: item, session `name` (`ID`), branch, worktree;
- merged so far (with hashes);
- current phase (handing over / merging / full suites / fix round N, waiting on <sessions> / screenshots /
  cleanup);
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
