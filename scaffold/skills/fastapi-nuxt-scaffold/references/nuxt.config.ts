import vuetify, { transformAssetUrls } from 'vite-plugin-vuetify'

// Verified Nuxt+Vuetify SSR wiring (Vuetify's own Nuxt+SSR install guide) plus the
// scaffold's other modules. Vuetify isn't a Nuxt module itself -- it's wired in via a
// Vite plugin registered through the inline-module hook below.
export default defineNuxtConfig({
    compatibilityDate: '2025-01-01',
    modules: ['@pinia/nuxt', '@unocss/nuxt', '@nuxt/eslint',
        (_options, nuxt) => {
            nuxt.hooks.hook('vite:extendConfig', (config) => {
                // @ts-expect-error -- config.plugins is typed loosely by Nuxt's Vite integration
                config.plugins.push(vuetify({ autoImport: true }))
            })
        },
    ],
    build: {
        transpile: ['vuetify'],
    },
    runtimeConfig: {
        public: {
            // Where the generated client sends requests. Overridable at runtime with
            // NUXT_PUBLIC_API_BASE_URL, so one build can serve several environments.
            // Note this URL is used by the browser AND by Nuxt's own server during SSR; if a
            // deployment puts the API on a different internal address, split it in two.
            apiBaseUrl: 'http://localhost:8000/rest',
        },
    },
    vite: {
        vue: {
            template: {
                transformAssetUrls,
            },
        },
    },
})
