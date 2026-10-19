---
name: release-notes
description: Use when asked to write the client release notes / "what's new" email (noutățile versiunii) for <App>, for the changes about to be deployed or just deployed.
---

<!--
Template for an app's local release-notes skill. Copy it to <repo>/.claude/skills/release-notes/SKILL.md,
replace every <placeholder>, and delete what does not apply and this comment.
It supplies facts only; the process lives in client-comms:release-notes. Keep it that way, so a fix to the
process reaches every app.
-->

# <App> release notes

**REQUIRED:** invoke the `client-comms:release-notes` skill and follow it. It owns the whole process. This file
supplies only the facts about <App> that it asks for.

## Identity

- App name: **<App>**. Folder slug: `<app_slug>`.
- Output root: `release_notes/` in the repository (gitignored).
- Greeting: `Bună ziua,`. Sign-off: `Cu stimă,\n<Echipa …>` (or leave `[Semnătura]` for the sender).

## Range

- Branch `main`, remote `origin`, release-tag prefix `release-notes/`. The range is
  `refs/tags/release-notes/<latest>..refs/heads/main`, and each approved email is tagged on its last commit.
- <Anything unusual, such as a release branch or a known stray ref.>

## Theme

Colours come from `<path/to/theme file>`:

| content.json `theme` key | Token in that file | Value |
|---|---|---|
| `primary` | `<e.g. colors.primary>` | `<#hex>` |
| `on_primary` | `<e.g. colors.on-primary>` | `<#hex>` |
| `on_primary_muted` | <a light tint of primary, legible on it> | `<#hex>` |
| `where_bg` | <a very light tint of primary> | `<#hex>` |

Leave the other keys at their defaults unless the theme defines an equivalent.

## Where the truth is

- **User help docs:** `<docs/help/*.md>`. Take menu paths, button labels and chapter names from here.
- **Manual:** <how a user downloads it, e.g. the „Descarcă manualul de utilizare” button on the „Ajutor" pages>.
  Its chapters are <how to list them, e.g. the help docs' titles>. <Or: "No manual.">
- **Data-changing upgrade code:** `<e.g. backend/alembic/versions/>`. Read the data migrations in the range to
  state exactly what the upgrade removed or changed.
- **Other places worth checking:** <e.g. the date-range service for limits, the settings defaults file>.

## Vocabulary

| Use | Never | Note |
|---|---|---|
| <o activitate „se desfășoară”> | <„este deschisă”> | <why, if it is not obvious> |
| <rezervare> | <booking, programare> | |
| <client> | <user, utilizator> (for end customers) | |

<Domain nouns and how the client names them; anything the client is sensitive about.>

## Optional modules

<Which modules exist (e.g. from `docs/help/modules.json`) and which ones this client has. Content for a
module the client does not have stays out of the email. Or: "None.">

## Screenshots

- **Existing store:** `<docs/screenshots/>`, with the index of what each image shows in
  `<docs/screenshots/README.md>`.
- **Capturing a new one:** `<command, e.g. cd docs/screenshots && node capture.mjs <id>>`, against a demo
  instance only.
- **Demo instance:** <how to build, seed and tear down a throwaway instance with invented data; or point to
  the help-docs skill's procedure>. **Never dev or production data.**
- For a capture used only in the email, <how to aim the harness at one specific screen state>, and save it in
  the release folder's `src/`, not the docs store.
