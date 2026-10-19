---
name: release-notes
description: Use when an app's local release-notes skill hands off to it, or when asked to write a client-facing release-notes / "what's new" email (noutățile versiunii) for the changes shipped in a range of commits. Not for commit messages or developer changelogs.
---

# Client release notes

Turns the commits about to reach a client into a **Romanian, business-language email** for the client's
non-technical staff, built as an Outlook-ready `.eml` with embedded screenshots, plus `.html` and `.txt`.

The skill is generic. Everything app-specific — names, vocabulary, theme, where the help docs and screenshots
live, how to capture a new screenshot safely — comes from the **app's local skill** (contract below). This
SKILL.md is written in English; **the email is written in Romanian.**

## The app's local skill (hand-off contract)

The app's `.claude/skills/release-notes/SKILL.md` invokes `client-comms:release-notes` and supplies the
facts below. **Invoked directly, without that hand-off:** read `.claude/skills/release-notes/SKILL.md` in the
current repository first; it is where this app's facts are.

**No local skill yet:** create it with the user before Step 1. Start from `references/local-skill-template.md`
and establish as many facts as you can from the repository yourself: the theme file, `docs/help/`, the
migrations folder, the screenshot tooling, the vocabulary the help docs use. Present what you found, with the
file each fact came from, and ask only for what the repository cannot answer. The user confirms the file
before you write it.

Before Step 1, list the facts you have. **A missing required fact is a question to the user, never a guess**: a
guessed menu path or a guessed colour is exactly the kind of thing the client will notice.

| Fact | Required | Used for |
|---|---|---|
| App name, folder slug | yes | header band, subject, output folder, image `Content-ID` domain |
| Branch, remote, release-tag prefix | default `main` / `origin` / `release-notes/` | the range |
| Theme file and token → colour mapping | yes | `content.json` `theme` |
| User help docs path (e.g. `docs/help/*.md`) | yes | menu paths, labels, chapter names |
| Manual: how it is downloaded, chapter names | if the app has one | "Documentație", "re-download the manual" |
| Domain vocabulary: preferred / forbidden terms | yes | wording |
| Where data-changing upgrade code lives (migrations) | yes | "De reținut" facts |
| Screenshot store, capture command, demo-instance procedure | yes | images |
| Optional modules the client does or does not have | if any | leaving out what they cannot see |
| Output root | default `release_notes/` in the repository, gitignored | files |
| Greeting and sign-off | default `Bună ziua,` / placeholder | email |

## Step 1 — The range

The range runs from the commit the **previous email** covered up to the local branch:
`refs/tags/<prefix><previous date>..refs/heads/<branch>`. A release tag marks what an email covered. It lives in
git because the release folders are temporary and cannot be relied on.

```bash
git fetch <remote> --tags                                    # tags made on another machine
git tag --list '<prefix>*' --sort=-refname | head -1         # the latest release tag; date names sort
git merge-base --is-ancestor refs/tags/<tag> refs/heads/<branch> && echo ok
git log --format='%H %P%n%B%n----' refs/tags/<tag>..refs/heads/<branch>
```

- **Always fully qualified refs** (`refs/tags/…`, `refs/heads/…`, `refs/remotes/…`). A stray tag or branch with
  the same short name shadows the ref you meant, and the range silently grows (90 commits instead of 8, in one
  real case).
- **Pin the end:** note the `refs/heads/<branch>` sha now. That sha is what gets tagged in Step 6, even if the
  branch moves while you iterate. If it moves and the user wants the new commits included, extend the range
  explicitly.
- **Stop and ask for the range** when:
  - there is no release tag yet (the first email for this app). Offer `refs/remotes/<remote>/<branch>` as the
    start when it differs from the branch, and show the recent log;
  - the tag is not an ancestor of the branch (history was rewritten);
  - the range is empty, or its size is far from what the user expects.
  Show what you found.
- **Do not pass `--first-parent`.** Commits that arrived through a merge reached the client too. Use merge
  commits only as grouping hints; skip their messages when they add nothing.
- Everything in the range reaches the client, including work merged in from other branches.
- State the range (both shas), the commit count and each commit's short sha and first line to the user
  before writing.

## Step 2 — Decide what goes in, from evidence

