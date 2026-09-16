---
name: help-docs
description: Use when adding, updating or reviewing the user-facing help documentation ("save this to the docs", "add a help doc", "update the help docs", "document this for users").
---

# User-facing help documentation

`docs/help/*.md` is the **source of truth** for the documentation shown to users inside the
application (the Help button in the app bar and the `/help` page). The files are kept in git and
edited by developers.

## Where everything lives

| What | Where | Edited by hand? |
|---|---|---|
| The documents (source) | `docs/help/*.md` | **YES** — this is where you work |
| Developer notes | `docs/help/_*.md` (`_` prefix) | yes; the generator ignores them |
| Generated output | `<srcDir>/help/generated/` | **NO, never** (not in git either) |
| The generator | `<nuxtDir>/scripts/generate-help.mjs` | only when changing the mechanism |
| Automatic run | `<nuxtDir>/modules/help-docs.js` | only when changing the mechanism |
| The UI | `<srcDir>/pages/help.vue`, `<srcDir>/pages/help/[[slug]].vue`, `<srcDir>/components/help/` | only for UI changes |

## Procedure

1. Create or edit the file in `docs/help/`. For every screen or dialog described, add a
   screenshot too; if one does not exist yet, **produce it** — see [Screenshots](#screenshots).
2. Run the check:
   ```bash
   cd <nuxtDir> && npm run help:generate
   ```
3. If it reports an error, **fix it** — do not commit a broken document. The message names the
   exact file and cause (missing title, broken link, non-existent section, invalid file name).
4. Commit only the file in `docs/help/` (and any new screenshot). The generated output lives in
   `<srcDir>/help/generated/` and is **not** kept in git — it is produced on every build.

Generation runs automatically before `npm run dev` and `npm run build`, and on every save of a
document while the dev server is running. An invalid document **stops the build** (in
development it only warns, so a running server does not die).

## File name

The name becomes the document's address: `bookings.md` → `/help/bookings`. Only lowercase
letters without diacritics, digits and `-`; otherwise the generator stops with an error and
suggests the correct name.

## Frontmatter

```markdown
---
title: Bookings
order: 20
group: Daily operations
summary: How to find, create and change a booking.
routes:
  - /calendar
  - /bookings
---
```

| Field | Required | What it does |
|---|---|---|
| `title` | **yes** | The title in the help menu and in the dialog header. |
| `order` | no | Position in the menu, ascending (default 999). |
| `group` | no | The menu section the document appears in. |
| `summary` | no | One sentence shown under the title in the list. |
| `routes` | no | The pages this document is the **contextual help** for. |
| `tabs` | no | Per-tab contextual help for the pages in `routes` (see below). |

### `routes` — contextual help

The Help button in the app bar opens the document whose declared route matches the current page.
The most specific match wins, and a route also covers its sub-pages: `/clients` covers
`/clients/staff`, while `/reports/daily` takes precedence over `/reports` for the daily report
page. If no route matches, the dialog shows the list of topics instead.

Use the real paths from the application (`<srcDir>/pages/`), without parameters: `/client` also
covers `/client/12`.

`/` is the root page only — it does **not** act as a catch-all for every page, because a route
covers its sub-pages through the `/` separator (`/` plus `/` is `//`, which matches nothing). A
page with no matching document gets the topic list, which is the intended fallback.

### `tabs` — contextual help per tab

On a page with tabs, the Help button opens the help of the **active tab**, not the top of the
document. The active tab is in the address (`?activeTab=`), so the mapping is declared once
here:

```markdown
---
title: Clients
routes:
  - /client
tabs:
  profile: "#profile"
  services: "client-services.md"
  documents: "client-documents.md#consent"
---
```

The key is the tab's value from the address, and the target is written like any other help link:
`#section` for a section of this document, `other.md` for another document, `other.md#section`
for a section of it. **The target is verified at generation**, exactly like a link — a renamed
heading stops the build instead of quietly opening the document unscrolled.

## Links

The generator rewrites links and accepts only the forms below; any other form stops generation,
so that no dead link reaches users.

| You write | It goes to |
|---|---|
| `[Contracts](contracts.md)` | another help document |
| `[Renewal](contracts.md#renewal)` | a section of another document |
| `[See below](#filters)` | a section of the current document |
| `[The client list](app:/clients)` | a page of the application |
| `[Tax office](https://example.gov)` | an external address (opens in a new tab) |

A section's id is derived from its heading, without diacritics and with `-` instead of spaces:
`## Advanced filters` → `#advanced-filters`. Two identical headings in the same document get the
suffixes `-2`, `-3`.

**The target of an anchor is verified**, not just the link's form: a section that does not exist
stops generation, and the message lists the sections available in the target document. This way,
renaming a heading leaves no dead links behind.

A link to a section is written as `?s=<id>` in the generated HTML, not as a real `#anchor` —
the same document is also rendered inside the help dialog, where the browser has no anchor to
jump to. You never write that form yourself; the generator produces it.

## What the Markdown supports

Headings, lists, **bold**, _italic_, tables, quotes, horizontal rules, `code`. Raw HTML is
**disabled** — if you write a tag, it shows up as text. Bare addresses automatically become
links.

Use the level-1 heading only for the document title; the rest of the structure starts at `##`.

## What a document must cover

A document describing a screen with a form **covers every field of that form**, including
toggles, file pickers and action buttons, and **shows the screen in a screenshot**. An
undocumented field is a gap to fix, not a deliberate omission: whoever cannot find the field in
the help assumes it does not matter.

When the full explanation of a field belongs to another topic, split it:

- the form's document **names the field** where it is filled in, says in a single sentence what
  it sets, and links to the document that explains it at length;
- the topic document holds the complete rule, with its effects and exceptions;
- if a general setting takes part in the same rule, link to the same place from the settings
  document too.

When a form gains a new field, find the document describing that screen and complete it in the
same commit — see **When the application changes**.

## Style

- Write in the second person ("press", "choose"), for the application's operators.
- Describe what the user sees on screen, with the exact names of buttons and fields.
- Avoid technical jargon and implementation details — those belong in the code and in specs.
- **Do not document behaviour you have not verified in the application.** Read the page's code
  or open the application; if you cannot verify, ask rather than assume.

## When the application changes

If you change a user-visible behaviour, check whether a help document describes it and **draw
the user's attention** to the fact that it must be updated, proposing the change in the same
commit. Wrong documentation does more harm than missing documentation.

## Screenshots

### The rule: a screenshot whenever possible

A document that describes a screen, a list, a dialog or a form **includes a screenshot of it**,
placed where the text explains it. Only topics that have no screen of their own stay text-only
(a business rule, an email the user receives, a setting explained in another document).

Screenshots live in `docs/screenshots/`, shared by every document: a screenshot is taken once
and reused, never retaken because a second document needs it. When the interface changes, retake
the affected screenshots in the same commit as the document — an outdated screenshot misleads
just as a wrong text does.

### How to write it

A screenshot is written as a Markdown image, **alone in its paragraph**, with a relative path:

```markdown
![The client list, with the table's filters and columns](../screenshots/clients-list.png "The client list")
```

- the text between the square brackets is **required**: it says what the image shows and is what
  a reader who cannot see it gets;
- the title between quotes is optional and becomes the caption under the image;
- accepted extensions: png, jpg, jpeg, webp, gif, svg; an absolute path, an http address or a
  file outside the `docs/` folder stops generation, as does a missing file;
- file names must be unique across all of `docs/screenshots/` — the generator copies them into
  a single folder.

The generator checks every image as strictly as a link, copies it into the generated folder and
imports it into the bundle, so the final address (with hash and base URL) is given by Vite. In
the application the image appears framed, with the caption underneath, at the available width.
On GitHub and in editors the same relative path shows the image straight from the `.md`.

### Where screenshots come from

Take screenshots from a **demo or development instance whose data is invented** — never from
production, and never from a database that may hold real customer data. A screenshot is a
published document: whatever is on screen goes with it.

Capture at a consistent window size (1280×800 is a reasonable default) so the images look like a
set, and crop to the region the text is talking about rather than showing the whole desktop.
