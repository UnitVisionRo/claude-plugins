# `content.json` — what `build_email.py` reads

Every text field accepts one inline markup: `**bold**`. Nothing else. Raw HTML is rejected, because it would
leak into the plain-text part, and the builder escapes `&`, `<` and `>` itself. Arrows (`→`) and Romanian
quotes (`„…”`) are written literally.

```json
{
  "app_name": "PoolFlow",
  "subject": "PoolFlow — noutățile versiunii din 18 octombrie 2026",
  "subtitle": "Noutățile versiunii din 18 octombrie 2026",
  "theme": { "primary": "#1a3fd6", "on_primary": "#ffffff", "on_primary_muted": "#dbe4ff" },

  "greeting": "Bună ziua,",
  "intro": [
    "Vă prezentăm noutățile din noua versiune PoolFlow. Cele mai importante privesc **programul activităților** …",
    "Detaliile complete se găsesc în manualul de utilizare și în paginile de ajutor din aplicație."
  ],

  "notice": [
    "**Închirierile se rezervă doar fără trainer.** La actualizare au fost eliminate … Clienții nu au primit nicio notificare."
  ],

  "features": [
    {
      "title": "Program pe calendar pentru activități",
      "blocks": [
        { "p": "O activitate poate avea acum propriul calendar. De exemplu, Aquagym se poate desfășura doar marțea și joia …" },
        { "where": "Meniul **Activități** → deschideți activitatea → **Program pe calendar** → **Editează calendarul**." },
        { "image": { "src": "../../docs/screenshots/activitate-form.png",
                     "alt": "Fereastra unei activități, cu opțiunile Program fix / Program pe calendar",
                     "caption": "Fereastra activității: alegeți „Program pe calendar”, apoi „Editează calendarul”." } },
        { "h": "Adăugarea unei perioade: zile și ore alese" },
        { "p": "…" },
        { "where": "În calendarul activității → butonul **Adaugă o perioadă**, din dreapta sus." },
        { "image": { "src": "src/activitate-perioada.png", "name": "activitate-perioada.png", "alt": "…", "caption": "…" } }
      ]
    },
    {
      "title": "Disponibilitatea trainerilor pe calendar",
      "blocks": [
        { "p": "Se face la fel ca la activități: …" },
        { "where": "Meniul **Traineri** → …" }
      ]
    }
  ],

  "improvements": [
    "**Setare nouă: „max_date_range_days”** (în **Setări → Alte setări**, implicit 92 de zile). … De exemplu, …"
  ],
  "fixes": [
    "O rezervare care folosește **ultima ședință a unui pachet** se poate muta din nou, fără mesajul „Pachetul nu a fost achitat integral sau a expirat.”."
  ],
  "documentation": [
    "Pentru detalii complete vă recomandăm manualul de utilizare …, în special capitolele: „Activități”, …"
  ],
  "closing": ["Pentru orice întrebare vă stăm la dispoziție."],
  "signoff": "Cu stimă,\n[Semnătura]"
}
```

| Field | Required | Notes |
|---|---|---|
| `app_name`, `subtitle` | yes | Header band. The `app_name`, lowercased and stripped to `[a-z0-9-]`, is also the `Content-ID` domain. |
| `subject` | yes | The email subject and the HTML `<title>`. A date in it (or in `subtitle`) must include the day: `18 octombrie 2026`, not `octombrie 2026`. |
| `theme` | `primary` yes | Overrides of the defaults below; `primary` must come from the app's theme. An unknown key is an error, which catches typos. |
| `greeting`, `intro[]` | yes | `intro` is a list of paragraphs. |
| `notice[]` | no | "De reținut" bullets. Omit or leave empty only when nothing changes daily work or data. |
| `features[]` | one of the three sections | `title` plus `blocks`, where each block is exactly one of `p`, `h` (sub-heading), `where` ("Unde găsiți:" box) or `image`. Every feature needs at least one `where`. |
| `improvements[]`, `fixes[]` | one of the three sections | Bullets. |
| `documentation[]`, `closing[]` | `documentation` yes | Paragraphs. |
| `signoff` | yes | A `\n` becomes a line break. A `[…]` placeholder only produces a warning. |
| `titles` | no | Overrides of the section headings: `notice`, `features`, `improvements`, `fixes`, `documentation`. |

**Images.** `src` is resolved relative to the folder holding `content.json`, which suits captures in `src/`.
Images in the app's docs store are reached from the default release folder as `../../docs/screenshots/<file>`.
The file is copied into `images/` as `name`, which defaults to the source's lowercased file name and must
match `[a-z0-9-]+.(png|jpg|jpeg)`. Using the same image twice embeds it once.

**Theme keys and defaults:**

| Key | Default | Where it shows |
|---|---|---|
| `primary` | `#1a3fd6` | header band, section headings, the "Unde găsiți:" label, sub-headings |
| `on_primary` | `#ffffff` | the app name on the band |
| `on_primary_muted` | `#dbe4ff` | the subtitle on the band |
| `text` | `#1f2937` | body text |
| `muted` | `#6b7280` | captions, the "Documentație" heading |
| `page_bg` / `card_bg` | `#f3f4f6` / `#ffffff` | around and behind the email |
| `where_bg` | `#eef2ff` | the "Unde găsiți:" box; a light tint of `primary` |
| `notice_bg` / `notice_border` / `notice_title` | `#fff7e6` / `#f59e0b` / `#92400e` | the "De reținut" box |
| `fixes` | `#b91c1c` | the "Probleme rezolvate" heading |
| `image_border` | `#d1d5db` | the frame around screenshots |
