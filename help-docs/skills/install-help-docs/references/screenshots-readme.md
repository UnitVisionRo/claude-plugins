<!-- Destination: <shotsDir>/README.md -->

# Documentation screenshots

This folder holds the screenshots the help documents embed, one PNG per screen. Each has an
**id**, used as its file name: `<id>.png`. A document references one with a relative path:

```markdown
![What the image shows](../screenshots/clients-list.png "Optional caption")
```

The folder is shared by every document: a screenshot is taken once and reused, never retaken
because a second document needs it. If other documentation (a printed manual, a README) also
shows the application, it embeds these same files.

## Taking them

Screenshots are taken by `capture.mjs` (Playwright, Chromium, <width>×<height>, scale 1) against
the **demo instance** — a separate installation with its own database, populated with invented
data. Never against the working development database, and never against production: whatever is
on screen is published with the documentation. How the demo instance is built and seeded is in
the "Screenshots" section of the app's help-docs authoring skill.

Install, once, in this folder:

```bash
npm install && npx playwright install chromium
```

Then, with the demo instance running:

```bash
node capture.mjs --only <id>,<id>   # a few
node capture.mjs                    # all of them
node capture.mjs --list             # just the ids
```

The header of `capture.mjs` documents the environment variables and the credentials file. Open
each resulting PNG and check it shows what the table below says before referencing it.

## Adding one

A new screenshot means **three** things, in the same commit:

1. a row in the table below — the id, where the screen lives, and what has to be visible in it;
2. a step in the `STEPS` list in `capture.mjs` that navigates there, opens what needs opening
   and calls `shot(page, id)`;
3. the `.md` document that embeds it, with alt text describing what the image shows.

When the interface changes, retake the affected screenshots in the same commit as the change —
an outdated screenshot misleads exactly as a wrong sentence does.

## The screenshots

The "what must be visible" column is the contract: it is what makes a screenshot reproducible
by someone who did not take it, and what you check the PNG against after capturing. Be specific
about state — which record, which filter, which dialog, and whether anything must *not* be saved.

| id | Page / route | What must be visible |
|---|---|---|
| `login` | `/login`, signed out | The sign-in screen. |
| `dashboard` | `/` | The dashboard with its cards and charts, populated with demo data. |