Read every commit's **full** message. Commits written with `dev-workflow:git-commit-message` carry
business-facing `[New Feature] / [Improvement] / [Bug Fix] / [Performance Update] / [Security Update] /
[System Maintenance]` items with a body each, and those make a good first source. A message without that
structure, or one too vague to tell what changed for a user ("fixes", "wip", "update form"), is only a hint:
read the commit's diff (`git show <sha>`) to establish what it actually does. Either way, the message is
**not the last** source:

- **Verify each claim against the code before writing it.** Read the data migrations to state exactly what
  the upgrade deleted or changed. Read the code to settle any behaviour the email describes precisely:
  "does this apply to one record or the whole group?", "is this counted from today or from the period's
  first day?". These two questions were both answered wrong from commit text alone.
- **Drop** pure test, CI, tooling and refactoring items.
- **Fold** maintenance with a visible effect (a removed field, a removed limit) into one line, placed by
  impact: in "De reținut" when it changes someone's daily work or data, otherwise in Improvements. Never both.
- **`[Performance Update]`** that users will feel goes into Improvements, described by what they notice
  ("rapoartele se încarcă mai repede"). Give no number unless you measured it.
- **`[Security Update]`** and dependency bumps with no visible effect are dropped. If the user wants them
  mentioned, use one generic line in Improvements.
- **Net out** changes that cancel within the range: a feature added then reverted, a bug introduced and fixed
  in the same range. The client sees neither, so neither is mentioned.
- **Optional modules:** content for a module this client does not have is left out.

Sort what survives into the sections below. When something could go either way, ask.

## Step 3 — Write it

Write `content.json` (schema: `references/content-schema.md`) in the release folder. The email is, in order:

1. **Header band** in the app's colours: app name, subtitle `Noutățile versiunii din <luna> <anul>`, the
   month the release reaches the client.
2. **Intro:** greeting, then 2–3 sentences naming the release's main themes in business terms, pointing to the
   manual and the in-app help for details.
3. **"De reținut"** — first, so it cannot be missed. Everything that changes daily work or data: data the
   upgrade removed or changed, stated factually (including "clienții nu au primit nicio notificare" where
   that is true); rules that became stricter; removed fields or limits; what will now be refused on save;
   "vă rugăm să descărcați din nou manualul" when the manual changed. Each item opens with a bold sentence.
4. **"Funcționalități noi"** — one sub-section per feature: what it does, with a concrete example from the
   client's domain; an **"Unde găsiți:"** block with the exact menu path and button labels; screenshots
   with captions. When features share one UI, describe it in full once, then say "se face la fel" for the
   others, each with its own "Unde găsiți:". An improvement that changes the screen enough to need a
   screenshot becomes a sub-section here, because only features carry images.
5. **"Îmbunătățiri"** — bullets, each opening with a bold sentence. A setting gets its name, location,
   default, and a worked example showing exactly what it limits and what it does not.
6. **"Probleme rezolvate"** — bullets describing the **symptom** the user saw, quoting the old error message
   verbatim when there was one.
7. **"Documentație"** — manual chapters by name, and the in-app Help button. With no manual, only the
   Help button; the intro then points only to it too.
8. **Sign-off** from the local skill, or a `[placeholder]`.

Wording rules:

- **Past tense, already shipped:** "au fost eliminate", never "la actualizare se vor elimina".
- **Menu paths and labels come from the help docs and the UI, never from commit text.** Quote labels exactly
  as on screen, in „…”, or in **bold** for buttons and menus.
- Use the local skill's vocabulary; its forbidden terms are forbidden.
- Plain business prose, not a changelog: no commit ids, no technical names, no "we refactored".
- Romanian diacritics with comma below: **ș ț Ș Ț**, never cedilla ş ţ. The builder rejects cedillas.

## Step 4 — Screenshots

- **Reuse** the app's documentation screenshots when they show the new UI as described.
- When one is missing or shows the wrong thing, **capture it with the app's own capture tooling against a
  demo instance**, following the local skill's procedure. **Never against dev or production data**: real
  customer data in a client email is a data leak. Save these captures in the release folder's `src/`,
  not in the docs store. If the tooling can only write into the docs store, move the new file to `src/` and
  check with `git status` that the docs store is back as it was.
- **No safe instance available** (no demo procedure, or it fails): ask the user. Do not fall back to whatever
  server is running, and do not drop the image without saying so.
- **Open every image and look at it** before using it. A capture can be blank, show the wrong dialog, or
  contain something it should not.
- 4–6 images, for the significant GUI changes only. Each gets Romanian `alt` text and a caption saying what
  to look at.
