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
    app: {
        head: {
            title: '__APP_NAME__',
            // The manifest + icons below are what make the app installable ("Install app" in
            // Chrome/Edge, "Add to Home Screen" on iOS). There is deliberately no service
            // worker, so there is no offline mode -- installed, the app is the same online-only
            // app in its own window.
            link: [
                // nuxi ships public/favicon.ico; these are the additional PWA entries.
                {
                    // iOS ignores the manifest's icons for "Add to Home Screen" and only looks
                    // at this link (or /apple-touch-icon.png at the origin root), so it has to
                    // be declared explicitly even though the manifest lists icons already.
                    rel: 'apple-touch-icon',
                    sizes: '180x180',
                    href: '/apple-touch-icon.png',
                },
                { rel: 'manifest', href: '/manifest.webmanifest' },
            ],
            meta: [
                // Keep in sync with the manifest's theme_color and the app bar's colour.
                { name: 'theme-color', content: '#1867C0' },
            ],
        },
    },
    experimental: {
        // How often an open tab polls /_nuxt/builds/latest.json for a newer build id, which is
        // what raises app/components/AppUpdatePrompt.vue. Nuxt's default is one hour, and the
        // check is a plain setTimeout chain -- navigating between routes does NOT trigger one --
        // so this interval alone bounds how long a tab can sit on a superseded build.
        // (`experimental.appManifest`, which powers this, is already on by default.)
        checkOutdatedBuildInterval: 1000 * 60 * 15,
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
