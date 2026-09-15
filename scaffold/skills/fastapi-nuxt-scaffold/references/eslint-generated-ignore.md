`gui/eslint.config.mjs` does NOT exist right after `nuxi init` (even with `@nuxt/eslint`
installed) -- `@nuxt/eslint` only materializes it the first time Nuxt's dev/prepare step
runs with the module registered in `nuxt.config.ts`. So this edit must come AFTER copying
the reference `nuxt.config.ts` (which registers `@nuxt/eslint`) -- run `npx nuxt prepare`
once to generate the file, THEN edit it.

The generated file looks like:

```js
// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt(
  // Your custom configs here
)
```

Generated OpenAPI code under `app/generated/` isn't code you author, and it trips
`@nuxt/eslint`'s defaults (`no-explicit-any`, `ban-ts-comment`, etc.) if it isn't excluded.
Change the `withNuxt(...)` call to:

```js
// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt().append({
    ignores: ['app/generated/**'],
})
```

Note: `@nuxt/eslint-config` also auto-ignores whatever `gui/.gitignore` ignores (via
`eslint-config-flat-gitignore`), so once `references/gitignore.gui-additions` is applied
this may already be redundant in practice -- keep it anyway as an explicit, version-independent
guarantee that doesn't rely on that integration detail.
