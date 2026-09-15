---
name: "spec-driven-development"
description: "The phase → chunk → review workflow for planning and implementing functional specs. Use when building a feature from a spec, splitting a phase into chunks, planning or reviewing an implementation phase, or deciding when to commit. Defines where specs and plans live, how code references them, and the commit and review rules that override the superpowers defaults."
---

# Spec-driven development

The workflow for planning and implementing functional specs: a phase is split into chunks,
each chunk is planned, implemented and reviewed, and the phase is reviewed as a whole before a
human sees it.

## ⚠️ Precedence over the `superpowers` plugin

This workflow **uses** several superpowers skills, and **overrides** them where they disagree.
When `superpowers` is loaded, the rules below win. Where they are silent, follow superpowers.

| Topic | superpowers says | **This workflow says (wins)** |
|---|---|---|
| Review granularity | `subagent-driven-development`: launch a reviewer subagent per **task** | Review **per chunk**, never per task. There are exactly **two** review layers — see Self review rules. |
| Committing during work | Several skills commit as they go (`brainstorming` commits the design doc; `executing-plans` and `finishing-a-development-branch` commit progress) | **Never commit** except where this workflow explicitly allows it, and never without the user's instruction — see Commit rules. |
| Design docs | `brainstorming`: write to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and commit it | Specs live in **`docs/spec/<YY-MM-DD>-<feature_name>/`** and are **not** committed on the skill's own initiative. |
| Finishing a branch | `finishing-a-development-branch` decides how to integrate | The phase ends at **STEP 5**; integration is the user's call. |

Skills this workflow **does** invoke, unchanged: `/superpowers:writing-plans` (STEP 1) and
`/superpowers:subagent-driven-development` (STEP 2a, minus its per-task review).

## Spec and plan file locations

- **Functional spec**: `docs/spec/<YY-MM-DD>-<feature_name>/` — the source of truth for the
  platform's behavior. If the feature needs only a single file, name it
  `<YY-MM-DD>-<feature_name>.md`.
- **Plans**: `docs/spec/<YY-MM-DD>-<feature_name>/plans/` — the implementation plan for a
  feature, derived from the spec. Kind of like a "compiler" for the spec: it translates the
  spec into a concrete, actionable plan for implementation. Each plan is **phase-specific** and
  may be broken into multiple chunks, each with its own independently testable deliverable.

## Spec-grounded features

When building a feature grounded in the spec, add a code comment referencing the relevant spec
section **and the file that section lives in** — reference only, never the full spec text:

```python
# <YY-MM-DD>-<feature_name>/<file_name> §06 R6.3
```

**The file name is not optional.** Instead of `# Identificare prin id (§4.4)`, write
`# Identificare prin id (§4.4, <spec file path>)`. Mentioning only the section number is
useless without the file path, because **the same section number appears in multiple specs** —
`§4.4` alone cannot be resolved. This maintains traceability between code and the functional
spec.

## The workflow

Split each phase into the most atomic dev chunks possible. For **each phase**, execute the
workflow below. If chunks can be parallelized, do so with a general-purpose subagent. If using
subagents for parallelization, the planning must be done with the same model as yourself
(inherit). Relay any questions from the subagent to the user for clarification.

Build a DAG of chunk dependencies, and parallelize where possible. When chunks run in parallel
as a **batch**, STEP 1 (plan) and STEP 2 (implementation loop) run per-chunk concurrently, but
STEP 4 (human review) and STEP 5 (tracker update) are performed **once for the whole batch** —
not once per chunk.

<workflow>
<for-each-chunk>
STEP 1 — PLAN
  - Use a subagent to write the plans using the /superpowers:writing-plans skill
  - Subagent model selection: since planning is the most important part of the workflow, you
    must use opus or fable (when available) for planning. However, be mindful of the usage
    costs and choose fable only if the plan is very complex and requires a lot of reasoning.

STEP 2 — IMPLEMENTATION LOOP
  2a. Implement the plan with /superpowers:subagent-driven-development. Model selection is
      decided by the skill. Do NOT launch a review subagent for each task in this step,
      contrary to what the skill says. **Reviews** are done **per chunk**.
  2b. Self review the chunk.
  2c. If review found issues: fix them, then return to STEP 2a
      If review is clean: proceed to next chunk

  Do not commit during this step. Instruct the subagent to accumulate all changes in the
  working tree.
</for-each-chunk>

