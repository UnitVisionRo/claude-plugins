---
name: "spec-driven-development"
description: "The phase → chunk → review workflow for planning and implementing functional specs. Use when brainstorming a functional spec or building a feature from a spec, splitting a phase into chunks, planning or reviewing an implementation phase, or deciding when to commit. Defines where specs and plans live, how code references them, the design principles for extracting vs. reusing code, and the commit and review rules that override the superpowers defaults."
---

# Spec-driven development

The workflow for designing and implementing functional specs: a feature is designed into a
spec, each phase of the spec is split into chunks, each chunk is implemented and reviewed, and
the phase is reviewed as a whole before a human sees it. The human reviews at the checkpoints
chosen once the spec is split into phases.

## ⚠️ Precedence over the `superpowers` plugin

This workflow **uses** several superpowers skills, and **overrides** them where they disagree.
When `superpowers` is loaded, the rules below win. Where they are silent, follow superpowers.

| Topic | superpowers says | **This workflow says (wins)** |
|---|---|---|
| Review granularity | `subagent-driven-development`: launch a reviewer subagent per **task** | Review **per chunk**, never per task. There are exactly **two** review layers — see Self review rules. |
| Committing during work | Several skills commit as they go (`brainstorming` commits the design doc; `executing-plans` and `finishing-a-development-branch` commit progress) | **Never commit** except where this workflow explicitly allows it, and never without the user's instruction — see Commit rules. |
| Design docs | `brainstorming`: write to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and commit it | Specs live where **the project's `CLAUDE.md`** says (see Spec and plan file locations) and are **not** committed on the skill's own initiative. |
| Finishing a branch | `finishing-a-development-branch` decides how to integrate | The phase ends at **STEP 5**; integration is the user's call. |
| Design questions | `brainstorming`: one question per message | Ask in **rounds** through `AskUserQuestion`, each as full as the tool allows — see Designing the spec. |
| Design gates | `brainstorming` HARD-GATE: after the written spec, the human also reviews the implementation plan and chooses an execution method | The human gates end at the **written-spec review** — see Designing the spec. No plan review, no execution-method question; the only question before the work starts is the review cadence, and the next human gate is STEP 4 at the first checkpoint. |
| After the spec | `brainstorming`: invoke `writing-plans` next | Split the spec into phases and start **The workflow** at STEP 0. |
| When to plan | `writing-plans`: before touching code on any multi-step task | A chunk gets a plan **only** when STEP 1 says so; every other chunk goes straight to STEP 2. |
| Plan detail | `writing-plans` "No Placeholders": every code step carries the complete code | Plans are **design-level** — see STEP 1. Code appears only where prose cannot pin the result. |
| Plan handoff | `writing-plans`: ask the human to review the plan and choose an execution method | Neither. Execution is STEP 2. |
| Model choice | `subagent-driven-development` and others: escalate to the most capable model for hard tasks, later fix rounds and final reviews | **Opus is the ceiling** for every model chosen automatically, in this workflow and in the skills it invokes. Fable runs only when the user asks for it. |

Skills this workflow invokes, with the overrides above: `/superpowers:brainstorming` (Designing
the spec), `/superpowers:writing-plans` (STEP 1, only for chunks that need a plan) and
`/superpowers:subagent-driven-development` (STEP 2a for planned chunks, minus its per-task
review).

## Spec and plan file locations

**The parent directory varies by project — the project's `CLAUDE.md` names it, and it wins.**
Check there before creating a spec or a plan; several projects use `specs/` at the repo root
rather than `docs/spec/`, and some keep plans in a sibling tree instead of under the spec.
Never create a new spec directory on the strength of this skill alone.

When the project says nothing, use this shape:

- **Functional spec**: `docs/spec/<YY-MM-DD>-<feature_name>/` — the source of truth for the
  platform's behavior. If the feature needs only a single file, name it
  `<YY-MM-DD>-<feature_name>.md`.
- **Plans**: `docs/spec/<YY-MM-DD>-<feature_name>/plans/` — derived from the spec: one short
  overview per phase (STEP 0) and, for a chunk that needs one, a design-level chunk plan
  (STEP 1). Plans translate the spec into work — which chunks, in what order, against which
  interfaces — and carry design, not code. Each chunk has its own independently testable
  deliverable.

The `<YY-MM-DD>-<feature_name>` naming applies wherever the parent lives. Whether plans are
committed is also per-project — some treat them as ephemeral and never commit them.

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

## Designing the spec

Design a feature with `/superpowers:brainstorming`, under the overrides in the precedence table.
Its classification decides what follows:

- **Architectural** — ends in a written functional spec, then continues with The workflow
  below.
- **Bounded** or **spike** — no spec and no phases. Brainstorming's own path applies, and so do
  this skill's Commit rules.

