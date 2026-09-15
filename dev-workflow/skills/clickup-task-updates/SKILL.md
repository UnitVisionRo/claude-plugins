---
name: clickup-task-updates
description: Use when writing to a ClickUp (or any issue-tracker) task during development — creating the task, recording new requirements that come up mid-work, or reporting what was implemented. Covers when to write (after the commit, not on every interaction) and where to write it (requirements in the description, implementation in comments).
---

# Tracker task updates: when, and where

## The rule

**Write to the tracker after the commit — not during the work.**

A development conversation is iterative: the user refines the ask, changes wording, rejects an
approach, asks for one more fix. None of that belongs in the tracker as it happens. Push a tracker
update once the work is committed, so the record reflects what actually shipped.

**Two destinations, two kinds of content:**

| Content | Goes in |
|---|---|
| Requirements — the original ask, plus any **additional requirements** that emerged during the work | the task **description** (append to it; keep it the current, complete statement of scope) |
| What was **implemented** — commits, files, behaviour delivered, validation run | a **comment** on the task |

The description answers "what was asked for". The comments answer "what was done, and when". Never
put implementation notes in the description, and never let a new requirement live only in a comment.

Never technical details in the tracker, audience is business-facing. Describe behaviour, not code, in both description and comments.
Do not mention branches used for development (everything eventually is merged into main so we don't need to track them) or commit intervals, only the individual commits SHAs.
For example, this is wrong: `Commit-uri (în ordine), interval main..user-groups-cleanup = 43305ef..ef05381`

Keep descriptions goal and business focused. They should be concise and describe the goal of the task and any requirements clearly.

## Workflow

1. **At the start** — create the task (ask which list if it isn't obvious), set its status and
   assignee, and write the requirements into the description.
2. **While working** — write nothing to the tracker. Requirements that come up mid-work are noted in
   the conversation; they get folded into the description at the next tracker write.
3. **After committing** — one tracker write:
   - append/refresh the description if scope grew or changed;
   - post a comment describing what was implemented, with the commits;
   - move the status if the phase is finished.
4. **Repeat per commit / per phase**, not per exchange.

## What the implementation comment contains

- **Every commit of the work, in commit order**, each with a one-line functional description. Never cite only the last commit — the reader can't otherwise tell a
  one-commit change from an eight-commit one. Get them with
  `git log --reverse --format="%h %s" <base>..<head>`, and re-read them at reporting time (a rebase
  rewrites SHAs, so SHAs quoted earlier in the conversation may be stale).
- What behaviour changed, in the same business-facing language the commit messages use.
- Don't say the commit was delivered (Livrat). THe reader might think it was delivered to production, which is not the case.

## ClickUp MCP gotchas

Apparently you can send Markdown to ClickUp, try this first.

These are real failure modes that silently destroy the record — check for them every time.

- **A WAF sits in front of the API and blocks some payloads.** Descriptions containing angle-bracket
  placeholders (`<id>`, `<cod>`) or SQL-looking fragments (`LIKE '%1%'`) are rejected with a
  Cloudflare "you have been blocked" HTML page, not a useful error. Write placeholders without angle
  brackets and describe query behaviour in prose. If a write is blocked, shorten to a minimal
  payload to confirm connectivity, then reintroduce content until the offending fragment shows
  itself — and remember a successful short "test" write **overwrote the description**, so restore it.
- Descriptions are replaced wholesale by an update, so build the new full text rather than assuming
  an append.

## Which list

Route the task by kind — a project's own instructions (CLAUDE.md / AGENTS.md) usually name the
lists:

- implementation / planned development work → the implementation list
- bug fixes and support → the support list
- client-requested features and changes to existing behaviour → the change-request list

If a change doesn't clearly belong to the task you're already updating, say so and ask rather than
folding it in silently.