STEP 3 — SUBAGENT REVIEW LOOP
  3.a Use a subagent (model: opus) to perform a review of the whole phase implementation. If all good, commit the phase and proceed to STEP 4;
      otherwise go to 3.b
  3.b If review found issues, fix them with subagents. Choose suitable models for each fix:
      simple fixes -> fast / cheap model, complex fix -> capable / more expensive models.
      After fixes, proceed to 3.a, re-review. Don't ask for a re-review of what was already
      reviewed and not impacted by the fixes.

STEP 4 — HUMAN REVIEW (human evaluates the whole phase)
  - DO NOT commit per fix during the human review. Fixes made in response to the human's
    review comments accumulate UNCOMMITTED in the working tree and are ALL committed together
    at the END of STEP 4 — and only when the human says so. (This is the opposite of STEP 3,
    whose review-fix commits are fine; the difference is that STEP 4 is interactive with the
    human, who is still reviewing.)
  - If approved: proceed to STEP 5
  - If minor issues: fix them (accumulate uncommitted, per the rule above); re-surface for the
    human
  - If major/structural issues: return to STEP 1

STEP 5 — UPDATE SPEC TRACKER
</workflow>

## Self review rules

There are ONLY 2 layers of self review: the chunk-level self review (STEP 2b) and the
phase-level self review (STEP 3). Use reviewer subagents for both.

**Contrary to `/superpowers:subagent-driven-development`, do NOT review each task in the
chunk.** One reviewer per chunk, after its tasks land.

## Commit rules

- **Do not `git commit`**, even when working with worktrees. The user reviews changes by git
  diffs, not by commit history. You may commit **ONLY** on the user's explicit instruction.
- A user describing a commit as an upcoming step is **not** an instruction to commit.
- **Authorization is single-use.** When the user authorizes a commit, that permission covers
  **that one commit only** — it never carries forward. It does not become a standing
  arrangement, it does not cover the next commit in the same task, and it does not survive into
  later work in the session. Every subsequent commit needs its own explicit go-ahead.
  Only the user can widen this, and only by saying so explicitly (e.g. "commit as you go from
  now on"); never infer a standing permission from a previous yes, from a pattern of yeses, or
  from the work obviously continuing.
- Do **NOT** add a `Co-Authored-By` line to commit messages.
- Within the workflow: no commits during STEP 2; STEP 3 review-fix commits are fine; STEP 4
  fixes accumulate uncommitted until the human says so.
- **The STEP 3 commits are the one standing exception**, and they are authorized by this
  workflow itself — by the user having adopted it — not by anything said in the conversation.
  That exception is confined to STEP 3: it does not license a commit at any other step, and it
  is not evidence that commits elsewhere are welcome.

## Per-agent test databases (create AND drop)

**Applies ONLY when doing parallelized development with subagents.**

Where the test suite derives its database from a single setting (e.g. `conftest.py` building
`f"{settings.DB_NAME}_test"`) and the schema fixture is **session-scoped** (`create_all` /
`drop_all`), two pytest sessions sharing one `DB_NAME` tear down each other's schema mid-run.
So every agent that runs pytest gets its **own** `DB_NAME`.

Nothing in the code creates or drops a database. Both halves are manual, and **both belong in
the plan**. For PostgreSQL:

```bash
# Setup — first task of the chunk
createdb <agent> && createdb <agent>_test
DB_NAME=<agent> uv run alembic upgrade head    # migrates <agent>, not <agent>_test

# ... the chunk's work ...

# Teardown — last task of the chunk, after the final gate passes
dropdb --if-exists <agent> && dropdb --if-exists <agent>_test
```

On MySQL the same discipline applies with `CREATE DATABASE` / `DROP DATABASE` in place of
`createdb` / `dropdb`.

- **The teardown line is not optional and is not implied.** `drop_all` empties the *tables*;
  the *database* survives every run. Skipping it for one chunk costs nothing and is invisible —
  which is exactly how 82 stray databases (~1 GB) accumulated before anyone noticed.
- **Drop only after the chunk's last gate is green.** The DB is the evidence for
  `N passed / 0 skipped`; don't destroy it before the number is reported.
- **Never force.** Plain `dropdb`. A refusal means something is still connected — leave that
  one and say so in the chunk report rather than terminating another agent's session.
- **Assert `0 skipped`, always.** A missing `<agent>_test` makes the schema fixture call
  `pytest.skip`, so the suite is skipped, not failed, and still **exits 0**. An agent can
  report "all green" having tested nothing.
- **⛔ Never run migrations against the shared dev database** — a chunk's migration is still a
  draft and may be rewritten in review, which would strand the dev DB at a revision no file
  describes.

**The corollary, at STEP 5:** because chunks never touch the main DB, it drifts behind head.
Bring it current once the phase is approved and its migrations are final:

```bash
uv run alembic upgrade head
```