Questions go to the human through the `AskUserQuestion` tool, in rounds. A round is one call,
filled with as many of the questions that can already be asked as the tool accepts in a single
call. When more questions are ready than one call holds, ask them in successive rounds. Each
question lists your recommended option first, labeled "(Recommended)". A question whose wording
depends on an answer still pending waits for a later round.

Besides the question rounds, the architectural path has exactly two approval gates:

1. approval of each design section during the dialogue;
2. review of the written spec.

Once the spec is approved, split it into phases (unless the spec already defines them), ask
the review cadence (see Human review cadence) and start the first phase at STEP 0. The human
sees the work next at STEP 4 of the first checkpoint.

## Human review cadence

The human chooses when STEP 4 happens. The choice moves STEP 4 and STEP 5 and nothing else:
every phase still gets its STEP 0 overview, its chunk loop, its STEP 3 review, its test run
and its STEP 3 commit.

- **More than one phase:** right after the phase split, ask one `AskUserQuestion` question
  listing the phases and offering these options, your recommendation first and labeled
  "(Recommended)":
  1. **Review each phase** — STEP 4 after every phase.
  2. **Review at checkpoints** — STEP 4 after named groups of phases. The option names the
     groups, e.g. "Review 1 after phases 1–4, review 2 after phases 5–7".
  3. **Review once at the end** — STEP 4 only after the last phase.
- **One phase:** don't ask; STEP 4 follows that phase.

Base the recommendation on the complexity of the implementation:

| Phases | Recommend |
|---|---|
| Each phase settles something the later ones build on that is costly to undo (data model, migrations, core interfaces), or carries UX or business decisions the human must see | Review each phase |
| Such a foundation exists only in some phases | Checkpoints, each closing right after a foundational phase or a coherent user-visible slice |
| Few, small or mechanical phases following existing patterns | Review once at the end |

State the reason for the recommendation in the question.

Write the schedule at the top of every phase overview (STEP 0), with whether that phase closes
a checkpoint. A phase that closes no checkpoint goes from STEP 3 straight to the next phase's
STEP 0. At a checkpoint, STEP 4 covers every phase since the previous checkpoint, and STEP 5
then runs for each of them.

The schedule decides only when the human reviews. A question that comes up mid-phase — from a
subagent, or a gap in the spec — goes to the human when it arises. If the human asks to change
the schedule, the new one applies from the next phase.

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
STEP 0 — PHASE OVERVIEW (once per phase)
  Write `plans/phase-<N>-overview.md`. It is design only, no code, and holds:
  - the chunks, each with its deliverable and the spec sections it implements;
  - the dependency DAG and the batches it allows;
  - the interfaces between chunks: schemas, endpoints, types, shared files;
  - the constraints every chunk shares: project rules, per-agent database names.
  Every chunk agent receives the spec and this overview.

<for-each-chunk>
STEP 1 — PLAN (only for a chunk that needs one)
  - A chunk needs a plan when it shares an interface with another chunk in the same batch —
    one of them produces a schema, an endpoint, a type or a shared file that the other uses.
    Both chunks get a plan. Any other chunk has no plan and goes straight to STEP 2.
  - Use a subagent to write the plan with the /superpowers:writing-plans skill, to
    `plans/phase-<N>-chunk-<M>-<slug>.md`. Planner subagents don't load this skill, so their
    prompt says: the plan is design-level as described here, it has no commit steps, and it
    ends with the plan's path instead of writing-plans' execution handoff. Below the header
    writing-plans requires, a design-level plan holds:
    1. the file map: each file created or modified, with its responsibility;
    2. the interfaces: exact names, signatures and types the chunk consumes and produces;
    3. the decisions the spec leaves open: which existing code to reuse, the shape of a
       migration, where new code lives;
    4. the tasks, each with its tests written as "input → expected behavior";
    5. Review Focus and known traps.
    Code appears only where prose cannot pin the result: a migration, a non-obvious query, a
    signature. A chunk plan runs to a few hundred lines.
  - Subagent model selection: since planning is the most important part of the workflow, you
    must use opus for planning.

STEP 2 — IMPLEMENTATION LOOP
  2a. Implement the chunk:
      - **Chunk without a plan:** one opus implementer subagent implements the whole chunk
        from the spec and the phase overview, running the tests as it goes.
      - **Chunk with a plan:** implement the plan with /superpowers:subagent-driven-development.
        Model selection is decided by the skill. Do NOT launch a review subagent for each task
        in this step, contrary to what the skill says. **Reviews** are done **per chunk**.
      Implementer subagents don't load this skill, so paste the Design principles section
      into every implementer's prompt.
      Every implementer's prompt names the test files that cover its work: implementers run
      those, never the full suites (`dev-workflow:automated-tests`).
  2b. Self review the chunk with a reviewer subagent other than its implementer.
  2c. If review found issues: fix them, then return to STEP 2a
      If review is clean: proceed to next chunk

  Do not commit during this step. Instruct the subagent to accumulate all changes in the
  working tree.