- The builder copies them into `images/`, downscales anything wider than 1000px, and displays them at 600px.

## Step 5 — Build

The release folder is `<output root>/<YYYY-MM-DD>/`: by default `release_notes/<YYYY-MM-DD>/` inside the
repository, **gitignored**. Check with `git check-ignore -q release_notes/x`; if it is not ignored, add
`/release_notes/` to `.gitignore` and tell the user. The folder is temporary: nothing later depends on it. A
folder that already exists for the same range is the same email, so iterate in it. A different range on the same
day gets `<YYYY-MM-DD>-2`, and so does its tag. If clients with different module sets each need an email, use one
subfolder per client.

```
content.json   build_email.py   render_preview.sh
release-notes.eml   release-notes.html   release-notes.txt   images/   src/
```

Copy `scripts/build_email.py` and `scripts/render_preview.sh` from this skill's base directory into the
folder, so that later edits are "change `content.json`, rebuild", independent of the plugin version. Then:

```bash
uv run --with pillow python3 build_email.py content.json
bash render_preview.sh release-notes.html      # then open the PNG and look at the whole email
```

The builder fails loudly on invalid content: a cedilla, raw HTML, unbalanced `**`, a feature without an
"Unde găsiți:", an image that is missing or has no alt or caption, or a theme without `primary`. After
writing the files, it parses the `.eml` back and verifies the MIME structure and every `cid:`. **Fix the
content, not the check.** Its notes about the image count and a sign-off placeholder are warnings, not failures.

What it builds, and why, in case the email ever has to be built another way:

- `multipart/related; type="multipart/alternative"` at the root; its first part is `multipart/alternative`
  (text, then HTML), followed by the images. Each image has `Content-ID: <name@app>`, `Content-Location`
  and `Content-Disposition: inline`. **Python's `EmailMessage.add_related` nests `related` inside
  `alternative`, and Outlook classic then shows the images as attachments with "image not found" in the
  body.**
- Images are referenced by `cid:`, not `data:` URIs, which Gmail and Outlook web strip.
- `X-Unsent: 1`: Outlook opens the `.eml` as a ready-to-send draft.
- Inline CSS, table layout, 640px wide.
- The plain text is generated from `content.json`, not stripped from HTML, so no tags leak into it.

## Step 6 — Hand over and iterate

Report:

- the range and commit count;
- what you left out, and why (netted out, internal, a module the client does not have);
- every statement you verified in code that the commit text got wrong or left vague;
- the folder path, and the preview PNG for the user to look at.

Give the fallback for clients whose Outlook mangles the `.eml`: **open the `.html` in a browser, select all,
copy, paste into a new Outlook message.**

The user will correct things. Each correction is an edit to `content.json` and a rebuild, never a hand-edit
of the output files. When you rename or reword something, search `content.json` for other mentions of it, such
as the intro, "se face la fel ca la …" or "Documentație".

**Never send the email.** Create a mail draft in a connected mailbox only when asked.

**When the user approves the final email, tag the pinned end commit**, so the next email starts there:

```bash
git tag -a <prefix><YYYY-MM-DD> <end sha> -m "Client release notes <YYYY-MM-DD>: <start sha>..<end sha>, <n> commits"
```

The tag name is the release folder's name (`-2` included). Tag only on approval: a tag on a draft that is then
abandoned makes the next email skip those commits. The tag is local. **Ask before pushing it**
(`git push <remote> refs/tags/<tag>`), but recommend pushing: an unpushed tag exists only in this clone.

## Common mistakes

| Mistake | Instead |
|---|---|
| `git log origin/main..main`, or a range from a release folder | `refs/tags/<prefix><latest>..refs/heads/main` |
| Tagging before the user approves | Tag the pinned end sha on approval; ask before pushing |
| Trusting the commit message about exact behaviour | Read the code and the migrations |
| Menu path paraphrased from a commit | Copy it from the help docs / UI |
| "se vor elimina", "va fi posibil" | "au fost eliminate", "puteți" |
| Mentioning a feature reverted later in the range | Net it out |
| Screenshot captured on the dev database | Demo instance only, via the app's tooling |
| Image used without opening it | Look at every image |
| Hand-editing the `.html` or `.eml` | Edit `content.json`, rebuild |
| `EmailMessage.add_related` | The bundled builder (`email.mime`, related at the root) |
