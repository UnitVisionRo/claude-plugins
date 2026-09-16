import { defineConfig, presetAttributify, presetIcons, presetWind4 } from 'unocss'

export default defineConfig({
    presets: [
        // `reset: false` is load-bearing, not a preference. Wind4's preflight ships a global
        // CSS reset that is emitted UNLAYERED, and an unlayered rule beats any rule inside an
        // `@layer` no matter how specific -- so it silently wins against all of Vuetify's
        // styles, which live in `@layer vuetify-*`. The visible symptom is subtle: the app
        // renders and looks almost right, but `.v-main`'s `padding-top: var(--v-layout-top)`
        // is flattened to 0 and page content slides underneath the app bar.
        //
        // Vuetify already ships its own reset (via `vuetify/styles`), so nothing is lost --
        // this only stops two resets fighting, with the component framework winning. Uno's
        // utilities, attributify and icons are unaffected.
        presetWind4({ preflights: { reset: false } }),
        presetAttributify(),
        presetIcons(),
    ],
})