</for-each-chunk>

STEP 3 — SUBAGENT REVIEW LOOP
  3.a Use a subagent (model: opus) to perform a review of the whole phase implementation. If all good, run the
      tests covering the phase's changes: every test file its chunks named, in one targeted run
      (`dev-workflow:automated-tests`). The full suites never run here, not even in the last phase. Then
      commit the phase and proceed to STEP 4 if this phase closes a review checkpoint, or to the next
      phase's STEP 0 if it does not (see Human review cadence); otherwise go to 3.b
  3.b If review found issues, fix them with subagents. Choose suitable models for each fix:
      simple fixes -> fast / cheap model, complex fix -> capable / more expensive models.
      After fixes, proceed to 3.a, re-review. Don't ask for a re-review of what was already
      reviewed and not impacted by the fixes.

STEP 4 — HUMAN REVIEW (at a checkpoint: human evaluates every phase since the previous one)
  - DO NOT commit per fix during the human review. Fixes made in response to the human's
    review comments accumulate UNCOMMITTED in the working tree and are ALL committed together
    at the END of STEP 4 — and only when the human says so. (This is the opposite of STEP 3,
    whose review-fix commits are fine; the difference is that STEP 4 is interactive with the
    human, who is still reviewing.)
  - Before that commit, run the tests covering the fixes.
  - **Full suites:** the one full run of the implementation (`FULL_SUITE=1`) happens when the human
    approves the final checkpoint, before its fixes are committed. If it fails, fix, re-run and
    re-surface for the human.
  - If approved: proceed to STEP 5
  - If minor issues: fix them (accumulate uncommitted, per the rule above); re-surface for the
    human
  - If major/structural issues: return to STEP 0 of the earliest affected phase

STEP 5 — UPDATE SPEC TRACKER
</workflow>

## Self review rules

There are ONLY 2 layers of self review: the chunk-level self review (STEP 2b) and the
phase-level self review (STEP 3). Use reviewer subagents for both.

**Contrary to `/superpowers:subagent-driven-development`, do NOT review each task in the
chunk.** One reviewer per chunk, after its tasks land.

Both review layers check the code against the Design principles below — include that section
in every reviewer's prompt, and treat a violation as a review finding like any other.

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
the chunk's instructions** — its plan, or the implementer's prompt when the chunk has no plan.
For PostgreSQL:

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
- **If a subagent can't create or drop databases** (permission denied), the orchestrator does
  both on its behalf: create before dispatching the chunk, drop after its final gate reports
  green. The rules above still apply — drop only after `0 skipped` is reported, never force.

**The corollary, at STEP 5:** because chunks never touch the main DB, it drifts behind head.
Bring it current once the phase is approved and its migrations are final:

```bash
uv run alembic upgrade head
```

## Design principles

Implementers follow these; both review layers check them (see Self review rules).

Follow DRY and SOLID in general. The two subsections below are how they apply in practice, and
they settle any conflict:

- **DRY** is *Reuse before duplication*.
- **SOLID** shapes code that has real callers and real variation; it is not a reason to add
  layers ahead of need. An interface with one implementation, or an extension point nothing
  extends yet, is the premature abstraction ruled out below — meet Open/Closed and Dependency
  Inversion by refactoring when the second implementation arrives. Single Responsibility
  may split a long function into smaller ones for readability — but those pieces stay local
  and private (see below).

### No premature abstraction — private until a second caller

- Indirection has a cost. Code with only one caller never goes in the shared service or
  utility layer (services, core helpers, composables, utilities).
- Splitting a long function to make it easier to read is fine. The pieces stay **local and
  private** next to their caller — in the same module, not exported (e.g. a leading `_` in
  Python) — until a second caller exists.
- Don't make anything public or shared "in case it's needed later". When a second caller
  arrives, that is the moment to promote the private helper to a public utility — a cheap,
  local refactor.

### Reuse before duplication

- Before writing behavior that may already exist, check the project's service layer and core
  helpers (e.g. `back/services/`, `back/core/`) and the frontend composables/utilities.
- Never duplicate functionality. If shared code nearly fits, extend or generalize it
  backward-compatibly, preserving existing callers' behavior. If the logic you need lives
  inline or in a private helper of one caller, promote it to the shared layer now (see above)
  rather than copying it.
- If adapting shared code safely isn't feasible, surface the trade-off instead of cloning the
  logic.
